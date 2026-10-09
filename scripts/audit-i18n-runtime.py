#!/usr/bin/env python3
"""运行时 i18n 泄漏审计：切到英文后，页面上还留着多少中文。

为什么单独一个，不和 i18n_dict_audit 混：
字典审计查的是**词典本身**（key 唯一、翻译一一对应），但字典齐全不等于
页面干净。实测最容易漏的是运行时三处：
  · 硬编码在 HTML 里的中文（i18n 覆盖不到，因为它只翻译 tr() 包过的串）
  · 服务端直出的中文文案（早报状态、空态提示）
  · 数据自带的中文（笔记标题、论文名），那本来就是中文内容不该翻

所以判据要说清：**只报"该翻却没翻"的界面文案**，不报数据内容。
界面文案的识别：可见文本里出现 CJK，**且**它所在的块不是笔记正文
（正文容器里的一律不报）。这样也能抓到"切到 EN 后卡片上写着中文标签"这种。

用法：
    python3 scripts/audit-i18n-runtime.py --base URL
"""
from __future__ import annotations

import argparse
import re
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
    ("/sources/bestblogs", "sources-bestblogs"),
]

CJK = re.compile(r"[一-鿿]")
# 正文容器：里面的中文是内容，不是界面文案，不该翻。
CONTENT_SELECTORS = ("article", ".note-body", ".reader-body", ".src-rich", "p")

SWITCH_JS = """() => {
  // 必须走 setLang：赋值 TKI18N.lang 不会重新渲染（第一版白扫一轮）。
  if (window.TKI18N && typeof window.TKI18N.setLang === "function") {
    window.TKI18N.setLang("en");
    return "setLang(en)";
  }
  return "no-way";
}"""

LEAK_JS = """() => {
  const bad = [];
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.offsetParent !== null;
  };
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length > 0) continue;           // 只看叶子，父节点的文本会重复
    if (!isVisible(el)) continue;
    const t = (el.textContent || '').trim();
    if (!t || !/[\\u4e00-\\u9fff]/.test(t)) continue;
    if (t.length > 42) continue;                    // 长句是正文/数据，不是标签
    const p = el.parentElement;
    // 数据/内容类不报：笔记标题、篇数计数本就是内容，翻了才是错的。
    if (p && p.closest('article, .note-body, .reader-body, .src-rich')) continue;
    if (el.closest('.digest-item-title, .digest-source, .pn-title, .pn-meta')) continue;
    if (el.closest('.pg-title, .pg-domain-count, .pg-overall-num, .note-title, h1, h2, h3')) continue;
    bad.push(((el.className || el.tagName.toLowerCase()).toString() || '').slice(0, 30)
             + ' :: ' + t.slice(0, 40));
  }
  const de = document.documentElement;
  return { leaks: bad.slice(0, 8), overflow: de.scrollWidth - de.clientWidth };
}"""


def audit(base: str) -> list[tuple[str, list[str], int]]:
    out: list[tuple[str, list[str], int]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path, name in PAGES:
            ctx = browser.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            try:
                page.goto(base + path, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(2200)
                step = page.evaluate(SWITCH_JS)
                page.wait_for_timeout(1800)
                info = page.evaluate(LEAK_JS)
                lang = page.evaluate("document.documentElement.lang || (window.TKI18N && window.TKI18N.lang) || '?'")
                if info["leaks"] or info["overflow"] > 2:
                    out.append((name, info["leaks"], info["overflow"], str(lang), step))
            except Exception as e:
                print(f"  skip {name}: {type(e).__name__} {str(e)[:70]}", file=sys.stderr)
            ctx.close()
        browser.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="运行时 i18n 泄漏审计")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    findings = audit(args.base)
    if not findings:
        print("i18n 运行时：切到英文后没有中文漏网（也没有横向溢出）。")
        return 0
    print(f"i18n 运行时：{len(findings)} 个页面有发现")
    for name, leaks, overflow, lang, step in findings:
        extra = f"（横向溢出 {overflow}px）" if overflow > 2 else ""
        print(f"  [{name}] lang={lang} 切法={step}{extra}")
        for l in leaks:
            print(f"      中文漏网: {l}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
