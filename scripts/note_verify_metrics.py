# 文章页程序化终检：横向溢出 / 占位符残留 / 空目录栏 / iframe 容器
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
PAGES = {
    "longest": "知识库管理/归档/知识更新方法论.md",
    "code-table": "知识库管理/方法/知识缺口怎么补——图谱关系槽与补强工作流.md",
    "clipping": "Clippings/自学两个月Agent，复盘思考.md",
    "shortest": "知识库管理/归档/更新候选/待核验内容.md",
}

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    for name, rel in PAGES.items():
        path_param = urllib.parse.quote(rel, safe="/")
        for width in (375, 1440):
            ctx = browser.new_context(viewport={"width": width, "height": 900})
            page = ctx.new_page()
            page.goto(f"{BASE}/?path={path_param}", wait_until="load", timeout=30000)
            page.wait_for_timeout(1200)
            overflow = page.evaluate(
                "document.scrollingElement.scrollWidth - document.documentElement.clientWidth"
            )
            body_text = page.evaluate("document.body.innerText")
            has_placeholder = "{{" in body_text
            toc_visible = page.evaluate(
                """() => { const t = document.getElementById('reader-toc');
                     return t ? !t.hidden && t.innerText.trim().length > 0 : false; }"""
            )
            iframe_box = page.evaluate(
                """() => { const f = document.querySelector('.reader-body iframe');
                     if (!f) return null; const r = f.getBoundingClientRect();
                     return {w: Math.round(r.width), h: Math.round(r.height)}; }"""
            )
            print(f"{name}-{width}: overflow={overflow}px placeholder={has_placeholder} "
                  f"toc={toc_visible} iframe={iframe_box}")
            ctx.close()
    browser.close()
