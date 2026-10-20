"""Verify recovered library content without claiming KiCad 10 validation."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/recover_kicad_symbol_library.py"
SPEC = importlib.util.spec_from_file_location("recover_kicad_symbol_library", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecoveredSymbolLibraryTests(unittest.TestCase):
    def test_committed_library_matches_both_caches(self) -> None:
        self.assertEqual(MODULE.OUTPUT.read_bytes(), MODULE.render().encode("utf-8"))
        self.assertEqual(len(MODULE.recover(MODULE.SCHEMATICS)), 28)

    def test_all_body_tokens_match_original_symbols(self) -> None:
        symbols = MODULE.recover(MODULE.SCHEMATICS)
        for path in MODULE.SCHEMATICS:
            source = path.read_text(encoding="utf-8")
            for start, end, depth, head in MODULE.forms(source):
                if depth == 2 and head == "symbol":
                    original = MODULE.token_values(source[start:end])
                    name = original[2].removeprefix(f'"{MODULE.LIBRARY}:')[:-1]
                    recovered = MODULE.token_values(symbols[name])
                    original[2] = f'"{name}"'
                    self.assertEqual(original, recovered, (path.name, name))

    def test_quotes_escapes_and_parentheses_remain_opaque(self) -> None:
        source = r'(symbol "a" (property "Value" "escaped \" quote (and parens)"))'
        parsed = MODULE.forms(source)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(source[parsed[0][0]:parsed[0][1]], source)
        for invalid in ('(symbol "unterminated)', '(symbol "a"', '(symbol "a"))'):
            with self.subTest(source=invalid), self.assertRaises(ValueError):
                MODULE.forms(invalid)

    def test_conflicting_caches_and_missing_references_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = tuple(Path(directory) / name for name in ("one.kicad_sch", "two.kicad_sch"))
            prefix = f'{MODULE.LIBRARY}:'
            paths[0].write_text(f'(kicad_sch (lib_symbols (symbol "{prefix}a" (pin 1))))')
            paths[1].write_text(f'(kicad_sch (lib_symbols (symbol "{prefix}a" (pin 2))))')
            with self.assertRaisesRegex(ValueError, "conflicting cached symbol"):
                MODULE.recover(paths)
            paths[1].write_text(f'(kicad_sch (lib_symbols) (symbol (lib_id "{prefix}missing")))')
            with self.assertRaisesRegex(ValueError, "unresolved symbol references"):
                MODULE.recover(paths)


if __name__ == "__main__":
    unittest.main()
