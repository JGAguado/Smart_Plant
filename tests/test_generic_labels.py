"""Verify generated bands against executed firmware needles with synthetic inputs."""
import copy
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from PIL import Image
import yaml

from scripts import smartplant_gauge_contract as contract
from scripts import smartplant_label_maker as labels
import test_display_gauge as runtime

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/multi-device/label_maker/example.yaml"


class GenericLabelTests(unittest.TestCase):
    setUpClass = classmethod(runtime.DisplayGaugeTests.setUpClass.__func__)

    def test_default_scales_positions_and_band_endpoints_match_actual_firmware(self):
        config = yaml.safe_load(EXAMPLE.read_text())
        metrics = contract.resolve_metrics(config)
        core = yaml.safe_load((ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text().replace("!lambda", ""))
        page = core["display"][0]["pages"][0]["lambda"]
        calls = re.findall(r"draw_gauge\(id\((\w+)\)\.state,.*?has_state\(\),\s*(.+?),\s*(.+?),\s*(\d+),\s*(\d+),", page)
        self.assertEqual(len(calls), 4)
        for (metric, geometry), call in zip(contract.CONTRACT["metrics"].items(), calls):
            def resolve(value):
                return float(core["substitutions"][value[2:-1]] if value.startswith("${") else value)
            self.assertEqual([resolve(call[1]), resolve(call[2])], metrics[metric]["scale"])
            self.assertEqual(tuple(map(int, call[3:5])), tuple(geometry["position"]))
            midpoint = sum(metrics[metric]["band"]) / 2
            ctx = Mock()
            labels.plot_parameter(ctx, {"rel_range": metrics[metric]["band"], "abs_range": metrics[metric]["scale"],
                                        "position": geometry["position"], "radius": contract.CONTRACT["radius"]})
            result = subprocess.run([str(self.executable), str(midpoint), "1", *map(str, metrics[metric]["scale"]),
                                     "%.1f", *map(str, geometry["position"])], check=True, capture_output=True, text=True)
            self.assertAlmostEqual(float(result.stderr), ctx.arc.call_args_list[0].args[-1], delta=1e-6)
            self.assertAlmostEqual(ctx.arc.call_args_list[0].args[-2], contract.angle(metrics[metric]["scale"][0], metrics[metric]["scale"]))

    def test_explicit_scales_generate_matching_overrides(self):
        config = yaml.safe_load(EXAMPLE.read_text())
        config["metrics"]["humidity"]["scale"] = [0, 100]
        config["metrics"]["illuminance"]["scale"] = [0, 10000]
        metrics = contract.resolve_metrics(config)
        overrides = contract.substitutions(metrics)
        self.assertEqual(overrides["hum_min"], "0.0")
        self.assertEqual(overrides["hum_max"], "100.0")
        self.assertEqual(overrides["light_max"], "10000.0")
        for metric in ("humidity", "illuminance"):
            midpoint = sum(metrics[metric]["band"]) / 2
            position = contract.CONTRACT["metrics"][metric]["position"]
            result = subprocess.run([str(self.executable), str(midpoint), "1", *map(str, metrics[metric]["scale"]),
                                     "%.1f", *map(str, position)], check=True, capture_output=True, text=True)
            self.assertAlmostEqual(float(result.stderr), contract.angle(midpoint, metrics[metric]["scale"]), delta=1e-6)

    def test_invalid_or_unsupported_ranges_fail_before_any_output(self):
        config = yaml.safe_load(EXAMPLE.read_text())
        for metric, field, value in [("humidity", "band", [70, 30]), ("humidity", "scale", [50, 50]),
                                     ("humidity", "band", [0, 100]), ("moisture", "scale", [-10, 100]),
                                     ("illuminance", "scale", [1, 5000]), ("temperature", "band", [math.nan, 25])]:
            with self.subTest(metric=metric, field=field, value=value), tempfile.TemporaryDirectory() as temporary:
                candidate = copy.deepcopy(config)
                candidate["metrics"][metric][field] = value
                path = Path(temporary)
                (path / "input.yaml").write_text(yaml.safe_dump(candidate))
                result = subprocess.run([sys.executable, str(ROOT / "scripts/smartplant_label_maker.py"),
                                         "--config", str(path / "input.yaml"), "--image", str(path / "label.png"),
                                         "--substitutions", str(path / "display.yaml")], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((path / "label.png").exists())
                self.assertFalse((path / "display.yaml").exists())

    def test_cli_is_deterministic_and_outputs_one_bit_image_and_usable_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            command = [sys.executable, str(ROOT / "scripts/smartplant_label_maker.py"), "--config", str(EXAMPLE),
                       "--image", str(path / "label.png"), "--substitutions", str(path / "display.yaml")]
            subprocess.run(command, check=True, capture_output=True)
            first = (path / "label.png").read_bytes(), (path / "display.yaml").read_bytes()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(first, ((path / "label.png").read_bytes(), (path / "display.yaml").read_bytes()))
            with Image.open(path / "label.png") as image:
                self.assertEqual(image.mode, "1")
                self.assertEqual(image.size, (296, 128))
            self.assertEqual(yaml.safe_load((path / "display.yaml").read_text())["substitutions"],
                             contract.substitutions(contract.resolve_metrics(yaml.safe_load(EXAMPLE.read_text()))))


if __name__ == "__main__":
    unittest.main()
