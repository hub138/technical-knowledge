# 空态修复验证：无效领域触发空态分支（无搜索词）
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "views")
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    for theme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{BASE}/?domain=%E7%B3%BB%E7%BB%9F%E8%AE%BE%E8%AE%A1&theme={theme}",
                  wait_until="load", timeout=30000)
        page.wait_for_timeout(1200)
        fn = f"empty-state-{theme}.png"
        page.screenshot(path=os.path.join(OUT, fn))
        print("shot:", fn)
        ctx.close()
    browser.close()
