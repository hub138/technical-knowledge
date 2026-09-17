#!/usr/bin/env python3
"""Score the site's visitor-facing copy against a fixed rubric.

Why this exists: copy quality was being judged by vibes, which meant changes
were as likely to be lateral as forward. This turns the question into numbers
that can be compared across runs, so "is this better?" has an answer that does
not depend on who is looking.

The rubric is deliberately mechanical. It can only catch the failure modes
that are expressible as rules — filler, abstraction, unearned claims,
inconsistency. Judgement about whether a page is *interesting* stays with the
reader; this is the floor, not the ceiling.

Usage:
    python3 scripts/copy_audit.py            # score, print report
    python3 scripts/copy_audit.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Words that add length without adding meaning. Kept as data rather than
# hardcoded in a regex so the list can be argued with and extended.
FILLER = (
    "围绕", "针对", "基于", "通过", "结合", "赋能", "助力", "打造",
    "致力于", "旨在", "全方位", "多维度", "深层次", "进一步",
)

# Nouns that sound technical but name nothing a reader can picture.
ABSTRACT = (
    "心智模型", "事实边界", "内容分类", "归位", "沉淀", "闭环",
    "抓手", "范式", "赋能", "生态位",
)

# Claims that need a receipt to be worth anything.
UNEARNED = ("最好", "最强", "第一", "领先", "无敌", "完美", "极致")

# Second person is how you address a reader; third-person self-description
# ("本知识库…") is how you write a manual.
SELF_REFERENTIAL = ("本知识库", "本站", "本页面", "该系统", "本仓库")


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    return text


def visible_lines(html: str) -> list[str]:
    """Lines of prose a reader would actually encounter."""
    out = []
    for raw in strip_html(html).split("\n"):
        line = raw.strip()
        # Skip chrome: single glyphs, control hints, bare numbers.
        if len(line) < 6:
            continue
        if re.fullmatch(r"[\d\s/%.·—\-]+", line):
            continue
        if line in {"Enter", "Esc"}:
            continue
        out.append(line)
    return out


def score(lines: list[str]) -> dict[str, object]:
    joined = "\n".join(lines)
    findings: list[dict[str, str]] = []

    for word in FILLER:
        for line in lines:
            if word in line and len(line) > 18:
                findings.append({"rule": "filler", "word": word, "line": line[:70]})

    for word in ABSTRACT:
        for line in lines:
            if word in line:
                findings.append({"rule": "abstract-noun", "word": word, "line": line[:70]})

    for word in UNEARNED:
        for line in lines:
            if word in line:
                findings.append({"rule": "unearned-claim", "word": word, "line": line[:70]})

    for word in SELF_REFERENTIAL:
        for line in lines:
            if word in line:
                findings.append({"rule": "self-referential", "word": word, "line": line[:70]})

    # Every number a reader sees should be traceable. Count digits appearing
    # outside of the interactive chrome.
    numbers = re.findall(r"\d+(?:\.\d+)?", joined)
    return {
        "lines": len(lines),
        "chars": len(joined),
        "numbers": len(numbers),
        "findings": findings,
        "by_rule": {
            rule: sum(1 for f in findings if f["rule"] == rule)
            for rule in ("filler", "abstract-noun", "unearned-claim", "self-referential")
        },
    }


PAGES = {
    "首页": ROOT / "index.html",
    "项目与教学": ROOT / "projects" / "index.html",
    "中台": ROOT / "site" / "insights.html",
    "学习中心": ROOT / "apps" / "learning" / "index.html",
    "课堂历史": ROOT / "apps" / "learning" / "history.html",
    "Agent 评估": ROOT / "apps" / "agent-evaluation" / "index.html",
}

# Copy embedded in JS template strings is not in the served HTML, so read the
# source files for those pages instead of fetching them.
SOURCES = {
    "首页": ROOT / "index.html",
    "中台": ROOT / "site" / "insights.html",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    report: dict[str, object] = {}
    total = {"filler": 0, "abstract-noun": 0, "unearned-claim": 0, "self-referential": 0}

    for name, path in PAGES.items():
        if not path.exists():
            continue
        lines = visible_lines(path.read_text(encoding="utf-8"))
        result = score(lines)
        report[name] = result
        for k, v in result["by_rule"].items():  # type: ignore[union-attr]
            total[k] += v

    if args.json:
        print(json.dumps({"pages": report, "total": total}, ensure_ascii=False, indent=2))
        return 0

    print("文案审查（规则可数，判断力另算）\n")
    print(f"{'页面':12s} {'段落':>5s} {'字数':>6s} {'填充词':>7s} {'抽象名词':>9s} {'空洞断言':>9s} {'说明书腔':>9s}")
    for name, r in report.items():
        b = r["by_rule"]  # type: ignore[index]
        print(
            f"  {name:10s} {r['lines']:5d} {r['chars']:6d} "
            f"{b['filler']:7d} {b['abstract-noun']:9d} {b['unearned-claim']:9d} {b['self-referential']:9d}"
        )
    print(f"\n  合计问题: 填充词 {total['filler']} · 抽象名词 {total['abstract-noun']} "
          f"· 空洞断言 {total['unearned-claim']} · 说明书腔 {total['self-referential']}")
    print(f"  总分（越低越好）: {sum(total.values())}")

    if args.verbose:
        print("\n明细：")
        for name, r in report.items():
            for f in r["findings"]:  # type: ignore[index]
                print(f"  [{f['rule']}] 「{f['word']}」 {f['line']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
