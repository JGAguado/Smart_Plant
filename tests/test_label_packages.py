"""Check generated scale precedence with the exact pinned ESPHome package loader."""
import copy
import importlib.metadata
import importlib.util
from pathlib import Path
import unittest

import yaml

from scripts import smartplant_gauge_contract as contract

ROOT = Path(__file__).resolve().parents[1]


class LabelPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("esphome") is None:
            raise unittest.SkipTest("Run with pinned ESPHome 2026.9.0")
        if importlib.metadata.version("esphome") != "2026.9.0":
            raise RuntimeError("Package precedence scenarios require ESPHome 2026.9.0")
        from esphome.components.packages import do_packages_pass
        cls.expand = staticmethod(do_packages_pass)
        core = yaml.safe_load((ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text().replace("!lambda", ""))
        config = yaml.safe_load((ROOT / "examples/multi-device/label_maker/example.yaml").read_text())
        config["metrics"]["humidity"]["scale"] = [0, 100]
        config["metrics"]["illuminance"]["scale"] = [0, 10000]
        cls.overrides = contract.substitutions(contract.resolve_metrics(config))
        cls.packages = {"core": {"substitutions": core["substitutions"]},
                        "display_scales": {"substitutions": cls.overrides}}

    def test_scale_package_after_core_supplies_all_generated_values(self):
        resolved = self.expand({"packages": copy.deepcopy(self.packages)})
        for name, value in self.overrides.items():
            self.assertEqual(resolved["substitutions"][name], value)

    def test_reversed_package_order_loses_custom_values(self):
        resolved = self.expand({"packages": dict(reversed(copy.deepcopy(self.packages).items()))})
        self.assertEqual(float(resolved["substitutions"]["light_max"]), 3775)
        self.assertEqual(float(resolved["substitutions"]["hum_max"]), 80)

    def test_device_substitutions_take_precedence_over_generated_package(self):
        resolved = self.expand({"substitutions": {"light_max": "5000"}, "packages": copy.deepcopy(self.packages)})
        self.assertEqual(resolved["substitutions"]["light_max"], "5000")


if __name__ == "__main__":
    unittest.main()
