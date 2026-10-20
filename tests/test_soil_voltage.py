"""Execute pinned sensor filters with the package's real soil configuration.

Run with ESPHome 2026.9.0. Only storage and filter plumbing are local scaffolding;
median scheduling, median computation, rejection and calibration use its source.
No ADC, broker or device is used.
"""
import importlib.metadata
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SoilVoltageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.find_spec("esphome")
        if spec is None:
            raise unittest.SkipTest("Run with pinned ESPHome 2026.9.0")
        if importlib.metadata.version("esphome") != "2026.9.0":
            raise RuntimeError("Soil filter scenarios require ESPHome 2026.9.0")
        source = (Path(spec.origin).parent / "components/sensor/filter.cpp").read_text()
        cls.config = yaml.safe_load((ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text().replace("!lambda", ""))
        voltage = next(s for s in cls.config["sensor"] if s.get("id") == "soil_voltage")
        moisture = next(s for s in cls.config["sensor"] if s.get("id") == "soil")
        if voltage["platform"] != "adc" or moisture["platform"] != "copy" or moisture["source_id"] != "soil_voltage":
            raise AssertionError("Only one ADC source may drive the moisture copy")
        median, clamp = voltage["filters"]
        calibration, final = moisture["filters"]
        median, clamp = median["median"], clamp["clamp"]
        if not clamp["ignore_out_of_range"]:
            raise AssertionError("Invalid voltages must be rejected before calibration")
        points = []
        for point in calibration["calibrate_linear"]:
            for name, value in cls.config["substitutions"].items():
                point = point.replace("${" + name + "}", value)
            points.append(tuple(map(float, point.split("->"))))
        (x0, y0), (x1, y1) = points
        slope = (y1 - y0) / (x1 - x0)
        intercept = y0 - slope * x0
        code = r'''
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <optional>
#include <vector>
using std::optional;
#define ESP_LOGVV(...)
template<class T> struct FixedVector : std::vector<T> { void init(size_t n) { this->reserve(n); } };
struct Ring : std::vector<float> {
  size_t capacity;
  void push_overwrite(float v) { if (size() == capacity) erase(begin()); push_back(v); }
};
struct SlidingWindowFilter {
  Ring window_; uint16_t send_every_, send_at_;
  optional<float> new_value(float);
  virtual float compute_result() = 0;
};
struct SortedWindowFilter : SlidingWindowFilter { FixedVector<float> get_window_values_(); };
struct MedianFilter : SortedWindowFilter { float compute_result() override; };
struct ClampFilter {
  float min_, max_; bool ignore_out_of_range_;
  optional<float> new_value(float);
};
// PINNED
int main(int argc, char **argv) {
  MedianFilter median;
  median.window_.capacity = WINDOW;
  median.send_every_ = EVERY;
  median.send_at_ = EVERY - FIRST;
  ClampFilter clamp{MINIMUM, MAXIMUM, true};
  std::array<float, 3> calibration{SLOPE, INTERCEPT, INFINITY};
  for (int i = 1; i < argc; ++i) {
    auto value = median.new_value(std::stof(argv[i]));
    if (!value) continue;
    value = clamp.new_value(*value);
    if (!value) continue;
    const float x = *calibrate_linear_compute(&calibration, 1, *value);
    const float percent = *[&]() -> optional<float> { FINAL; }();
    std::cout << i << ' ' << *value << ' ' << percent << '\n';
  }
}
'''
        signatures = ["optional<float> SlidingWindowFilter::new_value", "FixedVector<float> SortedWindowFilter::get_window_values_",
                      "float MedianFilter::compute_result", "optional<float> ClampFilter::new_value",
                      "optional<float> calibrate_linear_compute"]
        code = code.replace("// PINNED", "\n".join(function(source, signature) for signature in signatures))
        replacements = {"WINDOW": median["window_size"], "EVERY": median["send_every"], "FIRST": median["send_first_at"],
                        "MINIMUM": clamp["min_value"], "MAXIMUM": clamp["max_value"], "SLOPE": slope,
                        "INTERCEPT": intercept, "FINAL": final["lambda"]}
        for key, value in replacements.items():
            code = code.replace(key, str(value))
        cls.temp = tempfile.TemporaryDirectory(prefix="smartplant-soil-")
        cls.addClassCleanup(cls.temp.cleanup)
        cpp = Path(cls.temp.name) / "soil.cpp"
        cls.executable = cpp.with_suffix("")
        cpp.write_text(code)
        compiled = subprocess.run(["g++", "-std=c++17", str(cpp), "-o", str(cls.executable)], text=True, capture_output=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def process(self, values):
        result = subprocess.run([str(self.executable), *map(str, values)], check=True, text=True, capture_output=True)
        return [tuple(map(float, line.split())) for line in result.stdout.splitlines()]

    def test_single_filtered_publication_and_copy_percentage(self):
        self.assertEqual(self.process([1.25] * 4), [])
        for voltage, percentage in [(1.25, 100), (2.025, 50), (2.8, 0)]:
            result = self.process([voltage] * 10)
            self.assertEqual([r[0] for r in result], [5, 10])
            for _, actual_voltage, actual_percent in result:
                self.assertAlmostEqual(actual_voltage, voltage, places=4)
                self.assertAlmostEqual(actual_percent, percentage, places=3)

    def test_median_rejects_spikes_and_invalid_windows(self):
        result = self.process([0.1, 2.025, 2.025, 2.025, 4.0])
        self.assertEqual(result, [(5, 2.025, 50)])
        for invalid in (0.1, 4.0, "nan", "inf", "-inf"):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.process([invalid] * 5), [])

    def test_calibration_and_three_second_cadence_are_preserved(self):
        self.assertEqual(self.config["substitutions"]["soil_v_wet"], "1.25")
        self.assertEqual(self.config["substitutions"]["soil_v_dry"], "2.8")
        acquire = next(s for s in self.config["script"] if s["id"] == "acquire_normal")
        repeat = next(action["repeat"] for action in acquire["then"] if "repeat" in action)
        self.assertEqual(repeat, {"count": 5, "then": [{"component.update": "soil_voltage"}, {"delay": "3s"}]})


if __name__ == "__main__":
    unittest.main()
