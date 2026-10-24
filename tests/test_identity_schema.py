"""Validate rename behavior through ESPHome's real package/substitution loader."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml
ROOT = Path(__file__).resolve().parents[1]
@unittest.skipUnless(importlib.util.find_spec("esphome"), "ESPHome is required")
class EntityIdentityTests(unittest.TestCase):
    def test_display_rename_preserves_function_names_and_technical_identity(self):
        from esphome.core import CORE
        from esphome.config import read_config
        results=[]
        try:
            with tempfile.TemporaryDirectory() as directory:
                for label in ("First label", "Changed label"):
                    values={"device_name":"schema-plant", "configured_name":"schema-plant-abcdef",
                            "name_add_mac_suffix":"false", "friendly_name":label,
                            "wifi_ssid":"synthetic-wifi", "wifi_password":"synthetic-password",
                            "mqtt_broker":"192.0.2.1", "ota_password":"synthetic-ota",
                            "api_encryption_key":"AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
                            "label_image":str(ROOT/"docs/source/images/programming/Lemon_tree_label_page_1.png")}
                    source=yaml.safe_dump({"substitutions":values},sort_keys=False)
                    source+="packages:\n  core: !include "+str(ROOT/"examples/multi-device/packages/smart_plant_core.yaml")+"\n  transport: !include "+str(ROOT/"examples/multi-device/packages/smart_plant_profile_mqtt.yaml")+"\n"
                    path=Path(directory)/"schema.yaml";path.write_text(source)
                    CORE.reset();CORE.config_path=path;config=read_config({})
                    self.assertIsNotNone(config)
                    results.append({"name":config["esphome"]["name"],
                                    "friendly":config["esphome"]["friendly_name"],
                                    "sensor_names":{str(s["id"]):s.get("name") for s in config["sensor"] if "name" in s},
                                    "switch_names":{str(s["id"]):s.get("name") for s in config["switch"] if "name" in s},
                                    "prefix":config["mqtt"]["topic_prefix"]})
                    self.assertEqual(str(config["mqtt"]["discovery_unique_id_generator"]),"mac")
                    self.assertEqual(str(config["mqtt"]["discovery_object_id_generator"]),"device_name")
                self.assertNotEqual(results[0].pop("friendly"),results[1].pop("friendly"))
                self.assertEqual(results[0],results[1])
                self.assertEqual(results[0]["name"],"schema-plant-abcdef")
                self.assertEqual(results[0]["prefix"],"schema-plant-abcdef")
                self.assertEqual(results[0]["sensor_names"]["batpercent"],"Battery")
        finally:
            CORE.reset()
