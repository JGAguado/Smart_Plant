from pathlib import Path
import unittest

from display_automation import DisplayProgram, DisplayRuntime


ROOT = Path(__file__).resolve().parents[1]


class RecoveryBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.programs = {profile: DisplayProgram(ROOT, profile) for profile in ("api", "mqtt")}

    @classmethod
    def tearDownClass(cls):
        for program in cls.programs.values():
            program.close()

    def runtimes(self, busy):
        for program in self.programs.values():
            for reverse in (False, True):
                for refresh_index in range(len(program.refresh_sequences)):
                    runtime = DisplayRuntime(program, busy, reverse)
                    runtime.refresh_index = refresh_index
                    runtime.state.busy = busy(0)
                    runtime.state.display_safe_to_sleep = False
                    yield runtime

    def test_repeated_low_then_high_during_sleep_delay_has_one_budget(self):
        # Every LOW lasts long enough to pass the 500ms guard, but HIGH returns
        # before the final 1s sleep delay finishes. Each individual wait succeeds.
        for runtime in self.runtimes(lambda ms: int(ms % 2000 >= 600)):
            runtime.execute("recover_display_busy")
            runtime.run_until(33000)
            self.assertIsNotNone(runtime.sleep)
            self.assertLessEqual(runtime.sleep[0], 31530)
            self.assertEqual(runtime.state.display_busy_fault_count, 1)
            self.assertEqual(runtime.state.reset_low_count, 1)
            self.assertEqual(runtime.state.reset_high_count, 1)
            self.assertFalse([event for event in runtime.events if event[1] == "component.update"])

    def test_permanent_high_late_low_and_guard_oscillation_terminate(self):
        signals = (lambda ms: 1,
                   lambda ms: int(ms < 29900),
                   lambda ms: int(ms % 600 >= 300))
        for busy in signals:
            for runtime in self.runtimes(busy):
                runtime.execute("recover_display_busy")
                runtime.run_until(33000)
                self.assertIsNotNone(runtime.sleep)
                self.assertLessEqual(runtime.sleep[0], 31530)
                self.assertEqual(runtime.state.display_busy_fault_count, 1)

    def test_terminal_sleep_retains_distinct_battery_and_storage_durations(self):
        for runtime in self.runtimes(lambda ms: 1):
            old = runtime.program.substitutions["low_batt_sleep_duration"]
            runtime.program.substitutions["low_batt_sleep_duration"] = "12h"
            try:
                for battery, storage, duration in ((False, False, 3600000),
                                                    (False, True, 86400000),
                                                    (True, True, 43200000)):
                    trial = DisplayRuntime(runtime.program, lambda ms: 1)
                    trial.state.busy = 1
                    trial.state.display_safe_to_sleep = False
                    trial.state.low_batt_active = battery
                    trial.state.storage_active = storage
                    trial.execute("recover_display_busy")
                    trial.run_until(33000)
                    self.assertIsNotNone(trial.sleep)
                    self.assertEqual(trial.sleep[1], duration)
            finally:
                runtime.program.substitutions["low_batt_sleep_duration"] = old

    def test_new_refresh_cancels_recovery_guard_sleep_and_terminal_work(self):
        # Cancel across wait, recovery guard, final sleep delay, reset pulse and
        # fault notification. A later LOW completes the new settle normally.
        stages = ((100, lambda ms: 1),
                  (250, lambda ms: 0),
                  (2000, lambda ms: int(ms < 1000)),
                  (30000, lambda ms: 1),
                  (30200, lambda ms: 1),
                  (30800, lambda ms: 1))
        for cancel_at, signal in stages:
            for runtime in self.runtimes(signal):
                runtime.execute("recover_display_busy")
                runtime.run_until(cancel_at)
                # A fresh refresh asserts BUSY, then clears within its own wait.
                runtime.busy = lambda ms: int(ms < cancel_at + 1000)
                runtime.state.busy = 1
                runtime.refresh(runtime.refresh_index)
                runtime.run_until(cancel_at + 4000)
                self.assertIsNone(runtime.sleep)
                self.assertTrue(runtime.state.display_safe_to_sleep)
                self.assertFalse(runtime.tasks)
                self.assertEqual(runtime.state.reset_low_count, runtime.state.reset_high_count)

    def test_new_refresh_starts_a_fresh_budget(self):
        for runtime in self.runtimes(lambda ms: 1):
            runtime.execute("recover_display_busy")
            runtime.run_until(1000)
            runtime.busy = lambda ms: int(ms < 2000)
            runtime.refresh(runtime.refresh_index)
            runtime.run_until(4000)
            runtime.busy = lambda ms: 1
            runtime.state.busy = 1
            runtime.state.display_safe_to_sleep = False
            runtime.execute("recover_display_busy")
            runtime.run_until(33000)
            self.assertIsNone(runtime.sleep)
            runtime.run_until(36000)
            self.assertIsNotNone(runtime.sleep)
            self.assertGreaterEqual(runtime.sleep[0], 35010)
            self.assertLessEqual(runtime.sleep[0], 35530)

    def test_successful_recovery_cancels_budget_before_normal_sleep(self):
        for runtime in self.runtimes(lambda ms: int(ms < 1000)):
            runtime.execute("recover_display_busy")
            runtime.run_until(4000)
            self.assertIsNotNone(runtime.sleep)
            self.assertEqual(runtime.state.display_busy_fault_count, 0)
            self.assertNotIn("display_recovery_budget", runtime.tasks)


if __name__ == "__main__":
    unittest.main()
