# 回归三件套：
# 1) 文章页 skip link 全链路（Tab1 命中、Enter 落正文、无 JS 错误）；
# 2) 布局审计口径复跑（固定栏衔接、横向溢出）确认 skip link 无布局回归；
# 3) 文章页 Tab 全程 60 步重走，正文首步应从 25 降到 2 以内。
import json
import os
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
NOTE = urllib.parse.quote(
    "工程知识/缺陷分析：从个案到体系/正确性/案例十六：数据被自己人删掉——entry log 头里的假账.md",
    safe="/",
)

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", os.environ["KNOWLEDGE_SITE_PASSWORD"])
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)
    errors = []
    ctx.on("pageerror", lambda e: errors.append(str(e)))

    report = {"js_errors": errors}

    # 1) 全链路
    p = ctx.new_page()
    p.goto(BASE + "/?path=" + NOTE, wait_until="load", timeout=30000)
    p.wait_for_timeout(1800)
    p.keyboard.press("Tab")
    step1 = p.evaluate("() => document.activeElement.className.toString()")
    p.keyboard.press("Enter")
    p.wait_for_timeout(400)
    after = p.evaluate(
        "() => ({inBody: document.getElementById('reader-body').contains(document.activeElement),"
        " outlineVisible: getComputedStyle(document.getElementById('reader-body')).outlineStyle})"
    )
    report["skiplink_note"] = {"step1": step1, "after": after}
    p.close()

    # 2) 布局口径：三档宽度横向溢出 + 固定栏衔接（文章页头部顶距）。
    for width, height in [(1440, 900), (1024, 768), (390, 844)]:
        pw_page = ctx.new_page()
        pw_page.set_viewport_size({"width": width, "height": height})
        pw_page.goto(BASE + "/?path=" + NOTE, wait_until="load", timeout=30000)
        pw_page.wait_for_timeout(1500)
        overflow = pw_page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        gap = pw_page.evaluate(
            """() => {
                const bar = document.querySelector('.progress-bar') || document.querySelector('.topbar');
                const title = document.querySelector('#reader-title');
                if (!bar || !title) return null;
                const b = bar.getBoundingClientRect();
                const t = title.getBoundingClientRect();
                return Math.round(t.top - b.bottom);
            }"""
        )
        report[f"layout_{width}"] = {"h_overflow_px": overflow, "topbar_to_title_px": gap}
        pw_page.close()

    # 3) Tab 全程重走
    p = ctx.new_page()
    p.goto(BASE + "/?path=" + NOTE, wait_until="load", timeout=30000)
    p.wait_for_timeout(1800)
    p.keyboard.press("Tab")
    p.keyboard.press("Enter")
    p.wait_for_timeout(300)
    body_first = None
    for i in range(10):
        inside = p.evaluate("() => document.getElementById('reader-body').contains(document.activeElement)")
        if inside:
            body_first = i + 1
            break
        p.keyboard.press("Tab")
    report["body_first_step_after_skiplink"] = body_first
    p.close()
    browser.close()

with open(os.path.join(OUT, "results_regression.json"), "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
