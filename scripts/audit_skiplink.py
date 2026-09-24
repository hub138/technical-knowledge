# skip link 修复复测：
# 1) 文章页 Tab 第一步应落在 skip link；第二步应直达 #reader-body 内；
# 2) skip link 聚焦时可见（opacity/transform 就位）、不聚焦时不可见；
# 3) 点击 skip link 后焦点与滚动位置进入正文；
# 4) 首页/全景页同样第一步是 skip link，且目标存在。
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
NOTE = "%E5%B7%A5%E7%A8%8B%E7%9F%A5%E8%AF%86/%E7%BC%BA%E9%99%B7%E5%88%86%E6%9E%90%EF%BC%9A%E4%BB%8E%E4%B8%AA%E6%A1%88%E5%88%B0%E4%BD%93%E7%B3%BB/%E6%AD%A3%E7%A1%AE%E6%80%A7/%E6%A1%88%E4%BE%8B%E5%8D%81%E5%85%AD%EF%BC%9A%E6%95%B0%E6%8D%AE%E8%A2%AB%E8%87%AA%E5%B7%B1%E4%BA%BA%E5%88%A0%E6%8E%89%E2%80%94%E2%80%94entry%20log%20%E5%A4%B4%E9%87%8C%E7%9A%84%E5%81%87%E8%B4%A6.md"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", os.environ["KNOWLEDGE_SITE_PASSWORD"])
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)

    results = []
    for name, path in [
        ("note", "/?path=" + NOTE),
        ("home", "/"),
        ("panorama", "/?view=panorama"),
    ]:
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="load", timeout=30000)
        p.wait_for_timeout(1800)
        p.keyboard.press("Tab")
        step1 = p.evaluate(
            """() => {
                const el = document.activeElement;
                const cs = getComputedStyle(el);
                return {
                    cls: (el.className || '').toString(),
                    text: (el.textContent || '').trim(),
                    visible: cs.opacity === '1' && cs.transform === 'matrix(1, 0, 0, 1, 0, 0)',
                    outline: cs.outlineStyle + ' ' + cs.outlineWidth,
                };
            }"""
        )
        p.keyboard.press("Tab")
        step2 = p.evaluate(
            """() => {
                const el = document.activeElement;
                const chain = [];
                let node = el;
                for (let d = 0; d < 4 && node; d++) {
                    chain.push((node.id ? '#' + node.id : '') + '.' + (node.className || '').toString().split(' ')[0]);
                    node = node.parentElement;
                }
                return {chain: chain.join(' < '), tag: el.tagName, text: (el.textContent || '').trim().slice(0, 12)};
            }"""
        )
        # 回到 skip link 并回车，验证跳转行为。
        p.evaluate("() => document.querySelector('.skip-link').focus()")
        p.keyboard.press("Enter")
        p.wait_for_timeout(400)
        jumped = p.evaluate(
            """() => {
                const el = document.activeElement;
                const body = document.getElementById('reader-body');
                const inBody = body ? body.contains(el) : false;
                return {
                    inReaderBody: inBody,
                    active: el.tagName + '.' + (el.className || '').toString().slice(0, 20),
                    scrollY: Math.round(window.scrollY),
                };
            }"""
        )
        results.append({"page": name, "step1": step1, "step2": step2, "after_enter": jumped})
        p.close()

    # 截一张 skip link 聚焦现身的样子。
    p = ctx.new_page()
    p.goto(BASE + "/?path=" + NOTE, wait_until="load", timeout=30000)
    p.wait_for_timeout(1800)
    p.evaluate("() => document.querySelector('.skip-link').focus()")
    p.wait_for_timeout(300)
    p.screenshot(path=os.path.join(OUT, "skiplink-visible.png"), clip={"x": 0, "y": 0, "width": 700, "height": 260})
    p.close()
    browser.close()

with open(os.path.join(OUT, "results_skiplink.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(json.dumps(results, ensure_ascii=False, indent=2))
