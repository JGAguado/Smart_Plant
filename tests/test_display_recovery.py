from pathlib import Path
import unittest

from display_automation import DisplayProgram, DisplayRuntime


ROOT = Path(__file__).resolve().parents[1]


class LateBusyRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.programs = {profile: DisplayProgram(ROOT, profile) for profile in ("api", "mqtt")}

    @classmethod
    def tearDownClass(cls):
        for program in cls.programs.values():
            program.close()

    def runtimes(self, busy):
        for profile, program in self.programs.items():
            for reverse in (False, True):
                runtime = DisplayRuntime(program, busy, reverse)
                runtime.state.busy = busy(0)
                yield runtime

    def test_late_permanent_high_reaches_emergency_sleep(self):
        for runtime in self.runtimes(lambda ms: int(ms >= 500)):
            runtime.execute("enter_deep_sleep")
            runtime.run_until(34000)
            self.assertIsNotNone(runtime.sleep)
            self.assertEqual(runtime.state.display_busy_fault_count, 1)
            self.assertEqual(runtime.state.reset_low_count, 1)
            self.assertEqual(runtime.state.reset_high_count, 1)
            self.assertIn("recover_display_busy", [e[2] for e in runtime.events if e[1] == "script.execute"])

    def test_late_transient_high_resumes_safe_sleep(self):
        for runtime in self.runtimes(lambda ms: int(500 <= ms < 2000)):
            runtime.execute("enter_deep_sleep")
            runtime.run_until(5000)
            self.assertIsNotNone(runtime.sleep)
            self.assertEqual(runtime.sleep[1], 3600000)
            self.assertEqual(runtime.state.display_busy_fault_count, 0)
            self.assertLess(runtime.sleep[0], 4000)

    def test_recovery_to_sleep_race_returns_to_recovery(self):
        for runtime in self.runtimes(lambda ms: int(500 <= ms < 2000 or ms >= 3000)):
            runtime.execute("enter_deep_sleep")
            runtime.run_until(37000)
            starts = [t for t, key, name in runtime.events
                      if key == "script.execute" and name == "recover_display_busy"]
            self.assertEqual(starts, [1000, 3500])
            self.assertIsNotNone(runtime.sleep)
            self.assertEqual(runtime.state.display_busy_fault_count, 1)

    def test_normal_sleep_preserves_battery_and_storage_priority(self):
        for runtime in self.runtimes(lambda ms: 0):
            for low_battery, storage, duration in ((False, False, 3600000),
                                                  (False, True, 86400000),
                                                  (True, True, 86400000)):
                trial = DisplayRuntime(runtime.program)
                trial.state.low_batt_active = low_battery
                trial.state.storage_active = storage
                trial.execute("enter_deep_sleep")
                trial.run_until(2000)
                self.assertEqual(trial.sleep, (1000, duration))
                self.assertEqual(trial.state.display_busy_fault_count, 0)


if __name__ == "__main__":
    unittest.main()
