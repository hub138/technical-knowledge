#!/usr/bin/env python3
"""Report which vault pages the editorial inventory still flags, and why.

The inventory in scripts/editorial-inventory.py defines the editorial bar:
a durable page needs at least three headings, a concrete example, a visible
boundary, and a lead of ~180 characters. Running this after a rewrite says
immediately whether the page clears that bar, instead of waiting for the unit
test to fail with a bare assertion.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_inventory():
    spec = importlib.util.spec_from_file_location(
        "editorial_inventory", ROOT / "scripts" / "editorial-inventory.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_inventory()
    rows = module.inventory(ROOT)
    flagged = [r for r in rows if r["durable"] and r["round1"] != "通过"]

    pattern = sys.argv[1] if len(sys.argv) > 1 else None
    if pattern:
        flagged = [r for r in flagged if pattern in r["path"]]

    if not flagged:
        print(f"OK  {len(rows)} pages, none flagged")
        return 0

    print(f"{len(flagged)} of {len(rows)} pages still flagged:")
    for row in flagged:
        print(f"  {row['intro_chars']:>4}字开头  {','.join(row['risks'])}")
        print(f"            {row['path']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
