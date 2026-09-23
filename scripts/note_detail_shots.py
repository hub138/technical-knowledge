# 文章页局部细节审查截图：代表性样本 × 四宽度 × 深浅主题。
# 样本：最长文 / 含代码块表格文 / 含内联代码与图片文 / 最短归档文。
import os
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "note-detail")
os.makedirs(OUT, exist_ok=True)

PAGES = {
    "longest": "知识库管理/归档/知识更新方法论.md",
    "code-table": "知识库管理/方法/知识缺口怎么补——图谱关系槽与补强工作流.md",
    "clipping": "Clippings/自学两个月Agent，复盘思考.md",
    "shortest": "知识库管理/归档/更新候选/待核验内容.md",
}
WIDTHS = [375, 768, 1024, 1440]

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    for theme in ("light", "dark"):
        for name, rel in PAGES.items():
            path_param = urllib.parse.quote(rel, safe="/")
            for width in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                page = ctx.new_page()
                page.goto(
                    f"{BASE}/?path={path_param}&theme={theme}",
                    wait_until="load",
                    timeout=30000,
                )
                page.wait_for_timeout(1200)
                fn = f"{name}-{theme}-{width}.png"
                page.screenshot(path=os.path.join(OUT, fn), full_page=True)
                print("shot:", fn)
                ctx.close()
    browser.close()
