# Recovered KiCad symbol library

The KiCad schematics reference `Smart_Plant-eagle-import`. Their symbol table
points to a local library that was missing. The restored library contains the
28 symbols embedded in the two checked-in schematic caches.

Run `python3 scripts/recover_kicad_symbol_library.py --check` to compare the
library with both caches and check reference coverage. Run the script without
`--check` to regenerate the library deterministically. It rejects conflicting
cache definitions and unresolved references. Only the outer namespace and
indentation change; body tokens, pin definitions and geometry are preserved.

Run `python3 -m unittest discover -s tests -p test_kicad_symbol_library.py -v`
for source equality, parser boundaries, conflicting cache and missing-reference
checks. The library uses the KiCad10 symbol format version `20251024`, matching
the source schematics. No schematic, PCB or manufacturing output is changed.

These checks prove source recovery. They do not prove loading or ERC with
KiCad10. That application was unavailable during recovery; the installed KiCad9
cannot validate this newer format. No fabrication or electrical validation is
claimed. Revert the isolated library contribution to undo this source change.
