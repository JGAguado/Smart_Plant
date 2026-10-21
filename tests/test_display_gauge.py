"""Execute the production gauge lambda with a minimal C++ display recorder.

Run: python3 -m unittest discover -s tests -p test_display_gauge.py
Requires g++; no ESPHome build or hardware access is needed.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "examples/multi-device/packages/smart_plant_core.yaml"

STUB = r"""
#include <array>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

enum class TextAlign { TOP_CENTER };
#define id(name) name

struct Display {
  std::string label;
  double needle_angle = NAN;
  std::vector<std::array<int, 4>> lines;
  void line(int x0, int y0, int x1, int y1, int = 1) {
    lines.push_back({x0, y0, x1, y1});
  }
  void printf(int x, int y, int font, TextAlign align, const char *fmt, float value) {
    printf(x, y, font, 1, align, fmt, value);
  }
  void printf(int x, int y, int font, TextAlign align, const char *fmt) {
    printf(x, y, font, 1, align, fmt);
  }
  void printf(int, int, int, int, TextAlign, const char *fmt, ...) {
    char buffer[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    label = buffer;
  }
};

int main(int argc, char **argv) {
  if (argc != 8) return 2;
  Display it;
  int font_parameters = 0;
  int fg = 1;
  // PRODUCTION_LAMBDA
  draw_gauge(std::stof(argv[1]), std::string(argv[2]) == "1",
             std::stof(argv[3]), std::stof(argv[4]),
             std::stoi(argv[6]), std::stoi(argv[7]), argv[5]);
  std::cout << it.label << '\n';
  std::cerr << std::setprecision(10) << it.needle_angle;
  for (const auto &line : it.lines) {
    for (int coordinate : line) std::cout << coordinate << ' ';
    std::cout << '\n';
  }
  return 0;
}
"""


class DisplayGaugeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("g++")
        if compiler is None:
            raise RuntimeError("g++ is required to execute the production gauge")
        source = CORE.read_text(encoding="utf-8")
        start = source.index("          float pi =", source.index("- id: page1"))
        end = source.index("          };", start) + len("          };")
        gauge = textwrap.dedent(source[start:end])
        if "auto draw_gauge =" not in gauge:
            raise AssertionError("production draw_gauge lambda was not extracted")
        # Observe its angle before integer pixel rounding. Keep the production
        # value calculation and all drawing operations intact.
        gauge = gauge.replace("int x0 =", "it.needle_angle = pi / 2 + beta / 2 + val;\nint x0 =", 1)
        cls.temp = tempfile.TemporaryDirectory(prefix="smartplant-gauge-")
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        cpp = path / "gauge.cpp"
        cls.executable = path / "gauge"
        cpp.write_text(STUB.replace("// PRODUCTION_LAMBDA", gauge), encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", str(cpp),
             "-o", str(cls.executable)],
            check=True, capture_output=True, text=True,
        )

    def render(self, value, minimum, maximum, fmt, has_state=True, position=(80, 50)):
        result = subprocess.run(
            [str(self.executable), str(value), "1" if has_state else "0",
             str(minimum), str(maximum), fmt, *map(str, position)],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        return result[0], [tuple(map(int, line.split())) for line in result[1:]]

    def test_raw_numbers_and_clamped_needles(self):
        cases = [
            (10000, 0, 3775, "%.0flx", "10000lx"),
            (90, 20, 80, "%.0f%%", "90%"),
            (-15, -10, 50, "%.0f°C", "-15°C"),
            (-5, 0, 100, "%.0f%%", "-5%"),
            (120, 0, 100, "%.0f%%", "120%"),
            (52.5, -10, 50, "%.1f°C", "52.5°C"),
        ]
        for value, minimum, maximum, fmt, expected in cases:
            with self.subTest(value=value, fmt=fmt):
                label, needle = self.render(value, minimum, maximum, fmt)
                endpoint = min(max(value, minimum), maximum)
                _, endpoint_needle = self.render(endpoint, minimum, maximum, fmt)
                self.assertEqual(label, expected)
                self.assertEqual(len(needle), 3)
                self.assertEqual(needle, endpoint_needle)

    def test_in_range_and_boundaries(self):
        expected = {
            0: [(86, 87, 79, 90), (79, 90, 83, 94), (83, 94, 86, 87)],
            50: [(102, 50, 104, 43), (104, 43, 99, 43), (99, 43, 102, 50)],
            100: [(117, 87, 120, 94), (120, 94, 124, 90), (124, 90, 117, 87)],
        }
        for value, needle in expected.items():
            with self.subTest(value=value):
                label, actual = self.render(value, 0, 100, "%.0f%%")
                self.assertEqual(label, f"{value}%")
                self.assertEqual(actual, needle)

    def test_invalid_or_missing_values_have_no_needle(self):
        for value, has_state in [(42, False), ("nan", True), ("inf", True),
                                 ("-inf", True), ("nan", False)]:
            with self.subTest(value=value, has_state=has_state):
                self.assertEqual(
                    self.render(value, 0, 100, "%.0f%%", has_state), ("--", [])
                )


if __name__ == "__main__":
    unittest.main()
