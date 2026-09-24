# 补测三处：非当前导航项 hover、深色焦点环对比、输入框焦点形态。
# 输出口径与 audit_focus.py 一致，结果追加进 design-craft-r6。
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

    results = []

    # 1) 非当前导航项 hover：排除当前态与钉选项，用第二项。
    p = ctx.new_page()
    p.goto(BASE + "/", wait_until="load", timeout=30000)
    p.wait_for_timeout(1500)
    nav = p.locator(".tk-nav a:not(.tk-nav-pinned):not([aria-current])")
    n = nav.count()
    if n >= 2:
        loc = nav.nth(1)
        props = ["backgroundColor", "color"]
        before = loc.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        loc.hover()
        p.wait_for_timeout(500)
        after = loc.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        results.append({
            "page": "hover-nav-plain",
            "selector_count": n,
            "props": props,
            "before": before,
            "after": after,
            "changed": [b != a for b, a in zip(before, after)],
        })
    else:
        results.append({"page": "hover-nav-plain", "selector_count": n})
    p.close()

    # 2) 深色焦点环：Tab 后量焦点环颜色与邻域底色对比度（WCAG 3:1）。
    def rel_lum(rgb):
        def ch(c):
            c = c / 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = rgb
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

    def contrast(c1, c2):
        l1, l2 = rel_lum(c1), rel_lum(c2)
        hi, lo = max(l1, l2), min(l1, l2)
        return (hi + 0.05) / (lo + 0.05)

    def parse_rgb(s):
        parts = s.replace("rgba", "rgb").replace("rgb(", "").replace(")", "").split(",")
        return [int(x.strip()) for x in parts[:3]]

    for theme in ("light", "dark"):
        p = ctx.new_page()
        p.goto(BASE + "/?theme=" + theme, wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        p.keyboard.press("Tab")
        p.wait_for_timeout(200)
        data = p.evaluate(
            """() => {
                const el = document.activeElement;
                const cs = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return {
                    outlineColor: cs.outlineColor,
                    outlineWidth: cs.outlineWidth,
                    outlineStyle: cs.outlineStyle,
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 30),
                };
            }"""
        )
        body_bg = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
        oc = parse_rgb(data["outlineColor"])
        bg = parse_rgb(body_bg)
        ratio = contrast(oc, bg)
        data["bodyBg"] = body_bg
        data["contrast_outline_vs_body"] = round(ratio, 2)
        data["theme"] = theme
        results.append(data)
        p.screenshot(
            path=os.path.join(OUT, f"focus-{theme}.png"),
            clip={"x": 0, "y": 0, "width": 900, "height": 220},
        )
        p.close()

    # 3) 输入框焦点形态：搜索框聚焦的可见反馈。
    p = ctx.new_page()
    p.goto(BASE + "/", wait_until="load", timeout=30000)
    p.wait_for_timeout(1500)
    inp = p.locator("input[type=search]").first
    if inp.count():
        props = ["boxShadow", "borderColor"]
        before = inp.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        inp.focus()
        p.wait_for_timeout(400)
        after = inp.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        results.append({
            "page": "input-focus",
            "props": props,
            "before": before,
            "after": after,
            "changed": [b != a for b, a in zip(before, after)],
        })
    p.close()

    browser.close()

with open(os.path.join(OUT, "results_more.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
for r in results:
    print(json.dumps(r, ensure_ascii=False))
