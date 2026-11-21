"""Execute candidate C++ and, when requested, the real ESPHome host renderer.

DRAWN_DISPLAY_HOST=/absolute/path/to/program enables the exact ESPHome tests.
The host executable has no broker, Wi-Fi, HA or panel transport.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image, ImageChops
from PIL.ImageFilter import MaxFilter
import cairo
import yaml

ROOT = Path(__file__).resolve().parents[1]


class IntegratedPageTests(unittest.TestCase):
    def test_shared_and_standalone_use_the_same_generic_page(self):
        from display_automation import PackageLoader
        pages = [yaml.load((ROOT / filename).read_text(), PackageLoader)
                 for filename in ("examples/multi-device/packages/smart_plant_core.yaml",
                                  "docs/source/files/configuration.yaml")]
        self.assertEqual(pages[0]["display"][0]["pages"][0]["lambda"],
                         pages[1]["display"][0]["pages"][0]["lambda"])
        for page in pages:
            self.assertEqual(len(page["image"]), 1)
            self.assertEqual(page["image"][0]["file"], "${plant_illustration}")
            self.assertNotIn("page_1_background", page["display"][0]["pages"][0]["lambda"])

    def test_invalid_fixed_ranges_fail_in_the_actual_firmware_lambda(self):
        import test_low_battery as battery
        checker = battery.LowBatteryTests()
        for overrides in ({"light_max": "0"}, {"hum_recommended_min": "-1"},
                          {"temp_recommended_min": "35", "temp_recommended_max": "30"}):
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as temporary:
                result, _ = checker.compile(temporary, overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("display range", result.stderr)
@unittest.skipUnless(os.environ.get("DRAWN_DISPLAY_HOST"), "set DRAWN_DISPLAY_HOST to run exact ESPHome pixel tests")
class ESPHomePageTests(unittest.TestCase):
    def render(self, battery=70, values=(40, 1500, 22, 50), present=True, **environment):
        with tempfile.TemporaryDirectory(prefix="smartplant-host-") as temporary:
            path = Path(temporary)
            image = path / "page.pgm"
            pairs = [(battery, True)] + [(value, present) for value in values]
            env = dict(os.environ, ESPHOME_PREFDIR=str(path / "prefs"), SMART_PLANT_OUTPUT=str(image),
                       SMART_PLANT_VALUES=" ".join(f"{value} {int(state)}" for value, state in pairs),
                       **environment)
            result = subprocess.run([os.environ["DRAWN_DISPLAY_HOST"]], env=env, cwd=path,
                                    check=True, capture_output=True, text=True, timeout=10)
            self.assertIn("PROOF us=", result.stdout)
            self.assertNotIn("Encountered character without representation", result.stdout + result.stderr)
            with Image.open(image) as bitmap:
                return bitmap.copy()

    def test_warning_page_is_pixel_inverse_outside_changed_battery_text(self):
        normal, warning = self.render(), self.render(battery=25)
        diff = ImageChops.difference(normal, ImageChops.invert(warning))
        self.assertIsNone(diff.crop((0, 18, 296, 128)).getbbox())
        self.assertIsNone(diff.crop((0, 0, 194, 18)).getbbox())

    def test_warning_threshold_is_strictly_below_fixed_yaml_value(self):
        self.assertEqual(self.render(battery=29.99).getpixel((295, 127)), 0)
        self.assertEqual(self.render(battery=30).getpixel((295, 127)), 255)

    def test_missing_nan_infinity_and_extremes_render_in_both_polarities(self):
        for battery in (25, 70, "nan", "inf", "-inf", "3e38", "-3e38"):
            for values, present in [(("nan", "inf", "-inf", 0), True),
                                    ((0, 0, 0, 0), False),
                                    ((-100, 10000, -15, 120), True),
                                    (("3e38", "-3e38", "3e38", "-3e38"), True)]:
                with self.subTest(battery=battery, values=values):
                    self.assertEqual(self.render(battery, values, present).size, (296, 128))

    def test_long_titles_expose_existing_overflow_without_implicit_relayout(self):
        empty = self.render(SMART_PLANT_TITLE="", SMART_PLANT_SUBTITLE="")
        long = self.render(SMART_PLANT_TITLE="W" * 100, SMART_PLANT_SUBTITLE="W" * 100)
        # This is an observed compatibility limit, not a layout acceptance claim.
        self.assertIsNotNone(ImageChops.difference(empty, long).crop((194, 0, 296, 37)).getbbox())
        for title in ("100% Pilea", "Prêle et cœurs"):
            candidate = self.render(SMART_PLANT_TITLE=title, SMART_PLANT_SUBTITLE="")
            diff = ImageChops.difference(empty, candidate)
            self.assertIsNone(diff.crop((194, 0, 296, 128)).getbbox())
            self.assertIsNone(diff.crop((0, 37, 296, 128)).getbbox())
            self.assertIsNotNone(diff.getbbox())

    def test_valid_clock_changes_only_clock_area(self):
        diff = ImageChops.difference(self.render(), self.render(SMART_PLANT_CLOCK_VALID="1"))
        self.assertIsNotNone(diff.crop((194, 18, 278, 37)).getbbox())
        self.assertIsNone(diff.crop((0, 37, 296, 128)).getbbox())

    def test_band_edges_zero_width_and_whole_scale_have_preserved_fill_meaning(self):
        def rings(band):
            return self.render(SMART_PLANT_RING_ONLY="1", SMART_PLANT_RECOMMENDATION=band)
        minimum, middle, maximum = rings("0 0"), rings("0.5 0.5"), rings("1 1")
        self.assertIsNone(ImageChops.difference(middle, rings("0 1")).getbbox())
        counts = [sum(p == 0 for p in image.getdata()) for image in (minimum, middle, maximum)]
        self.assertLess(counts[0], counts[1])
        self.assertLess(counts[1], counts[2])

    def test_ring_raster_preserves_legacy_geometry_with_one_pixel_edge_tolerance(self):
        from scripts import smartplant_label_maker as reference
        page = yaml.safe_load((ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text().replace("!lambda", ""))
        values = page["substitutions"]
        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 296, 128)
        context = cairo.Context(surface)
        context.set_source_rgb(1, 1, 1)
        context.paint()
        for prefix, scale, position in [
            ("soil", [0, 100], [80, 50]),
            ("light", [0, float(values["light_max"])], [134, 70]),
            ("temp", [float(values["temp_min"]), float(values["temp_max"])], [188, 50]),
            ("hum", [float(values["hum_min"]), float(values["hum_max"])], [242, 70]),
        ]:
            reference.plot_parameter(context, {
                "abs_range": scale, "rel_range": [float(values[f"{prefix}_recommended_min"]),
                                                   float(values[f"{prefix}_recommended_max"])],
                "position": position, "radius": 22})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reference.png"
            surface.write_to_png(str(path))
            with Image.open(path) as image:
                expected = image.convert("L").point(lambda p: 255 if p >= 160 else 0)
        candidate = self.render(SMART_PLANT_RING_ONLY="1")
        # Cairo antialiasing and ESPHome binary pixels use different coverage.
        # Every ink pixel must be within one pixel of the other renderer's ink.
        actual_ink, expected_ink = ImageChops.invert(candidate), ImageChops.invert(expected)
        self.assertIsNone(ImageChops.subtract(actual_ink, expected_ink.filter(MaxFilter(3))).getbbox())
        self.assertIsNone(ImageChops.subtract(expected_ink, actual_ink.filter(MaxFilter(3))).getbbox())
        difference = ImageChops.difference(candidate, expected)
        self.assertLess(sum(bool(p) for p in difference.getdata()), 300)


if __name__ == "__main__":
    unittest.main()
