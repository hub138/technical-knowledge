#!/usr/bin/env python3
"""按两个方法论，扫描知识页缺失的关系槽并给出可回流的案例。

对应的判断依据：
  vault/知识库管理/方法/知识完善度怎么判断——四象限与九个信号.md
  vault/知识库管理/方法/知识缺口怎么补——图谱关系槽与补强工作流.md

与 scripts/audit-knowledge-quality.py 的分工：那个脚本查语义维度
（problem/essence/practice/...），这个脚本查**关系与证据**——
案例回流、可运行代码、数字、入链。两者互补，不重叠。

输出：按优先级排序的补强清单（先 C 类空心枢纽，再 B 类孤岛，再 D 类占位页）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"

# 案例页所在目录，用于"哪些页能作为案例回流来源"
CASE_DIR_MARK = "缺陷分析入门到精通"

CASE_REF = re.compile(r"案例[一二三四五六七八九十百]+")
CODE_BLOCK = re.compile(r"```")
HAS_NUMBER = re.compile(r"[0-9]")
VERIFY_WORDS = ("验证", "怎么测", "断言", "assert", "复现", "评测", "基线")
BOUNDARY_WORDS = ("不该用", "不适用", "反例", "失效", "边界", "限制", "失败", "不能证明")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head = text[3:end]
    body = text[end + 4:]
    meta: dict = {}
    for line in head.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta, body


def page_char_count(body: str) -> int:
    return len(re.sub(r"\s", "", body))


def scan_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    chars = page_char_count(body)
    is_case = CASE_DIR_MARK in str(path)

    missing: list[str] = []
    if chars < 1500:
        missing.append("篇幅不足")
    if not CODE_BLOCK.search(body):
        missing.append("无可运行示例")
    if not HAS_NUMBER.search(body):
        missing.append("无量化数字")
    if not any(w in body for w in VERIFY_WORDS):
        missing.append("无验证方式")
    if not any(w in body for w in BOUNDARY_WORDS):
        missing.append("无边界声明")
    # 案例回流只在非案例页上查
    if not is_case and not CASE_REF.search(body):
        missing.append("无案例回流")

    return {
        "path": str(path.relative_to(VAULT)),
        "title": meta.get("title", path.stem),
        "type": meta.get("type", ""),
        "confidence": meta.get("confidence", ""),
        "change_rate": meta.get("change_rate", ""),
        "review_after": meta.get("review_after", ""),
        "chars": chars,
        "is_case": is_case,
        "has_case_ref": bool(CASE_REF.search(body)),
        "missing": missing,
    }


def collect_cases() -> list[dict]:
    """收集可作为回流来源的案例页，带关键词便于匹配。"""
    cases = []
    for p in VAULT.rglob("*.md"):
        if CASE_DIR_MARK not in str(p):
            continue
        text = p.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        # 从标题与首段提取关键词
        kw = set(re.findall(r"[A-Za-z]{3,}", p.stem))
        for zh in ("权限", "ACL", "认证", "并发", "锁", "缓存", "配置", "依赖",
                   "内存", "磁盘", "网络", "超时", "重试", "索引", "事务",
                   "日志", "监控", "升级", "兼容", "类型", "反射", "序列化"):
            if zh in body:
                kw.add(zh)
        cases.append({
            "path": str(p.relative_to(VAULT)),
            "title": meta.get("title", p.stem),
            "keywords": kw,
        })
    return cases


def suggest_cases(page: dict, cases: list[dict], limit: int = 3) -> list[str]:
    """按关键词重叠给页面推荐可回流案例。"""
    pt = Path(VAULT) / page["path"]
    text = pt.read_text(encoding="utf-8")
    scored = []
    for c in cases:
        if c["path"] == page["path"]:
            continue
        overlap = sum(1 for k in c["keywords"] if k in text)
        if overlap >= 2:
            scored.append((overlap, c["title"]))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:limit]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--top", type=int, default=20, help="显示前 N 条")
    args = ap.parse_args()

    pages = [scan_page(p) for p in VAULT.rglob("*.md")
             if p.is_file() and "归档" not in str(p)]
    cases = collect_cases()

    knowledge = [p for p in pages if not p["is_case"]]
    for p in knowledge:
        p["suggested_cases"] = suggest_cases(p, cases)

    # 缺得越多越靠前；篇幅不足优先
    def rank(p):
        return (-len(p["missing"]), p["chars"])

    knowledge.sort(key=rank)

    if args.json:
        print(json.dumps(knowledge[:args.top], ensure_ascii=False, indent=2))
        return 0

    total = len(knowledge)
    no_case = sum(1 for p in knowledge if "无案例回流" in p["missing"])
    no_code = sum(1 for p in knowledge if "无可运行示例" in p["missing"])
    no_num = sum(1 for p in knowledge if "无量化数字" in p["missing"])
    short = sum(1 for p in knowledge if "篇幅不足" in p["missing"])

    print(f"知识页 {total} 篇，缺口统计：")
    print(f"  无案例回流   {no_case:>3} 篇  ({no_case*100//max(1,total)}%)")
    print(f"  无可运行示例 {no_code:>3} 篇  ({no_code*100//max(1,total)}%)")
    print(f"  无量化数字   {no_num:>3} 篇  ({no_num*100//max(1,total)}%)")
    print(f"  篇幅不足     {short:>3} 篇  ({short*100//max(1,total)}%)")
    print()
    print(f"优先补强清单（前 {args.top}）：")
    for p in knowledge[:args.top]:
        print(f"\n  [{len(p['missing'])}处缺口] {p['title']}")
        print(f"    {p['path']}  ({p['chars']} 字符)")
        print(f"    缺：{' / '.join(p['missing'])}")
        if p["suggested_cases"]:
            print(f"    可回流：{' · '.join(p['suggested_cases'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
