# 全站点审查截图：4 视图（home/directory/graph/panorama）+ 全景 2 tab，
# × 4 宽度 × 深浅主题。全景 tab 用 ?tab=stack 深链直达。
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "views")
os.makedirs(OUT, exist_ok=True)

TARGETS = [
    ("home", "/"),
    ("directory", "/?domain=%E6%80%A7%E8%83%BD%E5%B7%A5%E7%A8%8B%EF%BC%9A%E4%BB%8E%E7%94%A8%E6%88%B7%E7%AD%89%E5%BE%85%E5%88%B0%E8%B5%84%E6%BA%90%E7%93%B6%E9%A2%88"),
    ("graph", "/?view=graph"),
    ("pano-matrix", "/?view=panorama"),
    ("pano-stack", "/?view=panorama&tab=stack"),
]
WIDTHS = [375, 768, 1024, 1440]

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    for theme in ("light", "dark"):
        for name, url in TARGETS:
            for width in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                page = ctx.new_page()
                page.goto(f"{BASE}{url}&theme={theme}" if "?" in url else f"{BASE}{url}?theme={theme}",
                          wait_until="load", timeout=30000)
                page.wait_for_timeout(1500)
                fn = f"{name}-{theme}-{width}.png"
                page.screenshot(path=os.path.join(OUT, fn), full_page=True)
                print("shot:", fn)
                ctx.close()
    browser.close()
