"""Run the real retained-control YAML and native C++ policy lambdas offline."""
from pathlib import Path
import math
import unittest

import yaml

from display_automation import DisplayProgram, DisplayRuntime, PackageLoader


ROOT = Path(__file__).resolve().parents[1]


class MaintenanceStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.program = DisplayProgram(ROOT, "mqtt", control=True)

    @classmethod
    def tearDownClass(cls):
        cls.program.close()

    def runtime(self, healthy_display=True):
        runtime = DisplayRuntime(self.program)
        def busy(ms):
            updates = [t for t, key, value in runtime.events
                       if key == "component.update" and value == "my_display"]
            return int(bool(updates) and healthy_display and 50 <= ms - updates[-1] < 350)
        runtime.busy = busy
        runtime.state.boot_sequence_complete = True
        return runtime

    def publications(self, runtime, entity):
        return [(t, value["state"]) for t, key, value in runtime.events
                if key == "text_sensor.template.publish" and value["id"] == entity]

    def updates(self, runtime):
        return [value for _, key, value in runtime.events if key == "component.update"]

    def test_admission_finite_threshold_and_missing_battery(self):
        for value, available, expected in [
            (49.999, True, "REJECTED_LOW_BATTERY"), (50, True, "ON"),
            (80, True, "ON"), (80, False, "BATTERY_UNAVAILABLE"),
            (math.nan, True, "BATTERY_UNAVAILABLE"), (math.inf, True, "BATTERY_UNAVAILABLE"),
            (-math.inf, True, "BATTERY_UNAVAILABLE"),
        ]:
            with self.subTest(value=value, available=available):
                runtime = self.runtime()
                runtime.state.batpercent.state = value
                runtime.state.batpercent.available = available
                runtime.state.maintenance_requested = True
                runtime.execute("prepare_cycle")
                runtime.run_until(30000)
                states = [state for _, state in self.publications(runtime, "maintenance_status")]
                self.assertIn(expected, states)
                self.assertEqual(runtime.state.maintenance_active, expected == "ON")
                if expected != "ON":
                    self.assertNotIn("ON", states)
                    self.assertFalse(runtime.state.maintenance_requested)
                    self.assertIsNotNone(runtime.sleep)

    def test_both_requests_choose_maintenance_before_storage(self):
        runtime = self.runtime()
        runtime.state.storage_requested = True
        runtime.state.maintenance_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(2000)
        self.assertTrue(runtime.state.maintenance_active)
        self.assertEqual(runtime.state.selected_page, runtime.state.page_maintenance)
        self.assertEqual(self.updates(runtime), ["max17043_id", "my_display"])
        self.assertFalse(runtime.state.storage_active)
        self.assertIsNone(runtime.sleep)

    def test_daily_storage_boot_only_samples_battery_and_preserves_long_sleep(self):
        runtime = self.runtime()
        runtime.state.storage_active = True
        runtime.execute("boot")
        runtime.run_until(5000)
        self.assertEqual(self.updates(runtime), ["max17043_id", "my_display"])
        self.assertEqual(runtime.state.selected_page, runtime.state.page_storage)
        self.assertEqual(runtime.sleep[1], 86400000)
        self.assertFalse(runtime.state.storage_display_refresh_pending)

    def test_storage_persists_when_broker_is_offline(self):
        runtime = self.runtime()
        runtime.state.storage_active = True
        runtime.state.mqtt_connected = False
        runtime.execute("boot")
        runtime.run_until(36000)
        self.assertEqual(self.updates(runtime), ["max17043_id", "my_display"])
        self.assertTrue(runtime.state.storage_active)
        self.assertEqual(runtime.sleep[1], 86400000)

    def test_rejected_maintenance_falls_back_to_storage_and_keeps_rejection(self):
        runtime = self.runtime()
        runtime.state.batpercent.state = 40
        runtime.state.storage_requested = True
        runtime.state.maintenance_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(5000)
        self.assertTrue(runtime.state.storage_active)
        self.assertEqual(runtime.state.selected_page, runtime.state.page_storage)
        self.assertIn((260, "REJECTED_LOW_BATTERY"), self.publications(runtime, "maintenance_status"))
        self.assertNotIn("OFF", [state for _, state in self.publications(runtime, "maintenance_status")])

    def test_busylow_without_observed_assertion_never_acknowledges_ota(self):
        runtime = self.runtime(healthy_display=False)
        runtime.state.maintenance_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(6000)
        states = [state for _, state in self.publications(runtime, "maintenance_status")]
        self.assertIn("DISPLAY_REFRESH_FAILED", states)
        self.assertNotIn("ON", states)
        self.assertIsNotNone(runtime.sleep)

    def test_ack_follows_real_busy_cycle(self):
        runtime = self.runtime()
        runtime.state.maintenance_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(2000)
        published = self.publications(runtime, "maintenance_status")
        self.assertEqual([state for _, state in published], ["ON"])
        refresh_at = next(t for t, key, value in runtime.events
                          if key == "component.update" and value == "my_display")
        self.assertGreaterEqual(published[0][0], refresh_at + 350 + 500)

    def test_watchdog_and_manual_off_clear_retained_command_and_restore_readings(self):
        old = self.program.substitutions["maintenance_timeout"]
        self.program.substitutions["maintenance_timeout"] = "2s"
        try:
            for manual in (False, True):
                with self.subTest(manual=manual):
                    runtime = self.runtime()
                    runtime.state.maintenance_requested = True
                    runtime.execute("prepare_cycle")
                    runtime.run_until(2000)
                    if manual:
                        runtime.execute("maintenance_control_off")
                    runtime.run_until(24000)
                    self.assertFalse(runtime.state.maintenance_active)
                    self.assertFalse(runtime.state.maintenance_requested)
                    self.assertIsNotNone(runtime.sleep)
                    self.assertNotIn("maintenance_watchdog", runtime.tasks)
                    self.assertIn("aht20_sensor", self.updates(runtime))
                    self.assertEqual(runtime.state.selected_page, runtime.state.page1)
                    commands = [value for _, key, value in runtime.events if key == "mqtt.publish"]
                    self.assertTrue(any(v.get("payload") == "OFF" and "/cmd/maintenance" in v["topic"]
                                        and v["qos"] == 1 and v["retain"] for v in commands))
        finally:
            self.program.substitutions["maintenance_timeout"] = old

    def test_repeated_on_cancels_old_deadline_before_new_refresh(self):
        old = self.program.substitutions["maintenance_timeout"]
        self.program.substitutions["maintenance_timeout"] = "2s"
        try:
            runtime = self.runtime()
            runtime.execute("maintenance_control_on")
            runtime.run_until(2900)
            # First watchdog expires after the first settled refresh plus 2s.
            # Renew while that deadline is close and before the new settle ends.
            runtime.execute("maintenance_control_on")
            runtime.run_until(4600)
            self.assertTrue(runtime.state.maintenance_active)
            self.assertTrue(runtime.state.maintenance_requested)
            self.assertNotIn("exit_maintenance", [v for _, k, v in runtime.events if k == "script.execute"])
            self.assertEqual([s for _, s in self.publications(runtime, "maintenance_status")], ["ON", "ON"])
        finally:
            self.program.substitutions["maintenance_timeout"] = old

    def test_successful_ota_clears_one_shot_without_new_display_refresh(self):
        runtime = self.runtime()
        runtime.state.storage_active = True
        runtime.state.maintenance_active = True
        runtime.state.maintenance_requested = True
        old = self.program.substitutions["maintenance_timeout"]
        self.program.substitutions["maintenance_timeout"] = "1s"
        runtime.execute("maintenance_watchdog")
        self.program.substitutions["maintenance_timeout"] = old
        runtime.execute("ota_end")
        runtime.run_until(2100)
        self.assertFalse(runtime.state.maintenance_requested)
        self.assertFalse(runtime.state.maintenance_active)
        self.assertTrue(runtime.state.storage_display_refresh_pending)
        self.assertNotIn("my_display", self.updates(runtime))
        self.assertIn("OFF", [s for _, s in self.publications(runtime, "maintenance_status")])
        self.assertNotIn("exit_maintenance", [v for _, k, v in runtime.events if k == "script.execute"])

    def test_storage_off_reacquires_plant_sensors_before_normal_sleep(self):
        runtime = self.runtime()
        runtime.state.storage_active = True
        runtime.state.storage_requested = True
        runtime.execute("storage_control_off")
        runtime.run_until(24000)
        self.assertFalse(runtime.state.storage_active)
        self.assertEqual(runtime.state.selected_page, runtime.state.page1)
        self.assertIn("aht20_sensor", self.updates(runtime))
        self.assertIn("veml7700_sensor", self.updates(runtime))
        self.assertEqual(self.updates(runtime).count("soil"), 5)
        self.assertEqual(runtime.sleep[1], 3600000)

    def test_storage_request_during_maintenance_waits_for_manual_exit(self):
        runtime = self.runtime()
        runtime.state.maintenance_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(2000)
        before = len(self.updates(runtime))
        runtime.execute("storage_control_on")
        runtime.run_until(2100)
        self.assertEqual(len(self.updates(runtime)), before)
        self.assertTrue(runtime.state.maintenance_active)
        runtime.execute("maintenance_control_off")
        runtime.run_until(5000)
        self.assertTrue(runtime.state.storage_active)
        self.assertEqual(runtime.state.selected_page, runtime.state.page_storage)
        self.assertEqual(runtime.sleep[1], 86400000)

    def test_critical_protection_overrides_storage_page_and_duration(self):
        runtime = self.runtime()
        runtime.state.batpercent.state = 15
        runtime.state.storage_requested = True
        runtime.execute("prepare_cycle")
        runtime.run_until(5000)
        self.assertTrue(runtime.state.low_batt_active)
        self.assertEqual(runtime.state.selected_page, runtime.state.page_low_batt)
        self.assertEqual(runtime.sleep[1], 86400000)

    def test_off_cancels_pending_sample_time_wait_and_maintenance_refresh(self):
        for at_ms, valid_time in [(100, True), (500, False), (500, True)]:
            with self.subTest(at_ms=at_ms, valid_time=valid_time):
                runtime = self.runtime()
                runtime.state.esptime.valid = valid_time
                runtime.execute("maintenance_control_on")
                runtime.run_until(at_ms)
                runtime.execute("maintenance_control_off")
                runtime.state.esptime.valid = True
                runtime.run_until(26000)
                self.assertFalse(runtime.state.maintenance_requested)
                self.assertFalse(runtime.state.maintenance_active)
                self.assertNotIn("ON", [s for _, s in self.publications(runtime, "maintenance_status")])
                self.assertIn("aht20_sensor", self.updates(runtime))
                self.assertEqual(self.updates(runtime).count("soil"), 5)
                self.assertEqual(runtime.sleep[1], 3600000)

    def test_latest_storage_command_cancels_pending_refresh_and_acquisition(self):
        for final_on in (False, True):
            with self.subTest(final_on=final_on):
                runtime = self.runtime()
                runtime.execute("storage_control_on")
                runtime.run_until(450)
                runtime.execute("storage_control_off")
                runtime.run_until(700)
                if final_on:
                    runtime.execute("storage_control_on")
                runtime.run_until(26000)
                self.assertEqual(runtime.state.storage_active, final_on)
                self.assertEqual(runtime.state.selected_page,
                                 runtime.state.page_storage if final_on else runtime.state.page1)
                self.assertEqual(runtime.sleep[1], 86400000 if final_on else 3600000)
                if final_on:
                    self.assertNotIn("acquire_normal", runtime.tasks)

    def test_rejection_off_echo_keeps_result_and_does_not_start_another_cycle(self):
        for storage in (False, True):
            with self.subTest(storage=storage):
                runtime = self.runtime()
                runtime.state.batpercent.state = 40
                runtime.state.storage_requested = storage
                runtime.execute("maintenance_control_on")
                runtime.run_until(500)
                # A broker forwards our retained cmd/maintenance OFF back to
                # the subscribed switch. TemplateSwitch runs OFF even if OFF.
                runtime.execute("maintenance_control_off")
                runtime.run_until(24000)
                self.assertEqual(self.updates(runtime).count("my_display"), 1)
                self.assertEqual(self.updates(runtime).count("max17043_id"), 1 if storage else 2)
                self.assertEqual(self.updates(runtime).count("soil"), 0 if storage else 5)
                self.assertEqual([s for _, s in self.publications(runtime, "maintenance_status")],
                                 ["REJECTED_LOW_BATTERY"])
                self.assertEqual(runtime.state.storage_active, storage)
                self.assertIsNotNone(runtime.sleep)

    def test_exit_off_echo_preserves_one_full_acquisition(self):
        old = self.program.substitutions["maintenance_timeout"]
        self.program.substitutions["maintenance_timeout"] = "2s"
        try:
            for manual in (False, True):
                with self.subTest(manual=manual):
                    runtime = self.runtime()
                    runtime.execute("maintenance_control_on")
                    runtime.run_until(2000)
                    if manual:
                        runtime.execute("maintenance_control_off")
                        runtime.run_until(2100)
                    else:
                        runtime.run_until(3300)
                    self.assertFalse(runtime.state.maintenance_active)
                    runtime.execute("maintenance_control_off")
                    runtime.run_until(26000)
                    started = [v for _, k, v in runtime.events if k == "script.execute"]
                    self.assertEqual(started.count("acquire_normal"), 1)
                    self.assertEqual(self.updates(runtime).count("soil"), 5)
                    self.assertEqual([s for _, s in self.publications(runtime, "maintenance_status")],
                                     ["ON", "OFF", "OFF"])
                    self.assertEqual(runtime.sleep[1], 3600000)
        finally:
            self.program.substitutions["maintenance_timeout"] = old

    def test_storage_duplicate_on_keeps_pending_acceptance_cycle(self):
        runtime = self.runtime()
        runtime.execute("storage_control_on")
        runtime.run_until(100)
        runtime.execute("storage_control_on")
        runtime.run_until(500)
        runtime.execute("storage_control_on")
        runtime.run_until(5000)
        self.assertEqual(self.updates(runtime), ["max17043_id", "my_display"])
        self.assertTrue(runtime.state.storage_active)
        self.assertEqual(runtime.sleep[1], 86400000)

    def test_storage_off_echo_keeps_one_acquisition_and_exit_refresh(self):
        runtime = self.runtime()
        runtime.state.storage_active = True
        runtime.state.storage_requested = True
        runtime.execute("storage_control_off")
        runtime.run_until(100)
        runtime.execute("storage_control_off")
        runtime.run_until(15100)
        # exit_storage has now published retained cmd/storage_mode OFF.
        runtime.execute("storage_control_off")
        runtime.run_until(34000)
        started = [v for _, k, v in runtime.events if k == "script.execute"]
        self.assertEqual(started.count("acquire_normal"), 1)
        self.assertEqual(self.updates(runtime).count("soil"), 5)
        self.assertEqual(self.updates(runtime).count("my_display"), 1)
        self.assertFalse(runtime.state.storage_active)
        self.assertEqual(runtime.sleep[1], 3600000)

    def test_storage_changes_and_duplicates_during_maintenance_keep_latest_request(self):
        runtime = self.runtime()
        runtime.execute("maintenance_control_on")
        runtime.run_until(2000)
        before = list(self.updates(runtime))
        for command in ("on", "on", "off", "off"):
            runtime.execute(f"storage_control_{command}")
        self.assertEqual(self.updates(runtime), before)
        self.assertFalse(runtime.state.storage_requested)
        self.assertTrue(runtime.state.maintenance_active)
        runtime.execute("maintenance_control_off")
        runtime.run_until(26000)
        self.assertFalse(runtime.state.storage_active)
        self.assertEqual(self.updates(runtime).count("soil"), 5)
        self.assertEqual(runtime.sleep[1], 3600000)

    def test_rejected_maintenance_acquires_initially_missing_plant_states(self):
        runtime = self.runtime()
        runtime.state.batpercent.state = 40
        for name in ("temp", "hum", "light", "soil"):
            sensor = getattr(runtime.state, name)
            sensor.available = False
            sensor.state = math.nan
        readings = {"aht20_sensor": {"temp": 21, "hum": 45},
                    "veml7700_sensor": {"light": 123}, "soil": {"soil": 42}}
        def update(component, state):
            for name, value in readings.get(component, {}).items():
                sensor = getattr(state, name)
                sensor.state = value
                sensor.available = True
        runtime.sensor_update = update
        runtime.execute("maintenance_control_on")
        runtime.run_until(500)
        runtime.execute("maintenance_control_off")  # retained rejection echo
        runtime.run_until(26000)
        for name, value in {"temp": 21, "hum": 45, "light": 123, "soil": 42}.items():
            self.assertTrue(getattr(runtime.state, name).available)
            self.assertEqual(getattr(runtime.state, name).state, value)
        self.assertEqual(self.updates(runtime).count("soil"), 5)
        self.assertEqual(runtime.state.selected_page, runtime.state.page1)
        self.assertEqual(runtime.sleep[1], 3600000)
        self.assertEqual([s for _, s in self.publications(runtime, "maintenance_status")],
                         ["REJECTED_LOW_BATTERY"])

    def test_topic_contract_persistence_and_transport_separation(self):
        packages = ROOT / "examples/multi-device/packages"
        mqtt = yaml.load((packages / "smart_plant_profile_mqtt.yaml").read_text(), PackageLoader)
        core = yaml.load((packages / "smart_plant_core.yaml").read_text(), PackageLoader)
        for switch in mqtt["switch"]:
            self.assertEqual(switch["subscribe_qos"], 1)
            self.assertEqual(switch["qos"], 1)
            self.assertTrue(switch["retain"] and switch["command_retain"])
            self.assertIn("/cmd/", switch["command_topic"])
        for sensor in mqtt["text_sensor"]:
            self.assertEqual(sensor["qos"], 1)
            self.assertTrue(sensor["retain"])
            self.assertIn("/status/", sensor["state_topic"])
        for package, name in ((core, "storage_active"), (mqtt, "storage_display_refresh_pending")):
            self.assertTrue(next(g for g in package["globals"] if g["id"] == name)["restore_value"])
        self.assertNotIn("mqtt", core)
        self.assertNotIn("mqtt.publish", (packages / "smart_plant_profile_api.yaml").read_text())
        names = [s["name"] for s in mqtt["switch"] + mqtt["text_sensor"]]
        self.assertEqual(len(names), len(set(names)))


