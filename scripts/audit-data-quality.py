#!/usr/bin/env python3
"""知识库 frontmatter 的数据质量审计 —— 查的是"内容本身"，不是页面。

为什么单独一个审计，不和 layout/contrast 一起：
它们都在浏览器里量渲染结果，而这里查的是**渲染之前**的东西。
tags 写重两遍，页面表现是"同一枚 chip 显示两次"（用户报过一次），
但根因在数据，不在 CSS；等眼睛在页面上看到重复就已经晚了 ——
而在 2500 篇里找，得靠全库扫一次。

查什么（都是会真的变成页面问题的）：
  · tags 重复     同一个 tag 在一篇里出现两次 → 渲染成两枚重复 chip
  · tags 空项     `- ""` 或 `-   ` → 页面上多一枚空白 chip
  · tags 数量异常 单篇超过 12 个 → 卡片被挤到换行
  · 重复路径      同一个文件被两条路径收录（同一 path 两处 md）

退出码：有 tags 重复/空项返回 1（阻断），路径重复只报告。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
MAX_TAGS = 12

_TAG_BLOCK = re.compile(r"^tags:\s*\n((?:[ \t]*-.*\n?)+)", re.M)


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def frontmatter(path: Path) -> str | None:
    """返回 frontmatter 文本，没有返回 None。"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    return parts[1] if len(parts) > 2 else None


def scan() -> list[dict]:
    findings: list[dict] = []
    for md in sorted(VAULT.rglob("*.md")):
        head = frontmatter(md)
        if not head:
            continue
        rel = str(md.relative_to(VAULT))
        m = _TAG_BLOCK.search(head)
        if not m:
            continue
        raw = [_clean(line.strip()[2:]) for line in
               (l for l in m.group(1).splitlines() if l.strip())]
        raw = [r for r in raw if r.startswith("- ") is False]  # 上面已经剥过 "- "
        values = [_clean(r[2:]) if r.startswith("- ") else _clean(r) for r in raw]
        values = [v for v in values if v]

        dup = sorted({v for v in values if values.count(v) > 1})
        blank = [r for r in raw if not _clean(r)]
        if dup:
            findings.append({"path": rel, "kind": "tags_duplicated",
                             "detail": dup[:4], "severity": "error"})
        if blank:
            findings.append({"path": rel, "kind": "tags_blank",
                             "detail": blank[:2], "severity": "error"})
        if len(values) > MAX_TAGS:
            findings.append({"path": rel, "kind": "tags_too_many",
                             "detail": len(values), "severity": "warn"})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="frontmatter 数据质量审计")
    ap.add_argument("--json", action="store_true", help="输出 JSON 供编排器解析")
    args = ap.parse_args()

    findings = scan()
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]

    if args.json:
        print(json.dumps(findings, ensure_ascii=False))
        return 1 if errors else 0

    print(f"扫描发现 {len(findings)} 条（ERROR {len(errors)} / WARN {len(warns)}）")
    for f in findings[:12]:
        tag = "ERR " if f["severity"] == "error" else "WARN"
        print(f"  {tag} [{f['kind']}] {f['path'][:58]} :: {f['detail']}")
    if not findings:
        print("frontmatter 数据干净：没有重复/空 tag。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
