"""Guard the generic package against an omitted OTA credential."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "examples/multi-device/packages/smart_plant_core.yaml").read_text()


class OtaPasswordContractTest(unittest.TestCase):
    def test_core_contains_compile_time_guard(self):
        self.assertIn('const char *value = "${ota_password}";', CORE)
        self.assertIn('static_assert(ota_password_is_set()', CORE)
        self.assertIn('priority: 800', CORE)

    def test_guard_accepts_explicit_nonempty_and_rejects_empty_or_unresolved(self):
        source = r'''
#include <string>
constexpr bool ota_password_is_set(const char *value) {
  const char *unset = "$" "{ota_password}";
  if (value[0] == '\0') return false;
  unsigned i = 0;
  while (value[i] && value[i] == unset[i]) ++i;
  return value[i] != unset[i];
}
static_assert(ota_password_is_set("synthetic-ota"));
static_assert(!ota_password_is_set(""));
static_assert(!ota_password_is_set("${ota_password}"));
int main() { return 0; }
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "guard.cpp"
            binary = Path(directory) / "guard"
            cpp.write_text(source)
            result = subprocess.run(
                ["g++", "-std=c++17", str(cpp), "-o", str(binary)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
