"""Execute the package's real C++ lambdas and inspect both sleep action paths."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "examples/multi-device/packages/smart_plant_core.yaml"


class PackageLoader(yaml.SafeLoader):
    pass


PackageLoader.add_constructor("!lambda", lambda loader, node: loader.construct_scalar(node))
PACKAGE = yaml.load(CORE.read_text(), Loader=PackageLoader)
SCRIPTS = {script["id"]: script for script in PACKAGE["script"]}
PAGES = {page["id"]: page["lambda"] for page in PACKAGE["display"][0]["pages"]}
SUBSTITUTIONS = PACKAGE["substitutions"]


def resolve(source, overrides=None):
    values = dict(SUBSTITUTIONS, **(overrides or {}))
    for name, value in values.items():
        source = source.replace("${" + name + "}", str(value))
    return source


HARNESS = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>
#define id(x) x
struct Sensor { float state = 50; bool available = true; bool has_state() { return available; } };
Sensor batpercent, soil, light, temp, hum;
bool low_batt_active = false;
int page1 = 1, page_low_batt = 2;
int font_title, font_subtitle, font_parameters, font_icon, page_1_background;
enum Color { COLOR_OFF, COLOR_ON };
enum class TextAlign { TOP_LEFT, TOP_RIGHT, TOP_CENTER };
struct Time { bool valid = true; bool is_valid() { return valid; } };
struct Clock { Time value; Time now() { return value; } } esptime;
struct Display {
  Color background = COLOR_OFF, image_fg = COLOR_ON, image_bg = COLOR_OFF;
  std::vector<Color> foregrounds;
  std::vector<std::string> text;
  void fill(Color color) { background = color; }
  void image(int, int, int, Color fg, Color bg) { image_fg = fg; image_bg = bg; }
  void line(int, int, int, int, Color color) { foregrounds.push_back(color); }
  template<typename... Args>
  void printf(int, int, int, Color color, TextAlign, const char *format, Args... args) {
    char value[128]; std::snprintf(value, sizeof(value), format, args...);
    foregrounds.push_back(color); text.emplace_back(value);
  }
  void strftime(int, int, int, Color color, TextAlign, const char *, Time) {
    foregrounds.push_back(color);
  }
};
void evaluate() { EVALUATE }
int selected_page() { SELECT_PAGE }
void normal_page(Display &it) { NORMAL_PAGE }
void critical_page(Display &it) { CRITICAL_PAGE }
int main() {
  // Exact thresholds and their neighboring float values, with either restored latch.
  for (bool restored : {false, true}) {
    for (float value : {0.0f, 14.999f, 15.0f, 15.001f, 21.999f, 22.0f, 22.001f, 100.0f}) {
      batpercent = {value, true}; low_batt_active = restored; evaluate();
      assert(low_batt_active == (restored ? value < 22.0f : value <= 15.0f));
      assert(selected_page() == (low_batt_active ? page_low_batt : page1));
    }
    for (float value : {std::numeric_limits<float>::quiet_NaN(),
                        std::numeric_limits<float>::infinity(),
                        -std::numeric_limits<float>::infinity()}) {
      batpercent = {value, true}; low_batt_active = restored; evaluate();
      assert(low_batt_active == restored);
    }
    for (float value : {0.0f, 100.0f}) {
      batpercent = {value, false}; low_batt_active = restored; evaluate();
      assert(low_batt_active == restored);
    }
  }
  // Charge recovery and another discharge, across successive measurement cycles.
  low_batt_active = false;
  const float recovery_values[] = {15.0f, 20.0f, 22.0f, 20.0f, 15.0f};
  const bool recovery_expected[] = {true, true, false, false, true};
  for (int index = 0; index < 5; ++index) {
    batpercent = {recovery_values[index], true}; evaluate();
    assert(low_batt_active == recovery_expected[index]);
  }
  // Both valid and missing gauge/time paths must use the selected foreground.
  for (bool available : {false, true}) {
    soil.available = light.available = temp.available = hum.available = available;
    esptime.value.valid = available;
    for (float value : {29.999f, 30.0f, 30.001f}) {
      batpercent = {value, true}; Display display; normal_page(display);
      Color fg = value < 30.0f ? COLOR_OFF : COLOR_ON;
      Color bg = value < 30.0f ? COLOR_ON : COLOR_OFF;
      assert(display.background == bg && display.image_fg == fg && display.image_bg == bg);
      assert(!display.foregrounds.empty());
      for (Color color : display.foregrounds) assert(color == fg);
    }
  }
  for (float value : {std::numeric_limits<float>::quiet_NaN(),
                      std::numeric_limits<float>::infinity()}) {
    batpercent = {value, true}; Display display; normal_page(display);
    assert(display.background == COLOR_OFF && display.image_fg == COLOR_ON);
    for (Color color : display.foregrounds) assert(color == COLOR_ON);
  }
  batpercent = {10, false}; Display unknown; critical_page(unknown);
  assert(unknown.background == COLOR_ON && unknown.text.back() == "BATTERY --%");
  for (Color color : unknown.foregrounds) assert(color == COLOR_OFF);
  batpercent = {15, true}; Display critical; critical_page(critical);
  assert(critical.text.back() == "BATTERY 15%");
}
'''


class LowBatteryTests(unittest.TestCase):
    def source(self, overrides=None):
        evaluation = SCRIPTS["render_and_sleep"]["then"][0]["lambda"]
        selection = SCRIPTS["render_and_sleep"]["then"][1]["display.page.show"]
        source = HARNESS
        for marker, body in (("EVALUATE", evaluation), ("SELECT_PAGE", selection),
                             ("NORMAL_PAGE", PAGES["page1"]), ("CRITICAL_PAGE", PAGES["page_low_batt"])):
            source = source.replace(marker, resolve(body, overrides))
        return source

    def compile(self, directory, overrides=None):
        cpp = Path(directory) / "low_battery.cpp"
        binary = Path(directory) / "low_battery"
        cpp.write_text(self.source(overrides))
        result = subprocess.run(["g++", "-std=c++17", "-Werror=format", str(cpp), "-o", str(binary)],
                                capture_output=True, text=True)
        return result, binary

    @unittest.skipUnless(shutil.which("g++"), "g++ required for real package lambdas")
    def test_real_lambdas_at_thresholds_and_rendering_branches(self):
        with tempfile.TemporaryDirectory() as directory:
            result, binary = self.compile(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    @unittest.skipUnless(shutil.which("g++"), "g++ required for threshold validation")
    def test_invalid_threshold_overrides_fail_at_compile_time(self):
        for overrides in ({"low_batt_crit_pct": "-1"}, {"low_batt_exit_pct": "15"},
                          {"low_batt_warn_pct": "22"}, {"low_batt_warn_pct": "101"}):
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as directory:
                result, _ = self.compile(directory, overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Low-battery thresholds", result.stderr)

    def test_latch_is_persistent_and_core_has_no_transport_policy(self):
        latch = next(item for item in PACKAGE["globals"] if item["id"] == "low_batt_active")
        self.assertTrue(latch["restore_value"])
        self.assertEqual(latch["initial_value"], "false")
        self.assertNotIn("mqtt", PACKAGE)
        self.assertNotIn("storage_active", CORE.read_text())
        for profile in ("api", "mqtt"):
            text = (CORE.parent / f"smart_plant_profile_{profile}.yaml").read_text()
            self.assertIn("script.execute: acquire_normal", text)
        self.assertIn({"script.execute": "render_and_sleep"}, SCRIPTS["acquire_normal"]["then"])

    def test_normal_and_emergency_sleep_keep_confirmation_and_battery_duration(self):
        paths = []

        def find(value):
            if isinstance(value, list):
                if "safe_mode.mark_successful" in value:
                    paths.append(value)
                for child in value:
                    find(child)
            elif isinstance(value, dict):
                for child in value.values():
                    find(child)

        for name in ("enter_deep_sleep", "recover_display_busy"):
            find(SCRIPTS[name])
        self.assertEqual(len(paths), 2)
        self.assertEqual(SUBSTITUTIONS["low_batt_sleep_duration"], "24h")
        for actions in paths:
            confirm = actions.index("safe_mode.mark_successful")
            allow = actions.index({"deep_sleep.allow": "deep_sleep_control"})
            rail_off = actions.index({"switch.turn_off": "exc"})
            self.assertLess(confirm, allow)
            self.assertLess(allow, rail_off)
            decision = actions[rail_off + 1]["if"]
            self.assertEqual(decision["condition"]["lambda"], "return id(low_batt_active);")
            self.assertEqual(decision["then"], [{"deep_sleep.enter": {
                "id": "deep_sleep_control", "sleep_duration": "${low_batt_sleep_duration}"}}])
            self.assertEqual(decision["else"], [{"deep_sleep.enter": "deep_sleep_control"}])


if __name__ == "__main__":
    unittest.main()
