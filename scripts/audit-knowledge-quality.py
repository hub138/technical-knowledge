#!/usr/bin/env python3
"""Audit the causal contract of durable engineering knowledge pages.

The audit deliberately checks semantic signals instead of requiring one
visible template. Overview and map pages are navigation surfaces; durable
knowledge pages must still make their problem, mechanism, practice, tradeoff,
boundary, and verification legible.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CORE_TYPES = {
    "concept",
    "guide",
    "playbook",
    "principle",
    "decision",
    "design",
    "architecture",
    "evolution",
}

DIMENSION_SIGNALS = {
    "problem": ("要解决的问题", "解决的问题", "解决什么", "解决的是", "为什么需要", "痛点", "目标", "瓶颈", "挑战", "难题", "约束", "面对", "需要", "要求"),
    "essence": ("本质", "核心机制", "机制", "原理", "核心模型", "因果", "决定", "依赖", "路径", "分层", "生命周期", "架构", "模型", "关键在于", "核心是"),
    "practice": ("做法", "实现", "如何", "工程用法", "步骤", "配置", "设计", "使用", "采用", "通过", "处理", "策略", "方法", "流程", "先", "再", "可以", "建议"),
    "effect": ("效果", "收益", "代价", "取舍", "影响", "成本", "性能", "权衡", "提升", "降低", "开销", "延迟", "吞吐", "可靠性", "因此", "从而", "导致", "能够"),
    "boundary": ("边界", "适用", "不适用", "限制", "风险", "误区", "失败", "前提", "不能", "不要", "避免", "只在", "除非"),
    "verification": ("验证", "评测", "指标", "测试", "检查", "基准", "证据", "复现", "观测", "对照", "测量", "实验", "回归", "比较"),
}


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    data: dict[str, Any] = {}
    active_list: str | None = None
    for line in text[4:marker].splitlines():
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and active_list:
            data.setdefault(active_list, [])
            if isinstance(data[active_list], list):
                data[active_list].append(list_match.group(1).strip().strip('"\''))
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        active_list = None
        if not value:
            data[key] = []
            active_list = key
        elif value.startswith("[") and value.endswith("]"):
            data[key] = [item.strip().strip('"\'') for item in value[1:-1].split(",") if item.strip()]
        else:
            data[key] = value.strip('"\'')
    return data, text[marker + 5 :]


def _has_source(frontmatter: dict[str, Any]) -> bool:
    sources = frontmatter.get("sources")
    return isinstance(sources, list) and any(str(source).strip() for source in sources)


def _dimension_present(body: str, title: str, signals: tuple[str, ...]) -> bool:
    headings = "\n".join(
        line for line in body.splitlines() if re.match(r"^\s*#{1,6}\s+", line)
    )
    if any(signal in headings for signal in signals):
        return True
    # A table or prose sentence can answer a dimension without using the
    # exact heading. Avoid counting a bare word in a link target as evidence.
    prose = title + "\n" + re.sub(r"\[\[[^]]+\]\]", "", body)
    prose = re.sub(r"https?://\S+", "", prose)
    return any(signal in prose for signal in signals)


def audit(root: Path) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    knowledge_root = root / "vault" / "工程知识"
    for path in sorted(knowledge_root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        relative = path.relative_to(root / "vault").as_posix()
        page_type = str(frontmatter.get("type", ""))
        if page_type not in CORE_TYPES:
            continue

        missing: list[str] = []
        for key in ("title", "updated", "review_after", "change_rate", "confidence"):
            if not str(frontmatter.get(key, "")).strip():
                missing.append(f"metadata:{key}")
        if not _has_source(frontmatter):
            missing.append("source")
        for dimension, signals in DIMENSION_SIGNALS.items():
            if not _dimension_present(body, str(frontmatter.get("title", "")), signals):
                missing.append(dimension)
        if not re.search(r"\[\[[^]]+\]\]", body + "\n" + str(frontmatter.get("sources", ""))):
            missing.append("relation")
        if missing:
            failures.append({"path": relative, "type": page_type, "missing": missing})
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="print machine-readable findings")
    args = parser.parse_args()
    failures = audit(args.root.resolve())
    if args.json:
        print(json.dumps(failures, ensure_ascii=False, indent=2))
    elif failures:
        for failure in failures:
            print(f"{failure['path']}: {', '.join(failure['missing'])}")
        print(f"quality audit failed: {len(failures)} page(s)")
    else:
        print(f"quality audit passed: {len(list((args.root / 'vault' / '工程知识').rglob('*.md')))} engineering page(s) scanned")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
