# 全站截图审查脚本：每个页面 × 深浅主题各一张全页截图。
# 页面清单与 view/hash 取自 index.html 的 SPA 路由。
import os
import urllib.parse

SITE_PASSWORD = os.environ["KNOWLEDGE_SITE_PASSWORD"]

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots")
os.makedirs(OUT, exist_ok=True)

DEFECT = urllib.parse.quote("缺陷分析：从个案到体系", safe="")
NOTE = urllib.parse.quote(
    "工程知识/缺陷分析：从个案到体系/正确性/案例十六：数据被自己人删掉——entry log 头里的假账.md",
    safe="/",
)

PAGES = [
    ("home", "/"),
    ("insights", "/insights"),
    ("panorama-matrix", "/?view=panorama"),
    ("panorama-stack", "/?view=panorama&tab=stack"),
    ("domain-defect", f"/?domain={DEFECT}"),
    ("note", f"/?path={NOTE}"),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    # 站点有访问门禁：只有被重定向到登录页时才需要登录换 cookie。
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", SITE_PASSWORD)
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)
    page.close()
    for theme in ("light", "dark"):
        sep = "&" if "?" in BASE else "?"
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for name, p in PAGES:
            url = BASE + p + ("&" if "?" in p else "?") + "theme=" + theme
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(1200)
            page.screenshot(path=os.path.join(OUT, f"{name}-{theme}.png"), full_page=True)
            print("shot:", f"{name}-{theme}.png")
        ctx.close()
    browser.close()
