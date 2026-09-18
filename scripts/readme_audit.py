#!/usr/bin/env python3
"""Check that the READMEs stay in step across languages.

Why this exists: README.md and README.zh.md are two files that have to say the
same things. Nothing enforced that, so they drifted — one said the interface
defaults to English for a day after the other had been changed to Chinese, and a
reader landing on the wrong one got a wrong fact. The same class of bug the
translation dictionary has (see i18n_audit.py), in a file where no test was
looking.

This checks structure, not prose. It cannot tell whether a translation is good;
it can tell whether the two documents have the same shape, which is what makes a
drift visible.

Usage:
    python3 scripts/readme_audit.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = "README.zh.md"
TRANSLATIONS = ["README.md"]

# The number of headings must match exactly; a section added to one language and
# not the other is the drift this is meant to catch.
FAIL_ON_HEADING_MISMATCH = True
# Commands, paths and code blocks are language-independent, so they must be
# identical on both sides — a command that exists in one README and not the
# other is wrong in one of them.
CODE = re.compile(r"```.*?```", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
INTERNAL_LINK = re.compile(r"\]\(#([^)]+)\)")
SCRIPT_REF = re.compile(r"scripts/[a-z_]+\.py")
FILE_REF = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|js|css|sh|yml|json))`")


def headings(text: str) -> list[int]:
    return [len(level) for level, _ in HEADING.findall(text)]


def heading_titles(text: str) -> list[str]:
    """Slugs of every heading, in order.

    Comparing only the heading levels misses a renamed section: swapping
    "Contributing" for "How to contribute" keeps the count and the depth, so the
    audit stays green while the two READMEs now have differently-shaped tables
    of contents. Slugs are compared rather than titles because the titles are in
    different languages by design — what has to match is the order and number of
    real sections, which the slug count per prefix gives us.
    """
    return [slugify(title) for _, title in HEADING.findall(text)]


def slugify(title: str) -> str:
    slug = title.strip().lower()
    slug = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", slug)
    return re.sub(r"\s+", "-", slug)


def anchors(text: str) -> set[str]:
    """GitHub's heading anchor rule, near enough to catch a broken link."""
    return {slugify(title) for _, title in HEADING.findall(text)}


def _level_counts(levels: list[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for level in levels:
        counts[level] = counts.get(level, 0) + 1
    return dict(sorted(counts.items()))


def code_commands(text: str) -> set[str]:
    """The runnable commands in fenced blocks, with comments stripped.

    Two things make this harder than it looks, and both were live bugs:

    1. A block's trailing comment is written in the document's own language
       ("# 起在 localhost:8787" vs "# serves localhost:8787"), so comparing
       blocks verbatim flags every command. Strip the comments.
    2. The directory tree is a fenced block whose every line is annotated in the
       document's language. It must be excluded — and excluding it by "does the
       line contain a slash" also excluded `./run-site.sh`, which emptied the
       whole set. Two empty sets compare equal, so the check passed while
       looking at nothing.

    A tree block is identified by its shape instead: at least three lines, every
    one either `name/  annotation` or an indented continuation. The minimum
    matters — a single-line block such as `./run-site.sh  # comment` has the
    same shape and was being discarded as a tree, which is what emptied the
    command set the first time.
    """
    out = set()
    for block in CODE.findall(text):
        lines = [l for l in block.splitlines() if l.strip() and not l.strip().startswith("```")]
        if not lines:
            continue
        looks_like_tree = (
            len(lines) >= 3
            and all(
                re.match(r"^\s*[^\s#]+/?\s{2,}\S", l) or l.startswith(("  ", "\t"))
                for l in lines
            )
        )
        if looks_like_tree:
            continue
        for line in lines:
            command = line.split("#", 1)[0].strip()
            if not command:
                continue
            # A command starts with a bare word, a path, or a flag.
            if re.match(r"^[a-zA-Z0-9_./~$-]+(\s|$)", command):
                out.add(re.sub(r"\s+", " ", command))
    return out


def main() -> None:
    primary = (ROOT / PRIMARY).read_text(encoding="utf-8")
    problems: list[str] = []
    notes: list[str] = []

    for name in TRANSLATIONS:
        path = ROOT / name
        if not path.is_file():
            problems.append(f"{name}: missing")
            continue
        text = path.read_text(encoding="utf-8")

        # 1. Anchors resolve. A table of contents that points nowhere is the
        #    most visible way a README looks unmaintained.
        known = anchors(text)
        for link in INTERNAL_LINK.findall(text):
            if link not in known:
                problems.append(f"{name}: link #{link} has no matching heading")

        # 2. Same sections, in the same order.
        a, b = headings(primary), headings(text)
        if a != b:
            message = (
                f"{name}: heading structure differs from {PRIMARY} "
                f"({len(a)} vs {len(b)} headings, levels {_level_counts(a)} vs {_level_counts(b)})"
            )
            if FAIL_ON_HEADING_MISMATCH:
                problems.append(message)
            else:
                notes.append(message)

        # 3. The same commands are documented in both languages.
        primary_commands = code_commands(primary)
        these_commands = code_commands(text)
        # A guard against the failure mode this check already had once: if the
        # extractor returns nothing, two empty sets compare equal and the audit
        # reports success while inspecting nothing at all.
        if not primary_commands:
            problems.append(
                f"{PRIMARY}: no commands were extracted — the extractor is broken, "
                "not the document"
            )
        only_primary = primary_commands - these_commands
        only_this = these_commands - primary_commands
        for command in sorted(only_primary):
            problems.append(f"{name}: missing a command present in {PRIMARY}: {command[:70]}")
        for command in sorted(only_this):
            problems.append(f"{name}: has a command not in {PRIMARY}: {command[:70]}")

        # 4. Referenced scripts and files exist.
        for ref in set(SCRIPT_REF.findall(text)):
            if not (ROOT / ref).is_file():
                problems.append(f"{name}: references {ref}, which does not exist")
        for ref in set(FILE_REF.findall(text)):
            if ref.startswith(("http", "www")):
                continue
            if not (ROOT / ref).exists():
                problems.append(f"{name}: references {ref}, which does not exist")

        # 5. The language switcher points at a file that exists.
        for target in re.findall(r"\]\((README(?:\.[a-z]{2})?\.md)\)", text):
            if not (ROOT / target).is_file():
                problems.append(f"{name}: language link to {target}, which does not exist")

    print("README audit")
    print()
    print(f"  languages:  {PRIMARY} + {', '.join(TRANSLATIONS)}")
    print(f"  sections:   {len(headings(primary))} headings")
    print()

    for note in notes:
        print(f"  note  {note}")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for problem in problems:
            print(f"      {problem}")
        sys.exit(1)

    print(f"  {PRIMARY} and {', '.join(TRANSLATIONS)} agree on structure, commands and links")


if __name__ == "__main__":
    main()
