# 最小复现：新开 about:blank 注入同样的 DOM 结构（aside 在 main 之前、
# main 首元素是 skip link），按 Tab 看首步落点是否受 visibility/opacity
# 或 tabindex 顺序影响。分离"页面自身逻辑"与"浏览器 Tab 顺序规则"。
import json

from playwright.sync_api import sync_playwright

CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"

HTML = """
<!doctype html><html><body>
<aside class="tk-sidebar"><a href="/a">nav1</a></aside>
<main class="main"><a class="skip-link" href="#reader-body">跳到正文</a><header class="topbar"><input type="search"></header>
<article id="reader-body" tabindex="-1">正文</article></main>
<style>
.skip-link{position:fixed;top:64px;left:16px;opacity:0;pointer-events:none;transform:translateY(-12px)}
.skip-link:focus-visible{opacity:1;pointer-events:auto;transform:translateY(0)}
</style>
</body></html>
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    page = browser.new_page()
    page.set_content(HTML)
    page.keyboard.press("Tab")
    first = page.evaluate("() => document.activeElement.className + ' | ' + document.activeElement.textContent")
    # 第二个 Tab
    page.keyboard.press("Tab")
    second = page.evaluate("() => document.activeElement.className + ' | ' + document.activeElement.textContent")
    print(json.dumps({"tab1": first, "tab2": second}, ensure_ascii=False))
    browser.close()
