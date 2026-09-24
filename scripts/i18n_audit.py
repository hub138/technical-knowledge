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
]

# Shared components that build their own markup after load. They are not pages,
# so walking PAGES missed them entirely: the feedback dialog lives here, and it
# shipped a Chinese panel inside the English interface on every page while this
# audit reported full coverage. Only HTML string literals are read from these,
# which is what the reader ends up seeing.
COMPONENTS = [
    "site/shell.js",
]

HAN = re.compile(r"[\u4e00-\u9fff]")

# Strings that are correct as-is in every language, so a missing dictionary
# entry is the right state rather than a gap. Each one needs a reason here —
# this is not a place to silence findings.
NOT_TRANSLATED = {
    # The language switch names the language it would take you to. In English
    # it must read 中文; translating it to "Chinese" would label the button
    # with the language you are already reading.
    "中文",
}

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


def html_literals(source: str) -> str:
    """Concatenate the HTML a JS component builds in template literals.

    shell.js assembles the sidebar, the feedback dialog and the language switch
    as strings, then injects them. The audit needs to see the same text the
    reader will, so pull out the pieces that look like markup and drop the rest
    — the surrounding code is not UI copy and would only add noise.
    """
    chunks = []
    for literal in re.findall(r"`([^`]*)`", source, re.S):
        if HAN.search(literal) and re.search(r"<[a-zA-Z/]", literal):
            chunks.append(literal)
    for literal in re.findall(r'"([^"\n]*)"', source):
        if HAN.search(literal) and not literal.startswith(("data-", "tk-")):
            chunks.append(literal)
    # 模板字符串里的 ${...} 表达式体不是读者看到的文案（英文态内联拼装的
    # 三元分支里，中文分支已有引号串单独被抓到），剔除表达式体避免把
    # JS 代码本身当词条。
    chunks = [re.sub(r"\$\{[^}]*\}", " ", c) for c in chunks]
    return "\n".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    known = dictionary_keys()
    missing: dict[str, list[str]] = {}
    chrome_total = 0
    content_total = 0

    sources = [(rel, rel) for rel in PAGES]
    # Components carry their own name in the report so a finding points at the
    # file that has to change, not at the pages that happen to render it.
    sources += [(rel, rel + " (shared component)") for rel in COMPONENTS]

    for rel, label in sources:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if rel in COMPONENTS:
            text = html_literals(text)
        chrome, content = visible_strings(text)
        chrome_total += len(chrome)
        content_total += len(content)
        untranslated = sorted(
            s for s in chrome if s not in known and s not in NOT_TRANSLATED
        )
        if untranslated:
            missing[label] = untranslated

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
