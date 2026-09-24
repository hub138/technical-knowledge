# hover 反馈重测：按各组件规则实际改动的属性取口径。
# 导航=background+color；域树=border-left-color+color；卡片=transform+box-shadow；
# 文章行/子题=源码核对后补口径。输出前后对比写进 results_hover.json。
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"

SPECS = [
    ("hover-nav", "/", ".tk-nav a:not(.tk-nav-pinned)",
     ["backgroundColor", "color", "borderColor"]),
    ("hover-pinned", "/", ".tk-nav-pinned",
     ["backgroundColor", "color"]),
    ("hover-domain", "/", "article.domain-card a, .tk-domain",
     ["borderLeftColor", "color"]),
    ("hover-workcard", "/", "article.work-card",
     ["transform", "boxShadow", "borderColor"]),
    ("hover-noterow", "/", "article.note-row",
     ["backgroundColor", "color"]),
    ("hover-subtopic", "/", "a.tk-subtopic",
     ["backgroundColor", "color"]),
    ("hover-fab", "/", ".tk-fab",
     ["transform", "backgroundColor"]),
]

PROPS_JS = """(props) => {
    const el = document.activeElement === document.body
        ? null : null;
    return props.map((p) => getComputedStyle(document.querySelector(':hover') || document.body)[p]);
}"""

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
    for name, path, sel, props in SPECS:
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        loc = p.locator(sel).first
        if loc.count() == 0:
            results.append({"page": name, "missing": sel})
            p.close()
            continue
        before = loc.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        loc.hover()
        p.wait_for_timeout(500)
        after = loc.evaluate("(el, ps) => ps.map(pr => getComputedStyle(el)[pr])", props)
        changed = [b != a for b, a in zip(before, after)]
        results.append({
            "page": name,
            "selector": sel,
            "props": props,
            "before": before,
            "after": after,
            "changed": changed,
        })
        box = loc.bounding_box()
        if box:
            clip = {
                "x": max(0, box["x"] - 20),
                "y": max(0, box["y"] - 20),
                "width": min(1440, box["width"] + 40),
                "height": min(900, box["height"] + 40),
            }
            p.screenshot(path=os.path.join(OUT, f"{name}.png"), clip=clip)
        p.close()

    browser.close()

with open(os.path.join(OUT, "results_hover.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
for r in results:
    print(json.dumps(r, ensure_ascii=False))
