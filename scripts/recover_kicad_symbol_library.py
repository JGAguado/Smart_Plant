#!/usr/bin/env python3
"""Recover the local symbol library from the two authoritative schematic caches.

Run with --check to verify the committed library without writing it. This checks
source equality and reference coverage, not KiCad loading, ERC or fabrication.
Only the outer symbol's library namespace and indentation change.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = "Smart_Plant-eagle-import"
OUTPUT = ROOT / "Design" / f"{LIBRARY}.kicad_sym"
SCHEMATICS = tuple(sorted((ROOT / "Design").glob("*.kicad_sch")))
# KiCad 10.0 eeschema/sch_file_versions.h, blob
# 2ad78c104d6dee673359ab0f7b7c91b2944e3f50: SEXPR_SYMBOL_LIB_FILE_VERSION.
# https://github.com/KiCad/kicad-source-mirror/blob/10.0/eeschema/sch_file_versions.h
LIBRARY_VERSION = "20251024"
TOKEN = re.compile(r'\s+|"(?:\\.|[^"\\])*"|[()]|[^()\s"]+')


def tokens(source: str) -> list[tuple[str, int, int]]:
    result = []
    offset = 0
    while offset < len(source):
        match = TOKEN.match(source, offset)
        if match is None:
            raise ValueError(f"invalid token at offset {offset}")
        value = match.group()
        if not value.isspace():
            result.append((value, offset, match.end()))
        offset = match.end()
    return result


def forms(source: str) -> list[tuple[int, int, int, str]]:
    """Return balanced forms as (start, end, depth, head), including nested ones."""
    stream = tokens(source)
    stack = []
    result = []
    for index, (value, start, end) in enumerate(stream):
        if value == "(":
            if index + 1 == len(stream) or stream[index + 1][0] in ("(", ")"):
                raise ValueError("missing form head")
            stack.append((start, len(stack), stream[index + 1][0]))
        elif value == ")":
            if not stack:
                raise ValueError("unmatched closing parenthesis")
            begin, depth, head = stack.pop()
            result.append((begin, end, depth, head))
        elif not stack:
            raise ValueError("token outside a form")
    if stack:
        raise ValueError("unclosed form")
    return sorted(result)


def token_values(source: str) -> list[str]:
    return [value for value, _, _ in tokens(source)]


def recover(schematics: tuple[Path, ...]) -> dict[str, str]:
    if not schematics:
        raise ValueError("no source schematics")
    symbols: dict[str, str] = {}
    references = set()
    for path in schematics:
        source = path.read_text(encoding="utf-8")
        parsed = forms(source)
        caches = [(a, b) for a, b, depth, head in parsed if depth == 1 and head == "lib_symbols"]
        if len(caches) != 1:
            raise ValueError(f"{path}: expected one lib_symbols cache")
        cache_start, cache_end = caches[0]
        for start, end, depth, head in parsed:
            if head == "lib_id":
                references.add(token_values(source[start:end])[2].strip('"'))
            if not (depth == 2 and head == "symbol" and cache_start < start < cache_end):
                continue
            block = source[start:end]
            stream = tokens(block)
            qualified = stream[2][0]
            prefix = f'"{LIBRARY}:'
            if not qualified.startswith(prefix):
                raise ValueError(f"{path}: unexpected library {qualified}")
            name = qualified[len(prefix):-1]
            # Keep every body token and all string escapes exactly as exported.
            local = block[:stream[2][1]] + f'"{name}"' + block[stream[2][2]:]
            # Cache symbols sit one indentation level deeper than library symbols.
            local = "\n".join(line[1:] if line.startswith("\t") else line for line in local.split("\n"))
            if name in symbols and token_values(symbols[name]) != token_values(local):
                raise ValueError(f"{path}: conflicting cached symbol {name}")
            symbols.setdefault(name, local)
    missing = references - {f"{LIBRARY}:{name}" for name in symbols}
    if missing:
        raise ValueError(f"unresolved symbol references: {sorted(missing)}")
    return symbols


def render(schematics: tuple[Path, ...] = SCHEMATICS) -> str:
    symbols = recover(schematics)
    body = "\n".join("\t" + symbols[name] for name in sorted(symbols))
    return (
        f"(kicad_symbol_lib\n\t(version {LIBRARY_VERSION})\n"
        '\t(generator "recover_kicad_symbol_library")\n'
        '\t(generator_version "1.0")\n'
        + body + "\n)\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != expected.encode("utf-8"):
            parser.exit(1, "symbol library is missing or differs from schematic caches\n")
    else:
        OUTPUT.write_bytes(expected.encode("utf-8"))
    print(f"{len(recover(SCHEMATICS))} symbols; all schematic lib_id references resolved")


if __name__ == "__main__":
    main()
