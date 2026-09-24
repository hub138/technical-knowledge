# 键盘到达正文步数量测：文章页 Tab 走 60 步，记录第几步进入正文区域。
# 核心资产优先原则：键盘路径第一优先应能直达正文。
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

    p = ctx.new_page()
    p.goto(BASE + "/?path=" + NOTE, wait_until="load", timeout=30000)
    p.wait_for_timeout(1800)
    walk = []
    p.keyboard.press("Tab")
    for i in range(60):
        info = p.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el) return {tag: 'NONE'};
                const chain = [];
                let node = el;
                for (let d = 0; d < 4 && node; d++) {
                    chain.push((node.id ? '#' + node.id : '') + '.' + (node.className || '').toString().split(' ')[0]);
                    node = node.parentElement;
                }
                const cs = getComputedStyle(el);
                return {
                    step: null,
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 30),
                    text: (el.textContent || '').trim().slice(0, 14),
                    chain: chain.join(' < '),
                    outline: cs.outlineStyle === 'solid' && parseFloat(cs.outlineWidth) >= 2,
                };
            }"""
        )
        info["step"] = i + 1
        walk.append(info)
        p.keyboard.press("Tab")

    # 判定正文进入点：reader-body 内的元素或 reader-toc。
    body_steps = [w["step"] for w in walk if "reader-body" in w.get("chain", "")]
    toc_steps = [w["step"] for w in walk if "reader-toc" in w.get("chain", "")]
    no_outline = [w for w in walk if not w.get("outline", False)]

    result = {
        "total_walked": len(walk),
        "body_first_step": body_steps[0] if body_steps else None,
        "body_steps": body_steps[:8],
        "toc_first_step": toc_steps[0] if toc_steps else None,
        "missing_outline": no_outline,
    }
    browser.close()

with open(os.path.join(OUT, "results_tabpath.json"), "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))
