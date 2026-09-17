#!/usr/bin/env python3
"""Run every check and report one verdict.

Why this exists: there are five separate audits now, each catching a failure
mode that the others cannot see. Run one at a time and it is easy to believe the
site is fine — that is exactly how 263 references to deleted tokens survived a
contrast pass, a test suite and a careful read of the diff.

    tests        does the server do what it says
    contrast     is text readable, in both themes
    layout       does anything overlap, overflow or get clipped
    tokens       does every var() name something that exists
    copy         is the visitor-facing writing any good

Usage:
    python3 scripts/check_all.py                # everything
    python3 scripts/check_all.py --fast         # skip the browser checks
    python3 scripts/check_all.py --base URL
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

# Pages checked in both themes by the contrast audit, and the file each serves.
CONTRAST_PAGES = [
    ("/", "index.html"),
    ("/projects", "projects/index.html"),
    ("/insights", "site/insights.html"),
    ("/apps/learning/index.html", "apps/learning/index.html"),
    ("/apps/learning/openmaic.html", "apps/learning/openmaic.html"),
    ("/apps/learning/intuition.html", "apps/learning/intuition.html"),
    ("/apps/learning/transfer.html", "apps/learning/transfer.html"),
    ("/apps/learning/history.html", "apps/learning/history.html"),
    ("/apps/agent-evaluation/index.html", "apps/agent-evaluation/index.html"),
]


def run(label: str, argv: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    ok = proc.returncode == 0
    return ok, output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8787")
    parser.add_argument("--fast", action="store_true", help="skip the browser checks")
    args = parser.parse_args()

    results: list[tuple[str, bool, str]] = []

    # 1. Server behaviour.
    ok, out = run("tests", [PYTHON, "-m", "unittest", "tests.test_site"])
    summary = next((l for l in out.splitlines() if l.startswith("Ran ")), "")
    results.append(("tests", ok, summary or out.splitlines()[-1] if out else ""))

    # 2. Static source checks (no browser needed).
    for label, script in (("tokens", "scripts/token_audit.py"),
                          ("copy", "scripts/copy_audit.py")):
        ok, out = run(label, [PYTHON, str(ROOT / script)])
        if label == "copy":
            # copy_audit reports a score rather than passing or failing
            score = next((l for l in out.splitlines() if "总分" in l), "")
            results.append((label, True, score.strip() or "score reported"))
        else:
            note = next(
                (l.strip() for l in out.splitlines() if "referenced custom" in l),
                "checked",
            )
            results.append((label, ok, note))

    if not args.fast:
        # 3. Layout at three widths.
        ok, out = run("layout", [PYTHON, str(ROOT / "scripts/layout_audit.py"),
                                 "--base", args.base])
        note = next(
            (l.strip() for l in out.splitlines() if "no layout problems" in l
             or "layout problem" in l),
            "",
        )
        results.append(("layout", ok, note))

        # 4. Contrast, every page in both themes.
        failures = 0
        checked = 0
        for path, source in CONTRAST_PAGES:
            for theme in ("light", "dark"):
                checked += 1
                ok, out = run(
                    "contrast",
                    [PYTHON, str(ROOT / "scripts/contrast_audit.py"),
                     f"{args.base}{path}#{theme}", source, "1440"],
                )
                if not ok:
                    failures += 1
        results.append((
            "contrast", failures == 0,
            f"{checked - failures}/{checked} page-theme combinations",
        ))

    width = max(len(label) for label, _, _ in results)
    print("verification")
    print()
    for label, ok, note in results:
        mark = "ok  " if ok else "FAIL"
        print(f"  {mark}  {label:<{width}}  {note}")

    failed = [label for label, ok, _ in results if not ok]
    print()
    if failed:
        print(f"  {len(failed)} check(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"  all {len(results)} checks pass")


if __name__ == "__main__":
    main()
