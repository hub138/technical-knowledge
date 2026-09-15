#!/usr/bin/env python3
"""Build a page-by-page editorial inventory for the engineering knowledge vault."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CORE_TYPES = {
    "concept", "guide", "playbook", "principle", "decision", "design",
    "architecture", "evolution",
}


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    result: dict[str, Any] = {}
    active: str | None = None
    for line in text[4:marker].splitlines():
        item = re.match(r"^\s+-\s+(.+)$", line)
        if item and active:
            result.setdefault(active, [])
            if isinstance(result[active], list):
                result[active].append(item.group(1).strip().strip('"\''))
            continue
        pair = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not pair:
            continue
        key, value = pair.groups()
        active = None
        if not value:
            result[key] = []
            active = key
        elif value.startswith("[") and value.endswith("]"):
            result[key] = [x.strip().strip('"\'') for x in value[1:-1].split(",") if x.strip()]
        else:
            result[key] = value.strip().strip('"\'')
    return result, text[marker + 5:]


def body_signals(body: str) -> dict[str, bool | int]:
    headings = [line.strip()[3:].strip() for line in body.splitlines() if line.startswith("## ")]
    paragraphs: list[str] = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith(("#", "|", "- ", "* ", ">")):
            continue
        paragraphs.append(stripped)
    return {
        "heading_count": len(headings),
        "has_example": any(x in body for x in ("## 示例", "## 最小", "## 实验", "最小实验", "最小对照", "```", "mermaid", "例：", "例如")) or bool(re.search(r"最小.{0,10}(实验|对照|演练)", body)),
        "has_verification": any(x in body for x in ("验证", "评测", "基准", "测试", "观测", "检查")),
        "has_boundary": any(x in body for x in ("边界", "限制", "风险", "误区", "不适用", "不能")),
        "has_relation": "[[" in body,
        # Tables often carry the first causal summary; count the first three prose
        # blocks so a concise, well-structured page is not misclassified as thin.
        "intro_chars": min(sum(len(p) for p in paragraphs[:3]), 700),
    }


def inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "vault" / "工程知识").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        page_type = str(frontmatter.get("type", ""))
        durable = page_type in CORE_TYPES
        signals = body_signals(body)
        risks: list[str] = []
        if durable and int(signals["heading_count"]) < 3:
            risks.append("结构薄")
        if durable and not signals["has_example"]:
            risks.append("缺少例子或实验")
        if durable and not signals["has_boundary"]:
            risks.append("边界不明显")
        if durable and int(signals["intro_chars"]) < 180:
            risks.append("开头解释不足")
        rows.append({
            "path": path.relative_to(root / "vault").as_posix(),
            "domain": path.relative_to(root / "vault" / "工程知识").parts[0],
            "type": page_type,
            "durable": durable,
            "title": str(frontmatter.get("title", path.stem)),
            "updated": str(frontmatter.get("updated", "")),
            "review_after": str(frontmatter.get("review_after", "")),
            "change_rate": str(frontmatter.get("change_rate", "")),
            "source_count": len(frontmatter.get("sources", [])) if isinstance(frontmatter.get("sources"), list) else 0,
            **signals,
            "risks": risks,
            "round1": "通过" if not durable or not risks else "待编辑",
            "round2": "待复核" if durable else "不适用",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = inventory(args.root.resolve())
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    durable_count = sum(1 for row in rows if row["durable"])
    print(f"editorial inventory: {len(rows)} pages scanned ({durable_count} durable)", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
