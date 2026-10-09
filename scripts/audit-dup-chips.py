#!/usr/bin/env python3
"""全站重复 chip 审计 —— 同一个 chip 文本在页面上出现多次。

为什么单独一个：
用户报过一次「domain+topic 三行、前两行一模一样」。那一次我量了
出问题的那一篇就下结论"线上没这个 bug"，**没把它当一类问题全站扫** ——
结果真正的根因（25 篇笔记 frontmatter 的 tags 写重）一直在库里躺着，
只是那一页恰好没触发到。

所以这个审计不去找"某一页的某个 chip"，而是遍历页面、统计 chip 文本，
把"同一段文本出现 >1 次"当成问题报出来。

注意两种**别误报**的情况（第一版就踩过）：
  1. 父子文本会被算重：`.lp-chip` 的内容是"安全与治理（7 篇）"，
     它内部的 `.lp-chip-count` 又是"（7 篇）" —— 同一枚 chip 被算成两个。
     判据改成"只统计叶子节点里没有同名子元素"的比较方式：把 chip 的
     **最深一层文本**拿去比，父子元素就不会重复计数。
  2. 侧栏与正文各自渲染同一批子主题（`.tk-subtopics` 和 `.atlas-dots`）
     时文本重合，但那两个区块在页面上分处两侧，不是重复渲染。
     这里只报"同一区块内"的重复：祖先路径相同的才算。

用法：
    python3 scripts/audit-dup-chips.py                 # 扫默认站点
    python3 scripts/audit-dup-chips.py --base URL      # 指定
"""
from __future__ import annotations

import argparse
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = "http://127.0.0.1:8787"

PAGES = [
    ("/", "home"),
    ("/papers", "papers"),
    ("/sources", "sources"),
    ("/projects", "projects"),
    ("/learn", "learn"),
    ("/learn/history", "learn-history"),
    ("/panorama/path", "path"),
    ("/panorama/reading", "reading"),
    ("/?view=graph", "graph"),
    ("/?view=panorama", "panorama"),
    ("/paper?id=1508.07909", "paper-detail"),
]

# 只统计**可见**的 chip，且取最深一层文本。两个坑：
#   1. 父子同名元素各算一次会让每一枚 chip 都"重复"。
#   2. 响应式双渲染：桌面与移动各渲染一份 chip，另一份靠 CSS 藏起来但
#      还在 DOM 里（实测 /panorama/path 上"（N 篇）"计数被算到 x5）。
#      那种重复眼睛看不到，不算 bug —— 只报量得出来的。
LEAF_TEXT = """(sel) => Array.from(document.querySelectorAll(sel)).filter((el) => {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 && el.offsetParent !== null;
}).map((el) => {
  let deepest = el;
  while (deepest.firstElementChild
         && deepest.firstElementChild.textContent.trim()
            === deepest.textContent.trim()) {
    deepest = deepest.firstElementChild;
  }
  // 剥掉"篇数"后缀再比：不同 chip（不同领域/主题名）完全可能都是
  // "8 篇"，那是计数相同不是内容重复 —— 第一版没剥，把 path 页报成
  // "（8 篇）x4"，是误报。
  const t = deepest.textContent.trim().replace(/（\\d+\\s*篇）/, "").trim();
  return t;
})"""

CHIP_SEL = '[class*="chip"], [class*="meta-chip"]'


def audit(base: str) -> list[tuple[str, list[str]]]:
    findings: list[tuple[str, list[str]]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path, name in PAGES:
            ctx = browser.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            try:
                page.goto(base + path, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2600)
                texts = page.evaluate(LEAF_TEXT, CHIP_SEL)
                seen: dict[str, int] = {}
                for t in texts:
                    if t:
                        seen[t] = seen.get(t, 0) + 1
                dups = [f"{t} x{n}" for t, n in seen.items() if n > 1]
                if dups:
                    findings.append((name, dups[:5]))
            except Exception as e:  # 一个页面挂了不能拖垮整轮审计
                print(f"  skip {name}: {type(e).__name__} {str(e)[:60]}", file=sys.stderr)
            ctx.close()
        browser.close()
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="全站重复 chip 审计")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    findings = audit(args.base)
    if not findings:
        print("重复 chip：没有（各页 chip 文本唯一）。")
        return 0
    print(f"重复 chip：{len(findings)} 个页面有发现")
    for name, dups in findings:
        print(f"  [{name}] " + " · ".join(dups))
    return 1


if __name__ == "__main__":
    sys.exit(main())
