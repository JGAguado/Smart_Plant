"""Execute the public renderer with UBSan and its real YAML automation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml
from display_automation import DisplayProgram, DisplayRuntime, PackageLoader

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "docs/source/files/configuration.yaml"

STUB = r"""
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
using std::abs;
#define id(name) name
struct Sensor { float state; bool present; bool has_state() const { return present; } };
struct Now { bool is_valid() const { return false; } };
struct Clock { Now now() { return {}; } };
enum class TextAlign { TOP_CENTER, TOP_LEFT, TOP_RIGHT };
struct Display {
  void image(int,int,int) {}
  void line(int x0,int y0,int x1,int y1) { std::cout << "line " << x0 << ' ' << y0 << ' ' << x1 << ' ' << y1 << '\n'; }
  void printf(int x,int y,int,TextAlign,const char *fmt,...) {
    char result[256]; va_list args; va_start(args,fmt);
    vsnprintf(result,sizeof result,fmt,args); va_end(args);
    std::cout << "text " << x << ' ' << y << ' ' << result << '\n';
  }
  void strftime(int,int,int,TextAlign,const char *,Now) {}
};
int main(int argc,char **argv) {
  if(argc != 11) return 2;
  Sensor batpercent{strtof(argv[1],nullptr),atoi(argv[2]) != 0};
  Sensor soil{strtof(argv[3],nullptr),atoi(argv[4]) != 0};
  Sensor light{strtof(argv[5],nullptr),atoi(argv[6]) != 0};
  Sensor temp{strtof(argv[7],nullptr),atoi(argv[8]) != 0};
  Sensor hum{strtof(argv[9],nullptr),atoi(argv[10]) != 0};
  Clock esptime; Display it;
  int page_1_background=0,font_title=0,font_subtitle=0,font_parameters=0,font_icon=0;
  // ACTUAL_PAGE
}
"""


class StandaloneRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = yaml.load(PUBLIC.read_text(), PackageLoader)
        page = package["display"][0]["pages"][0]["lambda"]
        cls.temp = tempfile.TemporaryDirectory(prefix="smartplant-public-renderer-")
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        source = path / "renderer.cpp"
        cls.executable = path / "renderer"
        source.write_text(STUB.replace("// ACTUAL_PAGE", page))
        subprocess.run(["c++", "-std=c++20", "-fsanitize=undefined,float-cast-overflow",
                        "-fno-sanitize-recover=all", str(source), "-o", str(cls.executable)], check=True)

    def render(self, values, present=None):
        present = present or [True] * 5
        args = [item for value, exists in zip(values, present) for item in (str(value), str(int(exists)))]
        result = subprocess.run([str(self.executable), *args], check=True, text=True, capture_output=True)
        text, lines = {}, []
        for line in result.stdout.splitlines():
            if line.startswith("text "):
                _, x, y, label = line.split(" ", 3)
                text.setdefault((int(x), int(y)), []).append(label)
            else:
                lines.append(tuple(map(int, line.split()[1:])))
        return text, lines

    def test_missing_nonfinite_and_extreme_battery_never_cast_invalid_values(self):
        for value, present in [("nan", True), ("inf", True), ("-inf", True), (42, False)]:
            text, lines = self.render([value, 50, 1000, 25, 50], [present, True, True, True, True])
            self.assertEqual([label.strip() for label in text[(278, 1)]], ["--%"])
            self.assertEqual(len(lines), 12)
        for value in ("1e30", "-1e30", -5, 120):
            text, _ = self.render([value, 50, 1000, 25, 50])
            self.assertEqual(len(text[(278, 1)]), 2)

    def test_each_missing_or_nonfinite_gauge_has_placeholder_and_no_needle(self):
        positions = [(102, 87), (156, 107), (210, 87), (264, 107)]
        for index, position in enumerate(positions, 1):
            for value, exists in [(42, False), ("nan", True), ("inf", True), ("-inf", True)]:
                values, present = [50, 50, 1000, 25, 50], [True] * 5
                values[index], present[index] = value, exists
                text, lines = self.render(values, present)
                self.assertEqual(text[position], ["--"])
                self.assertEqual(len(lines), 9)

    def test_out_of_range_text_stays_raw_and_needles_match_endpoints(self):
        raw = [75, 120, 10000, -15, 90]
        clamped = [75, 100, 3775, -10, 80]
        text, lines = self.render(raw)
        _, endpoint_lines = self.render(clamped)
        self.assertEqual(lines, endpoint_lines)
        for position, expected in [((102, 87), "120%"), ((156, 107), "10000lx"),
                                   ((210, 87), "-15°C"), ((264, 107), "90%")]:
            self.assertEqual(text[position], [expected])


class StandaloneFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.program = DisplayProgram(ROOT, standalone=True)
        cls.addClassCleanup(cls.program.close)

    def runtime(self, busy, reverse=False):
        runtime = DisplayRuntime(self.program, busy, reverse)
        runtime.state.busy = busy(0)
        return runtime

    def assert_valid_sleep(self, runtime):
        self.assertIsNotNone(runtime.sleep)
        self.assertEqual(runtime.sleep[1], 3600000)
        keys = [event[1] for event in runtime.events]
        self.assertEqual(keys.count("safe_mode.mark_successful"), 1)
        self.assertLess(keys.index("safe_mode.mark_successful"), keys.index("deep_sleep.enter"))

    def test_boot_after_setup_and_normal_refresh_observes_busy(self):
        package = yaml.load(PUBLIC.read_text(), PackageLoader)
        self.assertLess(package["esphome"]["on_boot"]["priority"], 400)
        for reverse in (False, True):
            runtime = self.runtime(lambda ms: int(10000 <= ms < 12000), reverse)
            runtime.execute("consider_deep_sleep")
            runtime.run_until(15000)
            self.assert_valid_sleep(runtime)
            self.assertTrue(runtime.state.display_busy_seen)
            self.assertTrue(runtime.state.display_settle_ok)
            self.assertEqual(sum(e[1] == "component.update" for e in runtime.events), 1)

    def test_fault_and_oscillation_reach_one_bounded_sleep_request(self):
        signals = (lambda ms: 1, lambda ms: int(ms % 2000 >= 600),
                   lambda ms: int(ms < 29900), lambda ms: int(ms % 600 >= 300))
        for signal in signals:
            for reverse in (False, True):
                runtime = self.runtime(signal, reverse)
                runtime.state.display_safe_to_sleep = False
                runtime.execute("recover_display_busy")
                runtime.run_until(32000)
                self.assert_valid_sleep(runtime)
                self.assertLessEqual(runtime.sleep[0], 30530)
                self.assertEqual(runtime.state.reset_low_count, 1)
                self.assertEqual(runtime.state.reset_high_count, 1)
                self.assertFalse([e for e in runtime.events if e[1] == "component.update"])

    def test_late_high_after_settle_enters_recovery(self):
        for reverse in (False, True):
            runtime = self.runtime(lambda ms: int(ms >= 500), reverse)
            runtime.execute("enter_deep_sleep")
            runtime.run_until(33000)
            self.assert_valid_sleep(runtime)
            self.assertEqual(runtime.state.reset_low_count, 1)

    def test_new_refresh_cancels_wait_guard_sleep_reset_and_old_notification(self):
        for cancel, signal in [(100, lambda ms: 1), (250, lambda ms: 0),
                               (2000, lambda ms: int(ms < 1000)),
                               (30000, lambda ms: 1), (30200, lambda ms: 1)]:
            for reverse in (False, True):
                runtime = self.runtime(signal, reverse)
                runtime.state.display_safe_to_sleep = False
                runtime.execute("recover_display_busy")
                runtime.run_until(cancel)
                runtime.busy = lambda ms: int(ms < cancel + 1000)
                runtime.state.busy = 1
                runtime.refresh()
                runtime.run_until(cancel + 4000)
                self.assertIsNone(runtime.sleep)
                self.assertFalse(runtime.tasks)
                self.assertTrue(runtime.state.display_safe_to_sleep)
                self.assertEqual(runtime.state.reset_low_count, runtime.state.reset_high_count)


if __name__ == "__main__":
    unittest.main()
