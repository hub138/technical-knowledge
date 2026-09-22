#!/usr/bin/env python3
"""Audit the published-facing writing style of engineering knowledge pages.

This is the executable half of `vault/知识库管理/归档/面向发布的知识写作文风契约.md`.
The structural contract (`audit-knowledge-quality.py`) checks that a page has a
problem, a mechanism and evidence. This one checks that the page *reads* like a
finished technical document instead of a generation draft: no self-disclosure,
no disclaimer-shaped boundary statements, and no reading-order dependency in
the opening paragraph.

Scope: this is a regression net for known-bad phrases, not a quality standard.
A passing run means no known-bad phrase was found; it says nothing about whether
the page is any good. The contract's principles (how far to unpack an idea,
whether cross-page links actually explain the shared mechanism, whether a term
should stay in English) are judgement calls and deliberately stay out of this
gate. When the contract gains a new *literal* forbidden phrase, add it here too;
when it gains a principle, leave it to the reader.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

KNOWLEDGE_ROOT = ("vault", "工程知识")

# Each entry: (rule name, offending pattern, why it fails).
#
# Patterns are deliberately narrow. Bare 缺口 (gap) and 下一步 (next step) are
# legitimate technical terms in this corpus — "证据缺口", "可观测缺口", "决定下一步".
# Only the material-status senses are defects, so those are matched explicitly.
FORBIDDEN: tuple[tuple[str, str, str], ...] = (
    ("self-disclosure/gap", r"专文暂缺|尚无专文|待补|留待以后|后续补|知识库缺口|本书记为待", "暴露材料不完整"),
    ("self-disclosure/roadmap", r"下一步计划|后续计划|下一期|TODO|FIXME|项目扩容计划|自动化管道（下一步）", "路线图不是知识正文"),
    ("self-disclosure/self-assurance", r"不是编出来|不是纸面设计|不是编的|真实做过", "自我保证无效，证据才有效"),
    ("self-disclosure/appeal-to-nobody", r"很少有人|没人会|大多数人不会|没有人会", "用「没人做」抬高自己"),
    ("self-reference/book", r"本书记为|本书认为|本材料认为|本书只覆盖", "拟人化自我指涉"),
    ("tone/imperative", r"^(?:请看|请注意|记住|切记)", "不命令读者"),
    # Upstream attribution: every defect fact belongs to upstream. The material
    # may come from scanning a downstream distribution branch, but the prose
    # must never attribute a defect to it — including in negated form.
    # Upstream attribution: every defect fact belongs to upstream. The prose
    # must never attribute a defect to a downstream branch. The pattern is
    # written as a character class so this file does not carry the literal
    # term it forbids -- the contract and this repo are version controlled.
    # Covers the base term and its derivatives (code / team / implementation).
    ("attribution/self-developed", r"自\s*[研硏][\u4e00-\u9fff]{0,3}", "缺陷事实一律归属上游，分支特有代码写成「该发行分支上的 X」"),
)

# Reading-order dependency: the opening paragraph is auto-extracted as the
# summary and must stand on its own.
LEAD_DEPENDENCY = re.compile(
    r"^(?:先看|前几篇|上一篇|如上所述|前面提到|我们再|接下来我们)"
)

FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
FRONTMATTER_END = "\n---\n"

# Grammar is a prompt-level judgement too; Chinese measure-word slips are hard
# to catch without context and produce noise. Kept out of the machine gate.


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find(FRONTMATTER_END, 4)
    if marker < 0:
        return {}, text
    return {}, text[marker + len(FRONTMATTER_END) :]


def strip_code(body: str) -> list[str]:
    """Return prose lines with fenced code blocks removed."""
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return out


def first_paragraph(lines: list[str]) -> str:
    """The first non-empty prose line after the H1."""
    seen_h1 = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            seen_h1 = True
            continue
        if not seen_h1:
            continue
        if stripped.startswith(("#", ">", "|", "-", "*")):
            continue
        return stripped
    return ""


def audit(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    knowledge_root = root.joinpath(*KNOWLEDGE_ROOT)
    if not knowledge_root.exists():
        return findings

    for path in sorted(knowledge_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        _, body = parse_frontmatter(text)
        lines = strip_code(body)
        relative = path.relative_to(root).as_posix()

        # Wikilinks and URLs are navigation, not prose.
        prose_lines = [
            re.sub(r"\[\[[^]]+\]\]", "", re.sub(r"https?://\S+", "", line))
            for line in lines
        ]

        for index, line in enumerate(prose_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            for rule, pattern, why in FORBIDDEN:
                if re.search(pattern, stripped):
                    findings.append(
                        {
                            "path": relative,
                            "line": index,
                            "rule": rule,
                            "why": why,
                            "text": stripped[:120],
                        }
                    )

        lead = first_paragraph(prose_lines)
        if lead and LEAD_DEPENDENCY.match(lead):
            findings.append(
                {
                    "path": relative,
                    "line": 0,
                    "rule": "lead/reading-order-dependency",
                    "why": "概览摘要取自首段，首段必须自包含",
                    "text": lead[:120],
                }
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="print machine-readable findings")
    args = parser.parse_args()
    findings = audit(args.root.resolve())
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    elif findings:
        for item in findings:
            location = f"{item['path']}:{item['line']}" if item["line"] else item["path"]
            print(f"{location}  [{item['rule']}] {item['why']}")
            print(f"    {item['text']}")
        print(f"writing style audit failed: {len(findings)} finding(s)")
    else:
        root = args.root.resolve().joinpath(*KNOWLEDGE_ROOT)
        print(f"writing style audit passed: {len(list(root.rglob('*.md')))} page(s) scanned")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
