#!/usr/bin/env python3
"""设计基线审计：把"好设计"变成可查的契约，而不是靠我记得。

为什么单独一个：前几轮踩了两个同型坑 —— (1) .to-top 看着在，其实
visibility:hidden、滚动才出现；(2) 固定按钮被 .content 这类层盖住，
elementFromPoint 命中的是别的元素，用户点不动。这两个都不是 bug
（是设计），但**没有契约就会漏**：眼睛看"按钮在那儿"是看不见这层的。

查三类（都是"好设计"的硬指标）：
  · 热区：固定定位的操作按钮（回顶、FAB、主题切换）不小于 44x44
    —— 44px 是移动端可点下限，小于这个在手机上容易误触
  · 可点：按钮中心点 elementFromPoint 必须命中它自己（含子元素）
    —— 命中别的层 = 被遮挡，摆了点不动
  · 键盘：全站有 :focus-visible 规则（键盘操作能看见焦点在哪）

用法：
    python3 scripts/audit-design-baseline.py --base URL
"""
from __future__ import annotations

import argparse
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = "http://127.0.0.1:8787"

# 固定定位、"摆在那儿但可能被层挡住"的操作按钮
FIXED = [".to-top", ".tk-fab", ".reader-fab", ".tk-theme-toggle--fixed"]

CHECK = """(sels) => {
  const out = [];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!el) continue;                    // 这一页没这个按钮就跳过，不算问题
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.width < 44 || r.height < 44)) {
      out.push(sel + ' 热区 ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' < 44');
    }
    if (r.width > 0 && cs.visibility !== 'hidden' && cs.display !== 'none') {
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const top = document.elementFromPoint(cx, cy);
      if (!(top && (el === top || el.contains(top)))) {
        out.push(sel + ' 中心点被挡：命中 ' + (top ? top.tagName + '.' +
          (top.className || '').toString().slice(0, 24) : 'null'));
      }
    }
  }
  let hasFocus = false;
  for (const ss of document.styleSheets) {
    let rules;
    try { rules = ss.cssRules; } catch (e) { continue; }
    for (const r of rules) {
      if (r.selectorText && r.selectorText.indexOf(':focus-visible') >= 0) { hasFocus = true; break; }
    }
    if (hasFocus) break;
  }
  if (!hasFocus) out.push('全站没有 :focus-visible 规则（键盘看不到焦点在哪）');
  return out;
}"""


def main() -> int:
    ap = argparse.ArgumentParser(description="设计基线审计（热区/可点/键盘焦点）")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1440, "height": 950}).new_page()
        pg.goto(args.base + "/", timeout=45000, wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        # 让 .to-top 这类"滚动才出现"的按钮先露出来，否则量的是隐藏态
        pg.evaluate("window.scrollTo(0, 1600)")
        pg.wait_for_timeout(900)
        bad = pg.evaluate(CHECK, FIXED)
        pg.screenshot(path="/tmp/shots/design-baseline.png")
        b.close()

    if not bad:
        print("设计基线：固定按钮热区/可点性正常，有 :focus-visible。")
        return 0
    print(f"设计基线：{len(bad)} 项不达标")
    for x in bad:
        print("   ", x)
    return 1


if __name__ == "__main__":
    sys.exit(main())
