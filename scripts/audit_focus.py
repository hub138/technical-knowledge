# 键盘焦点环 + hover 反馈 + 1440 大屏三维度审计脚本。
# 登录换 cookie 后依次：Tab 遍历全页可点元素核对焦点环、hover 关键组件、
# 1440 大屏四页对照，证据图与量测 JSON 留档。
import os
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
os.makedirs(OUT, exist_ok=True)

CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
DEFECT = urllib.parse.quote("缺陷分析：从个案到体系", safe="")
NOTE = urllib.parse.quote(
    "工程知识/缺陷分析：从个案到体系/正确性/案例十六：数据被自己人删掉——entry log 头里的假账.md",
    safe="/",
)

FOCUS_PAGES = [
    ("focus-home", "/"),
    ("focus-note", f"/?path={NOTE}"),
    ("focus-panorama", "/?view=panorama"),
    ("focus-graph", "/?view=graph"),
]

BIG_PAGES = [
    ("big-home", "/"),
    ("big-note", f"/{'' if False else '?'}path={NOTE}"),
    ("big-panorama", "/?view=panorama"),
    ("big-graph", "/?view=graph"),
]

FOCUS_SELECTORS = "a, button, [role=button], [tabindex], select, summary, input, textarea"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", os.environ["KNOWLEDGE_SITE_PASSWORD"])
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)
    cookies = ctx.cookies(BASE)

    results = []

    # ── 维度一：键盘焦点环 ──
    for name, path in FOCUS_PAGES:
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        count = p.evaluate(
            """(sel) => document.querySelectorAll(sel).length""", FOCUS_SELECTORS
        )
        p.keyboard.press("Tab")
        for i in range(12):
            p.evaluate(
                """(sel) => {
                    const el = document.activeElement;
                    const cs = getComputedStyle(el);
                    window.__focusInfo = {
                        tag: el.tagName,
                        cls: (el.className || '').toString().slice(0, 40),
                        outline: cs.outlineStyle + ' ' + cs.outlineWidth,
                        text: (el.textContent || '').trim().slice(0, 20),
                    };
                }""",
                FOCUS_SELECTORS,
            )
            info = p.evaluate("() => window.__focusInfo")
            info.update(page=name, step=i)
            results.append(info)
            if i in (0, 5):
                p.screenshot(
                    path=os.path.join(OUT, f"{name}-tab{i}.png"),
                    clip={"x": 0, "y": 0, "width": 1440, "height": 400},
                )
            p.keyboard.press("Tab")
        p.close()

    # ── 维度二：hover 反馈抽查 ──
    hover_specs = [
        ("hover-nav", "/", ".tk-nav a"),
        ("hover-card", "/", "a.card"),
        ("hover-btn", "/", ".button"),
        ("hover-domain", "/", ".tk-domain"),
    ]
    for name, path, sel in hover_specs:
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        loc = p.locator(sel).first
        if loc.count() == 0:
            results.append({"page": name, "missing": sel})
            p.close()
            continue
        before = loc.evaluate("el => getComputedStyle(el).backgroundColor")
        loc.hover()
        p.wait_for_timeout(400)
        after = loc.evaluate("el => getComputedStyle(el).backgroundColor")
        results.append({"page": name, "before": before, "after": after})
        p.screenshot(
            path=os.path.join(OUT, f"{name}.png"),
            clip={"x": 0, "y": 0, "width": 1440, "height": 500},
        )
        p.close()

    # ── 维度三：1440 大屏对照 ──
    for name, path in BIG_PAGES:
        p = ctx.new_page()
        p.goto(BASE + path + "&theme=light" if "?" in path else BASE + path + "?theme=light", wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        p.screenshot(path=os.path.join(OUT, f"{name}.png"), full_page=True)
        overflow = p.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
        results.append({"page": name, "h_overflow_1440": overflow})
        p.close()

    browser.close()

import json

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(json.dumps(results, ensure_ascii=False, indent=2))
