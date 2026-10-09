#!/usr/bin/env python3
"""交互审计：把页面上能点的都点一遍，看有没有报错、死链、点了没反应。

为什么单独一个：渲染审计（layout/contrast/dup-chips）只看页面长什么样，
i18n 审计只看字对不对 —— **没有任何一个检查会"真的去点"**。而点爆的 crisis
恰好是这类：按钮绑错了、事件监听忘了挂、点完抛异常页面静默不动。
肉眼扫一圈看不出来，因为你不点它就不炸。

判据（三种都算问题）：
  · 点下去抛 JS 错误（pageerror / console error）
  · 找不到按钮（选择器失效 = 结构改过但审计没跟上，或者按钮是禁用的）
  · 点完不到 1.2 秒页面**完全没有变化**（没新节点、没 class 变动、没滚动）
     —— 只针对"本来就该有反应"的按钮，见 SHOULD_CHANGE

用法：
    python3 scripts/audit-interactions.py --base URL
"""
from __future__ import annotations

import argparse
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = "http://127.0.0.1:8787"

# (页面, 选择器, 名字, 点完是否该有可见变化)
INTERACTIONS = [
    ("/", "button.digest-chip--refresh", "早报-更新", True),
    ("/", "button.digest-feature-btn", "早报-钉选切换", True),
    ("/", "button.tk-fav-btn", "早报-收藏", True),
    ("/", "button.reader-tool", "笔记-本文目录", True, True),
    ("/", "button.reader-back", "笔记-返回目录", True, True),
    ("/", "button.reader-tool", "笔记-下载md", False, True),
    ("/", "button.reader-learned", "笔记-标记已读", True, True),
    ("/", "button.reader-fab", "笔记-反馈", False, True),
    ("/", "button.to-top", "回到顶部", False),
    ("/", "button.kbd-hint", "快捷键说明", True),
    ("/papers", "button[data-score='score']", "论文-按评分", True),
    ("/papers", "button[data-kind='only-scored']", "论文-只看已评", True),
    ("/panorama/path", "button.lp-chip", "路线-选chip", True),
    ("/sources", "button.src-chip", "好文-chip", True),
    ("/learn", "button[data-kind='score']", "学习-评分排序", True),
]

CHANGE_JS = """() => ({
  nodes: document.querySelectorAll('*').length,
  hash: document.body.innerHTML.length,
  text: document.body.innerText.length,
  scroll: window.scrollY,
})"""

WATCH_JS = """() => {
  window.__errs = [];
  const push = (kind, text) => window.__errs.push(kind + ': ' + text);
  window.addEventListener('error', (e) => push('error', (e.message || '').slice(0, 90)));
  window.addEventListener('unhandledrejection',
    (e) => push('rejection', String(e.reason || '').slice(0, 90)));
}"""


def audit(base: str) -> list[tuple[str, str, list[str, bool]]]:
    bad: list[tuple[str, str, list[str], bool]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seen_pages: set[str] = set()
        for item in INTERACTIONS:
            path, sel, label, should_change = item[0:4]
            via_note = item[4] if len(item) > 4 else False
            ctx = browser.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            try:
                page.goto(base + path, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                if via_note:
                    # reader-* 那组按钮只在笔记详情页存在，得先搜索进一篇
                    box = page.locator('input[placeholder*="输入即筛选"]')
                    if box.count():
                        box.first.fill("缓存")
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2200)
                        hit = page.get_by_text("缓存", exact=False).first
                        if hit.count():
                            hit.click()
                            page.wait_for_timeout(2400)
                page.evaluate(WATCH_JS)
                # 等选择器出现再判"不存在"：首页早报/顶栏是异步渲染的，
                # 第一版只 sleep 2.5s 就查，按钮还没进 DOM，误报成"选择器失效"。
                try:
                    page.wait_for_selector(sel, state='attached', timeout=9000)
                except Exception:
                    bad.append((path, label, ["按钮不存在（选择器失效或异步未渲染）"], True))
                    ctx.close()
                    continue
                loc = loc = page.locator(sel)
                if not loc.count():
                    bad.append((path, label, ["按钮不存在（选择器失效）"], True))
                    ctx.close()
                    continue
                before = page.evaluate(CHANGE_JS)
                loc.first.click(timeout=8000)
                page.wait_for_timeout(1400)
                after = page.evaluate(CHANGE_JS)
                errs = page.evaluate("window.__errs || []")
                if errs:
                    bad.append((path, label, errs, should_change))
                elif should_change and after == before:
                    bad.append((path, label, ["点了没反应（DOM/滚动都没变）"], True))
            except Exception as e:
                bad.append((path, label, [f"{type(e).__name__}: {str(e)[:70]}"], True))
            ctx.close()
        browser.close()
    return bad



def check_note_switch(base: str) -> list[str]:
    """连点两篇不同文章：面包屑（.meta-chip）不许累积。

    2026-09-27 的真 bug：#reader-chips 每次渲染都 insertAdjacentHTML 一份、
    旧的从不清，连读几篇后屏幕上叠着好几行同样文字的面包屑（第 3 篇时 6 枚 chip）。
    单篇页面量不出这个 —— 必须切一次文章才触发。
    """
    bad = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 950}).new_page()
        pg.goto(base + "/", timeout=45000, wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        counts = []
        for keyword, hint in [("时钟", "电源与时钟"), ("零拷贝", "零拷贝")]:
            box = pg.locator('input[placeholder*="输入即筛选"]')
            box.first.fill(keyword)
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(2200)
            hit = pg.get_by_text(hint, exact=False).first
            if hit.count():
                hit.click()
                pg.wait_for_timeout(2500)
            counts.append(pg.evaluate(
                "() => document.querySelectorAll('.meta-chip').length"))
        b.close()
    if len(counts) == 2 and counts[1] > counts[0]:
        bad.append(f"切换文章后面包屑累积：第1篇 {counts[0]} 枚 → 第2篇 {counts[1]} 枚（旧的没清）")
    return bad

def main() -> int:
    ap = argparse.ArgumentParser(description="交互审计：点一遍页面上的按钮")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    findings = audit(args.base)
    findings = [(("/", "连点两篇文章-面包屑不累积"), errs, False)
                for errs in [check_note_switch(args.base)] if errs]
    if not findings:
        print(f"交互审计：{len(INTERACTIONS)} 个交互全部正常（无报错、无死链、该有反应的都有反应）。")
        return 0
    print(f"交互审计：{len(findings)}/{len(INTERACTIONS)} 个交互有问题")
    for path, label, errs, _ in findings:
        print(f"  [{path}] {label}")
        for e in errs[:2]:
            print(f"       {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
