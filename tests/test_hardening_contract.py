from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text()
API = (ROOT / "examples/multi-device/packages/smart_plant_profile_api.yaml").read_text()
MQTT = (ROOT / "examples/multi-device/packages/smart_plant_profile_mqtt.yaml").read_text()


class HardeningContractTest(unittest.TestCase):
    def test_transport_profiles_settle_rail_then_acquire_after_setup(self):
        for profile in (API, MQTT):
            self.assertLess(profile.index("priority: 700"), profile.index("priority: 399.0"))
            self.assertIn("delay(250)", profile)
            self.assertIn("script.execute: acquire_normal", profile)

    def test_sensor_cadence_is_bounded_and_soil_has_no_first_sample_publish(self):
        # Four sensors plus the display are manually driven.
        self.assertEqual(CORE.count("update_interval: never"), 5)
        self.assertIn("send_first_at: 5", CORE)
        self.assertIn("count: 5", CORE)
        self.assertIn("ignore_out_of_range: true", CORE)
        for timeout in ("timeout: 3s", "timeout: 5s", "timeout: 10s"):
            self.assertIn(timeout, CORE)

    def test_invalid_readings_are_not_rendered_as_numbers(self):
        self.assertIn("std::isfinite", CORE)
        self.assertIn('TextAlign::TOP_CENTER, "--"', CORE)
        self.assertIn('TextAlign::TOP_RIGHT, " --%%"', CORE)

    def test_sleep_requires_busy_low_and_recovery_is_bounded(self):
        self.assertIn("id: settle_display", CORE)
        self.assertIn("id: recover_display_busy", CORE)
        self.assertIn("script.stop: enter_deep_sleep", CORE)
        self.assertIn("display_busy_assert_timeout", CORE)
        self.assertIn("display_busy_clear_timeout", CORE)
        self.assertIn("display_busy_recovery_timeout", CORE)
        self.assertIn("digitalRead(${display_busy_gpio}) == LOW", CORE)
        self.assertLess(CORE.index("safe_mode.mark_successful"), CORE.index("deep_sleep.enter: deep_sleep_control"))

    def test_unreleased_component_tweaks_are_absent(self):
        self.assertNotIn("epaper_spi", CORE)
        self.assertNotIn("model: MAX17048", CORE)
        self.assertNotIn("max17043.sleep_mode", CORE)


if __name__ == "__main__":
    unittest.main()
