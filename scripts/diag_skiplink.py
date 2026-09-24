# 诊断脚本：直接检查 skip link 的 DOM 位置与可聚焦性。
# 验证：元素在文档中的顺序（是否真的在 main 首位）、Tab 首步落点、
# 以及 DOM 树里 main 内第一个可聚焦元素是不是 skip link。
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", os.environ["KNOWLEDGE_SITE_PASSWORD"])
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)

    p = ctx.new_page()
    p.goto(BASE + "/?path=工程知识", wait_until="load", timeout=30000)
    p.wait_for_timeout(1500)
    diag = p.evaluate(
        """() => {
            const skip = document.querySelector('.skip-link');
            if (!skip) return {exists: false};
            const main = document.querySelector('main.main');
            const firstFocusableInMain = main
                ? main.querySelector('a, button, input, [tabindex]')
                : null;
            // document 顺序比较
            const order = skip.compareDocumentPosition(firstFocusableInMain);
            const before = skip.getBoundingClientRect();
            // Tab 一次
            return {
                exists: true,
                skipHref: skip.getAttribute('href'),
                firstInMainIsSkip: firstFocusableInMain === skip,
                firstInMainTag: firstFocusableInMain ? firstFocusableInMain.tagName + '.' + firstFocusableInMain.className : null,
                skipIsBeforeFirstMain: (order & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
                rect: {x: Math.round(before.x), y: Math.round(before.y), w: Math.round(before.width)},
                pointerEvents: getComputedStyle(skip).pointerEvents,
                opacity: getComputedStyle(skip).opacity,
            };
        }"""
    )
    p.keyboard.press("Tab")
    first = p.evaluate(
        "() => document.activeElement.className.toString() + ' | ' + document.activeElement.textContent.trim().slice(0, 10)"
    )
    print(json.dumps({"diag": diag, "tab1_active": first}, ensure_ascii=False, indent=2))
    p.screenshot(path=os.path.join(OUT, "diag-skiplink.png"), clip={"x": 0, "y": 0, "width": 700, "height": 260})
    browser.close()
