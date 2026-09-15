#!/usr/bin/env python3
"""Second-pass review for duplication, metadata dates, and editorial drift.

This is deliberately narrower than the causal-contract audit. It reports facts
that can be checked without pretending that a script can judge prose quality:
duplicate titles/sections/paragraphs, malformed dates, overdue review windows,
and sources that are not URLs or Obsidian links.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


CORE_TYPES = {
    "concept", "guide", "playbook", "principle", "decision", "design",
    "architecture", "evolution",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^(?:https?://|\[\[).+")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    data: dict[str, Any] = {}
    active: str | None = None
    for line in text[4:marker].splitlines():
        item = re.match(r"^\s+-\s+(.+)$", line)
        if item and active:
            data.setdefault(active, [])
            if isinstance(data[active], list):
                data[active].append(item.group(1).strip().strip('"\''))
            continue
        pair = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not pair:
            continue
        key, value = pair.groups()
        active = None
        if not value:
            data[key] = []
            active = key
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [x.strip().strip('"\'') for x in value[1:-1].split(",") if x.strip()]
        else:
            data[key] = value.strip().strip('"\'')
    return data, text[marker + 5 :]


def body_parts(body: str) -> tuple[list[str], list[str]]:
    headings: list[str] = []
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in body.splitlines() + [""]:
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("## "):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            headings.append(stripped[3:].strip())
        elif stripped.startswith("# "):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        elif not stripped or stripped.startswith(("|", "- ", "* ", ">")):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(re.sub(r"\s+", " ", stripped))
    return headings, [p.strip() for p in paragraphs if p.strip()]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def review(root: Path, as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    pages = sorted((root / "vault" / "工程知识").rglob("*.md"))
    title_locations: defaultdict[str, list[str]] = defaultdict(list)
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for path in pages:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        if str(frontmatter.get("type", "")) not in CORE_TYPES:
            continue
        relative = path.relative_to(root / "vault").as_posix()
        title = str(frontmatter.get("title", path.stem)).strip()
        title_locations[normalize(title)].append(relative)
        headings, paragraphs = body_parts(body)

        duplicate_headings = [name for name, count in Counter(map(normalize, headings)).items() if count > 1]
        duplicate_paragraphs = [sample for sample, count in Counter(map(normalize, paragraphs)).items() if count > 1 and len(sample) >= 80]
        if duplicate_headings:
            findings.append({"path": relative, "kind": "duplicate_heading", "items": duplicate_headings})
        if duplicate_paragraphs:
            findings.append({"path": relative, "kind": "duplicate_paragraph", "items": duplicate_paragraphs})

        for key in ("updated", "review_after"):
            value = str(frontmatter.get(key, ""))
            if not DATE_RE.fullmatch(value):
                findings.append({"path": relative, "kind": "invalid_date", "field": key, "value": value})
            elif key == "review_after" and date.fromisoformat(value) <= as_of:
                warnings.append({"path": relative, "kind": "review_due", "review_after": value})

        sources = frontmatter.get("sources", [])
        if not isinstance(sources, list) or any(not URL_RE.match(str(source).strip()) for source in sources):
            findings.append({"path": relative, "kind": "invalid_source", "sources": sources})

    for title, locations in title_locations.items():
        if len(locations) > 1:
            findings.append({"kind": "duplicate_title", "title": title, "paths": locations})

    return {
        "as_of": as_of.isoformat(),
        "pages_scanned": len(pages),
        "durable_pages": sum(1 for path in pages if str(parse_frontmatter(path.read_text(encoding="utf-8"))[0].get("type", "")) in CORE_TYPES),
        "findings": findings,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = review(args.root.resolve(), args.as_of)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"second-pass review: {result['pages_scanned']} pages scanned ({result['durable_pages']} durable)")
        for finding in result["findings"]:
            print(f"finding: {finding}")
        if result["warnings"]:
            print(f"review windows due: {len(result['warnings'])}")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
