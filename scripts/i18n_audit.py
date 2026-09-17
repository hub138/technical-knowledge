#!/usr/bin/env python3
"""Report UI strings that have no English translation.

Why this exists: site/i18n.js keys its dictionary on the Chinese source text,
which means no page needs a data-i18n attribute on every element and a missing
entry degrades to "stays Chinese" rather than "renders a key like nav.projects".
The cost of that choice is that editing Chinese copy silently orphans its
translation, and adding a new page adds untranslated strings. Neither shows up
as an error — the page just quietly stays Chinese inside an English interface.

This walks the same files the site serves, extracts the text a reader sees, and
diffs it against the dictionary. It is deliberately mechanical: it cannot judge
whether a translation is *good*, only whether one exists.

Usage:
    python3 scripts/i18n_audit.py            # report
    python3 scripts/i18n_audit.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    "index.html",
    "projects/index.html",
    "site/insights.html",
    "apps/learning/index.html",
    "apps/learning/openmaic.html",
    "apps/learning/intuition.html",
    "apps/learning/transfer.html",
    "apps/learning/history.html",
    "apps/agent-evaluation/index.html",
]

HAN = re.compile(r"[\u4e00-\u9fff]")

# Text inside these never reaches the reader as UI copy.
SKIP_TAGS = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.S | re.I)


def dictionary_keys() -> set[str]:
    """Keys of the DICT object in site/i18n.js.

    Parsed with a regex rather than a JS engine so this runs anywhere; the
    object is a flat map of quoted strings to { en: "..." }, which is regular
    enough to read safely. A malformed entry shows up as a missing key, which
    is the direction that fails loudly.
    """
    source = (ROOT / "site" / "i18n.js").read_text(encoding="utf-8")
    start = source.index("const DICT = {")
    end = source.index("\n  };", start)
    block = source[start:end]
    return set(re.findall(r'^\s*"((?:[^"\\]|\\.)*)":\s*\{', block, re.M))


# Below this length a string is almost always a label, button or heading —
# interface chrome, which is meant to be translated. Above it, it is prose
# explaining an engineering mechanism, which stays in the language it was
# written in. The boundary is a heuristic and is stated so it can be argued
# with; what it must not be is unstated.
CHROME_MAX_LENGTH = 20


def visible_strings(html: str) -> tuple[set[str], set[str]]:
    """Chinese text a reader can see, split into chrome and content.

    Chrome is short: labels, buttons, headings, tooltips. Content is the prose
    that deliberately stays Chinese. Reporting one combined count made the
    number look alarming and said nothing about whether anything was wrong.
    """
    html = SKIP_TAGS.sub("", html)
    chrome: set[str] = set()
    content: set[str] = set()

    def place(text: str) -> None:
        text = text.strip()
        if not text:
            return
        bucket = chrome if len(text) <= CHROME_MAX_LENGTH else content
        bucket.add(text)

    for raw in re.findall(r">([^<>{}]*[\u4e00-\u9fff][^<>{}]*)<", html):
        place(raw)
    # Attribute text is read by people but is never prose, so it is always chrome.
    for attr in ("placeholder", "title", "aria-label", "alt"):
        for value in re.findall(rf'{attr}="([^"]*[\u4e00-\u9fff][^"]*)"', html):
            chrome.add(value.strip())
    return chrome, content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    known = dictionary_keys()
    missing: dict[str, list[str]] = {}
    chrome_total = 0
    content_total = 0

    for page in PAGES:
        path = ROOT / page
        if not path.is_file():
            continue
        chrome, content = visible_strings(path.read_text(encoding="utf-8"))
        chrome_total += len(chrome)
        content_total += len(content)
        untranslated = sorted(s for s in chrome if s not in known)
        if untranslated:
            missing[page] = untranslated

    if args.json:
        print(json.dumps({
            "dictionary_entries": len(known),
            "chrome_strings": chrome_total,
            "content_strings": content_total,
            "untranslated_chrome": sum(len(v) for v in missing.values()),
            "pages_with_missing": {k: len(v) for k, v in missing.items()},
            "missing": missing,
        }, ensure_ascii=False, indent=2))
        return

    worst = sum(len(v) for v in missing.values())
    translated = chrome_total - worst

    print("i18n coverage")
    print()
    print(f"  dictionary entries:  {len(known)}")
    print(f"  interface strings:   {chrome_total}  ({translated} translated)")
    print(f"  knowledge prose:     {content_total}  (stays Chinese by design)")
    print()

    if not missing:
        print("  every interface string has an English translation")
        return

    print(f"  {worst} interface string(s) still have no translation,")
    print(f"  across {len(missing)} page(s):")
    print()
    for page, items in missing.items():
        print(f"  {page}  ({len(items)})")
        for text in items[:12]:
            label = text if len(text) <= 46 else text[:43] + "..."
            print(f"      {label}")
        if len(items) > 12:
            print(f"      ... and {len(items) - 12} more")
        print()

    # Non-zero so this can gate a change; the point is that it cannot be
    # ignored by accident.
    sys.exit(1)


if __name__ == "__main__":
    main()
