"""Execute the profile's YAML wait with pinned ESPHome C++ action classes.

Run with ESPHome 2026.9.0 installed. Only scheduler/hardware scaffolding is fake;
WaitUntilAction, APIConnectedCondition and the subscription lookup are extracted
from that installed implementation. No socket or device is used.
"""
import importlib.util
import importlib.metadata
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "examples/multi-device/packages/smart_plant_profile_api.yaml"

STUB = r"""
#include <cstdint>
#include <cmath>
#include <functional>
#include <iostream>
#include <list>
#include <optional>
#include <tuple>
using std::optional;
uint32_t clock_ms = 0;
uint32_t millis() { return clock_ms; }
struct Application { uint32_t get_loop_component_start_time() { return clock_ms; } } App;
namespace setup_priority { constexpr float DATA = 600; }
struct Component {
  bool enabled = false;
  virtual void setup() {}
  virtual void loop() {}
  virtual float get_setup_priority() const { return 0; }
  void enable_loop() { enabled = true; }
  void disable_loop() { enabled = false; }
};
template<typename T> struct Value {
  T data{};
  T value() const { return data; }
  optional<T> optional_value() const { return data; }
};
#define TEMPLATABLE_VALUE(T, name) protected: Value<T> name##_; \
 public: void set_##name(T value) { name##_.data = value; }
template<typename... Ts> struct Condition {
  virtual bool check(const Ts &...x) = 0;
  bool check_tuple(const std::tuple<Ts...> &args) { return std::apply([this](const Ts &...x) { return check(x...); }, args); }
};
template<typename... Ts> struct Action {
  int num_running_ = 0;
  std::function<void()> next;
  virtual void play_complex(const Ts &...) {}
  virtual void play(const Ts &...) {}
  virtual void stop() {}
  void play_next_(const Ts &...) { --num_running_; next(); }
  void play_next_tuple_(const std::tuple<Ts...> &) { --num_running_; next(); }
};
struct Client { struct { bool state_subscription = false; } flags_; };
struct APIServer {
  int api_connection_count_ = 1;
  Client client;
  Client *clients_[1] = {&client};
  bool connected = false;
  bool is_connected() const { return connected; }
  bool is_connected_with_state_subscription() const;
};
APIServer server;
APIServer *global_api_server = &server;
struct Sensor { float state; bool valid; bool has_state() const { return valid; } };
Sensor batpercent;
bool low_batt_active;
#define id(name) name
// PINNED_IMPLEMENTATION
int main(int argc, char **argv) {
  if (argc != 9) return 2;
  const uint32_t timeout = std::stoul(argv[1]);
  const int subscribed_at = std::stoi(argv[2]);
  const int disconnected_at = std::stoi(argv[3]);
  server.connected = std::stoi(argv[4]);
  APIConnectedCondition<> condition;
  condition.set_state_subscription_only(std::stoi(argv[5]));
  WaitUntilAction<> wait(&condition);
  wait.set_timeout_value(timeout);
  int acquired_at = -1;
  int acquisitions = 0;
  wait.next = [&] { acquired_at = clock_ms; ++acquisitions; };
  server.client.flags_.state_subscription = subscribed_at == 0;
  batpercent = {std::stof(argv[6]), static_cast<bool>(std::stoi(argv[7]))};
  low_batt_active = std::stoi(argv[8]);
  const bool allow_wait = [&]() { /* BATTERY_POLICY */ }();
  if (allow_wait) wait.play_complex();
  else wait.next();
  // Returning proves the wait does not hold up Wi-Fi setup at priority 250.
  const bool wifi_setup_reached = true;
  wait.setup(); // Must preserve a wait started before component setup.
  for (clock_ms = 1; clock_ms <= timeout + 100; ++clock_ms) {
    if (static_cast<int>(clock_ms) == subscribed_at) server.client.flags_.state_subscription = true;
    if (static_cast<int>(clock_ms) == disconnected_at) server.client.flags_.state_subscription = false;
    if (wait.enabled) wait.loop();
  }
  std::cout << acquired_at << ' ' << acquisitions << ' ' << wifi_setup_reached << '\n';
}
"""


class PackageLoader(yaml.SafeLoader):
    pass


PackageLoader.add_multi_constructor("!", lambda loader, tag, node: loader.construct_scalar(node))


class APIBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        installed = importlib.util.find_spec("esphome")
        if installed is None:
            raise unittest.SkipTest("Run this suite with pinned ESPHome 2026.9.0 installed")
        if importlib.metadata.version("esphome") != "2026.9.0":
            raise RuntimeError("API boot scenarios require exact ESPHome 2026.9.0")
        source = Path(installed.origin).parent
        cls.profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
        boot = cls.profile["esphome"]["on_boot"]
        acquire = next(action for action in boot if action["priority"] == 399.0)
        reset, sample, settled, guarded, execute = acquire["then"]
        if reset != {"lambda": "id(storage_active) = false;"}:
            raise AssertionError("API boot must clear Storage restored from the MQTT profile")
        if sample != {"script.execute": "sample_battery"} or settled != {"script.wait": "sample_battery"}:
            raise AssertionError("Battery sampling must finish before the optional API window")
        policy = guarded["if"]["condition"]["lambda"]
        core = yaml.load((ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text(), Loader=PackageLoader)
        policy = re.sub(r"\$\{([^}]+)\}", lambda m: core["substitutions"][m[1]], policy)
        wait, = guarded["if"]["then"]
        if execute != {"script.execute": "acquire_normal"}:
            raise AssertionError("API wait must continue into the production acquisition script")
        condition = wait["wait_until"]["condition"]["api.connected"]
        cls.subscription_only = condition["state_subscription_only"]
        duration = wait["wait_until"]["timeout"]
        duration = cls.profile["substitutions"][duration[2:-1]]
        cls.timeout = int(float(duration.removesuffix("s")) * 1000)
        if not 0 < cls.timeout <= 10000:
            raise AssertionError("Default API connection wait must be bounded by 10 seconds")
        if not cls.subscription_only:
            raise AssertionError("Logs-only clients must not satisfy the API readiness check")
        action = (source / "core/base_automation.h").read_text()
        action = action[action.index("template<typename... Ts> class WaitUntilAction"):
                        action.index("template<typename... Ts> class UpdateComponentAction")]
        api = (source / "components/api/api_server.h").read_text()
        api = api[api.index("template<typename... Ts> class APIConnectedCondition"):]
        api = api[:api.index("\n};") + len("\n};")]
        server = (source / "components/api/api_server.cpp").read_text()
        match = re.search(r"bool APIServer::is_connected_with_state_subscription\(\) const \{.*?\n\}", server, re.S)
        if match is None:
            raise AssertionError("Cannot extract exact subscription lookup")
        cls.temp = tempfile.TemporaryDirectory(prefix="smartplant-api-boot-")
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        cpp = path / "api.cpp"
        cls.executable = path / "api"
        cpp.write_text(STUB.replace("// PINNED_IMPLEMENTATION", match[0] + "\n" + api + "\n" + action)
                       .replace("/* BATTERY_POLICY */", policy))
        subprocess.run([shutil.which("g++") or "g++", "-std=c++17", str(cpp), "-o", str(cls.executable)],
                       check=True, capture_output=True, text=True)

    def run_scenario(self, subscribed_at=-1, disconnected_at=-1, connected=False, battery=80, valid=True, latched=False):
        result = subprocess.run([str(self.executable), str(self.timeout), str(subscribed_at),
                                 str(disconnected_at), str(int(connected)), str(int(self.subscription_only)),
                                 str(battery), str(int(valid)), str(int(latched))],
                                check=True, capture_output=True, text=True, timeout=5)
        return tuple(map(int, result.stdout.split()))

    def test_early_subscriber_acquires_immediately(self):
        self.assertEqual(self.run_scenario(subscribed_at=0, connected=True), (0, 1, 1))

    def test_late_subscriber_releases_wait(self):
        self.assertEqual(self.run_scenario(subscribed_at=7000, connected=True), (7000, 1, 1))

    def test_logs_only_client_does_not_release_wait(self):
        self.assertEqual(self.run_scenario(connected=True), (self.timeout, 1, 1))

    def test_no_ha_still_acquires_once_after_timeout(self):
        self.assertEqual(self.run_scenario(), (self.timeout, 1, 1))

    def test_disconnect_during_acquisition_does_not_restart_wait(self):
        self.assertEqual(self.run_scenario(subscribed_at=1000, disconnected_at=1001, connected=True),
                         (1000, 1, 1))

    def test_critical_battery_skips_optional_network_wait(self):
        for battery in [0, 14.9, 15]:
            with self.subTest(battery=battery):
                self.assertEqual(self.run_scenario(battery=battery), (0, 1, 1))

    def test_restored_latch_waits_only_after_valid_exit(self):
        for battery, expected in [(15.1, 0), (21.9, 0), (22, self.timeout), (30, self.timeout)]:
            with self.subTest(battery=battery):
                self.assertEqual(self.run_scenario(battery=battery, latched=True), (expected, 1, 1))

    def test_invalid_latched_battery_skips_wait(self):
        for battery, valid in [(80, False), ("nan", True), ("inf", True), ("-inf", True)]:
            with self.subTest(battery=battery, valid=valid):
                self.assertEqual(self.run_scenario(battery=battery, valid=valid, latched=True), (0, 1, 1))

    def test_healthy_or_unlatched_unavailable_battery_keeps_bounded_wait(self):
        for battery, valid in [(15.1, True), (22, True), (80, False), ("nan", True), ("inf", True)]:
            with self.subTest(battery=battery, valid=valid):
                self.assertEqual(self.run_scenario(battery=battery, valid=valid), (self.timeout, 1, 1))


if __name__ == "__main__":
    unittest.main()
