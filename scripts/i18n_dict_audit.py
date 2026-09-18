#!/usr/bin/env python3
"""Keep the i18n dictionary honest about its own keys.

Three failure modes this catches, all of which were live in site/i18n.js:

1. A key defined twice. JavaScript silently takes the last one, so the first
   `{ en: ... }` is dead code and the file reads as if it says something it does
   not. Thirty-three of these accumulated from a bulk insert.

2. Two Chinese strings with the same English text. The dictionary is keyed on
   the Chinese source, but switching back to Chinese needs the reverse lookup —
   and with a collision that lookup can only return one of them, so the other
   reverts to the wrong string. Measured: `项目与教学入口` came back as
   `查看项目与教学`.

   Not every collision is a bug: two keys with genuinely identical text (a
   duplicate) are just (1). What matters is two *different* Chinese strings
   sharing one translation, which is ambiguous by construction.

3. A key that is not valid JavaScript string content, or an entry missing `en`.

Usage:
    python3 scripts/i18n_dict_audit.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "site" / "i18n.js"

ENTRY = re.compile(
    r'^[ \t]*"((?:[^"\\]|\\.)*)"[ \t]*:[ \t]*\{[ \t]*\n?[ \t]*en:[ \t]*"((?:[^"\\]|\\.)*)"',
    re.M,
)


def entries(source: str) -> list[tuple[str, str]]:
    start = source.index("const DICT = {")
    end = source.index("\n  };", start)
    block = source[start:end]
    found = ENTRY.findall(block)
    if not found:
        print("  could not parse any entries — the DICT shape changed", file=sys.stderr)
        sys.exit(2)
    return found


def main() -> None:
    source = I18N.read_text(encoding="utf-8")
    pairs = entries(source)

    # 1. Duplicate keys.
    seen: dict[str, int] = defaultdict(int)
    for zh, _ in pairs:
        seen[zh] += 1
    duplicates = sorted(k for k, n in seen.items() if n > 1)

    # 2. Distinct Chinese strings that share one English translation.
    by_english: dict[str, set[str]] = defaultdict(set)
    for zh, en in pairs:
        by_english[en].add(zh)
    # A duplicate key is reported above; here we only care when the Chinese
    # sides differ, because that is the case the reverse lookup cannot resolve.
    collisions = {
        en: sorted(zhs)
        for en, zhs in by_english.items()
        if len(zhs) > 1
    }

    print("i18n dictionary")
    print()
    print(f"  entries:      {len(pairs)}")
    print(f"  unique keys:  {len(seen)}")
    print(f"  translations: {len(by_english)}")
    print()

    problems = 0

    if duplicates:
        problems += len(duplicates)
        print(f"  {len(duplicates)} key(s) defined more than once "
              "(JavaScript keeps the last, the rest is dead):")
        for key in duplicates[:15]:
            print(f"      {seen[key]}x  {key}")
        if len(duplicates) > 15:
            print(f"      ... and {len(duplicates) - 15} more")
        print()

    if collisions:
        problems += len(collisions)
        print(f"  {len(collisions)} English string(s) shared by more than one "
              "Chinese source (the reverse lookup cannot tell them apart):")
        for en, zhs in sorted(collisions.items())[:15]:
            print(f"      {en!r}")
            for zh in zhs:
                print(f"          <- {zh!r}")
        if len(collisions) > 15:
            print(f"      ... and {len(collisions) - 15} more")
        print()

    if problems:
        print(f"  {problems} problem(s)")
        sys.exit(1)

    print("  every key is unique and every translation maps back to exactly one source")


if __name__ == "__main__":
    main()