class APIStorageIsolationTests(unittest.TestCase):
    def test_restored_mqtt_storage_cannot_change_api_page_or_sleep(self):
        program = DisplayProgram(ROOT, "api", control=True)
        try:
            for battery, latched, expected_low in [(80, False, False), (80, True, False),
                                                  (20, True, True), (math.nan, True, True)]:
                with self.subTest(battery=battery, latched=latched):
                    runtime = DisplayRuntime(program)
                    runtime.state.storage_active = True
                    runtime.state.low_batt_active = latched
                    runtime.state.batpercent.state = battery
                    def busy(ms):
                        updates = [t for t, k, v in runtime.events
                                   if k == "component.update" and v == "my_display"]
                        return int(bool(updates) and 50 <= ms - updates[-1] < 350)
                    runtime.busy = busy
                    runtime.execute("boot")
                    runtime.run_until(30000)
                    self.assertFalse(runtime.state.storage_active)
                    self.assertEqual(runtime.state.low_batt_active, expected_low)
                    self.assertEqual(runtime.state.selected_page,
                                     runtime.state.page_low_batt if expected_low else runtime.state.page1)
                    self.assertEqual(runtime.sleep[1], 86400000 if expected_low else 3600000)
        finally:
            program.close()


if __name__ == "__main__":
    unittest.main()
