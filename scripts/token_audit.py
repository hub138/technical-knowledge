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
    "papers/index.html",
    "papers/paper.html",
    "sources/index.html",
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

# Element-local custom properties: set inline on one element from JS (or in a
# style attribute) and read by a rule that targets it. They are deliberately not
# global tokens — the value differs per element — so they cannot be declared in
# tokens.css and must be listed here instead.
#
# Adding a name here is a claim that some element sets it. If that stops being
# true the var() resolves to nothing and the rule silently drops, so treat this
# list as something to prune, not a place to silence findings.
LOCAL = {
    "--dot",  # index.html renderAtlas: topic circle diameter, from note count
    "--ink",  # index.html renderAtlas: the domain's accent colour
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Defined per theme, because a token that exists only in the dark block
    # leaves the light theme silently broken — and the union of the two looks
    # complete, which is how a check like this gives a false pass. Colours are
    # the tokens that must be declared in both.
    tokens_css = (ROOT / "site" / "tokens.css").read_text(encoding="utf-8")
    dark_at = tokens_css.find(':root[data-theme="dark"]')
    light_block = tokens_css[:dark_at] if dark_at > 0 else tokens_css
    dark_block = tokens_css[dark_at:] if dark_at > 0 else ""

    defined_light = set(DEFINE.findall(light_block))
    defined_dark = set(DEFINE.findall(dark_block))
    # base.css carries structural tokens (spacing, type) that are theme-neutral.
    base_css = (ROOT / "site" / "base.css").read_text(encoding="utf-8")
    defined_shared = set(DEFINE.findall(base_css))

    defined = defined_light | defined_dark | defined_shared

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
        if name not in defined and name not in BUILT_IN and name not in LOCAL
    }

    # Colour tokens must be declared in both themes. Structural ones (spacing,
    # type scale, z-index) live in one place and are excluded.
    colour_tokens = {n for n in used if n.startswith("--color-")}
    one_sided = {
        name: ("light" if name in defined_light else "dark")
        for name in sorted(colour_tokens)
        if name not in defined_light or name not in defined_dark
    }

    # A token defined but never referenced is dead weight rather than a bug, so
    # it is reported separately and does not fail the run.
    unused = sorted(n for n in defined if n not in used and n not in BUILT_IN)

    if args.json:
        print(json.dumps({
            "defined": len(defined),
            "referenced": len(used),
            "undefined": missing,
            "one_sided": one_sided,
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

    if one_sided:
        print(f"  {len(one_sided)} colour token(s) declared in only one theme:")
        print()
        for name, where in one_sided.items():
            print(f"    {name}  (only in {where})")
        print()
        print("  A colour defined for one theme leaves the other rendering with a")
        print("  dropped declaration, which no error surfaces.")
        sys.exit(1)

    print("  every referenced custom property is defined, in both themes")
    if unused:
        print()
        print(f"  {len(unused)} defined but never referenced (not a failure):")
        for name in unused[:20]:
            print(f"    {name}")


if __name__ == "__main__":
    main()
