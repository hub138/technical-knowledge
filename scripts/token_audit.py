#!/usr/bin/env python3
"""Find CSS custom properties that are used but never defined.

Why this exists: an unresolved var() fails silently. The declaration is dropped
and the property falls back to inherited or initial, so the page renders — just
not as intended. A colour goes transparent, a radius becomes square, a duration
becomes zero. Nothing errors, nothing logs, and the contrast audit usually still
passes because the fallback inherits a readable colour.

That is exactly what happened here. A legacy alias block at the foot of
tokens.css mapped short names (--accent, --panel, --line) onto the real tokens.
Its comment said to delete it once nothing referenced those names any more, and
the check at the time only looked in site/ — so 460 references across the pages
kept pointing at tokens that no longer existed. The reader toolbar lost its
background and border and nobody noticed, because a transparent button on a
white page still looks like a button.

Usage:
    python3 scripts/token_audit.py            # report
    python3 scripts/token_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every file that can reference a custom property.
SOURCES = [
    "index.html",
    "projects/index.html",
    "site/insights.html",
    "apps/learning/index.html",
    "apps/learning/openmaic.html",
    "apps/learning/intuition.html",
    "apps/learning/transfer.html",
    "apps/learning/history.html",
    "apps/agent-evaluation/index.html",
    "site/base.css",
    "site/tokens.css",
    "site/shell.js",
    "site/nav.js",
    "site/i18n.js",
]

DEFINE = re.compile(r"^\s*(--[a-zA-Z0-9-]+)\s*:", re.M)
USE = re.compile(r"var\(\s*(--[a-zA-Z0-9-]+)")

# Properties a browser always provides, which are therefore legitimately
# referenced without being declared here.
BUILT_IN = {
    "--sidebar-width",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    tokens_file = ROOT / "site" / "tokens.css"
    defined: set[str] = set()
    for rel in ("site/tokens.css", "site/base.css"):
        path = ROOT / rel
        if path.is_file():
            defined |= set(DEFINE.findall(path.read_text(encoding="utf-8")))

    used: dict[str, list[str]] = {}
    for rel in SOURCES:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for name in USE.findall(text):
            used.setdefault(name, []).append(rel)

    missing = {
        name: sorted(set(files))
        for name, files in used.items()
        if name not in defined and name not in BUILT_IN
    }

    # A token defined but never referenced is dead weight rather than a bug, so
    # it is reported separately and does not fail the run.
    unused = sorted(n for n in defined if n not in used and n not in BUILT_IN)

    if args.json:
        print(json.dumps({
            "defined": len(defined),
            "referenced": len(used),
            "undefined": missing,
            "unused": unused,
        }, ensure_ascii=False, indent=2))
        return

    print("token audit")
    print()
    print(f"  defined:    {len(defined)}")
    print(f"  referenced: {len(used)}")
    print()

    if missing:
        print(f"  {len(missing)} custom property/properties are used but never defined:")
        print()
        for name, files in sorted(missing.items()):
            print(f"    {name}")
            for f in files:
                print(f"        referenced in {f}")
        print()
        print("  An unresolved var() is dropped silently, so these render as")
        print("  transparent / initial rather than failing loudly.")
        sys.exit(1)

    print("  every referenced custom property is defined")
    if unused:
        print()
        print(f"  {len(unused)} defined but never referenced (not a failure):")
        for name in unused[:20]:
            print(f"    {name}")


if __name__ == "__main__":
    main()
