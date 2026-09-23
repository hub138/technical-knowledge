# 量测文章页真实渲染指标：行宽、横向溢出、目录栏、对比度。
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots")

NOTE = "/?path=" + "/".join(
    ["%E7%9F%A5%E8%AF%86%E5%BA%93%E7%AE%A1%E7%90%86", "%E5%BD%92%E6%A1%A3",
     "%E6%9B%B4%E6%96%B0%E5%80%99%E9%80%89", "%E5%BE%85%E6%A0%B8%E9%AA%8C%E5%86%85%E5%AE%B9.md"]
)

JS = """
() => {
  const body = document.querySelector('.reader-body');
  const cs = body ? getComputedStyle(body) : null;
  const widest = [...document.querySelectorAll('.reader-body *')].map(el => {
    const r = el.getBoundingClientRect();
    return {tag: el.tagName, cls: el.className && String(el.className).slice(0,30), w: +r.width.toFixed(1), right: +r.right.toFixed(1)};
  }).sort((a,b)=>b.w-a.w).slice(0,6);
  const toc = document.querySelector('#reader-toc');
  const tocInfo = toc ? {hidden: getComputedStyle(toc).display === 'none',
                         text: toc.innerText.replace(/\\n+/g,' | ').slice(0,80)} : null;
  const ink = cs ? cs.color : '';
  const panel = getComputedStyle(document.querySelector('.tk-shell') || body).backgroundColor;
  return {
    bodyWidth: body ? +body.getBoundingClientRect().width.toFixed(1) : 0,
    fontSize: cs ? cs.fontSize : '',
    lineHeight: cs ? cs.lineHeight : '',
    color: ink, panelBg: panel,
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
    overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    widest, tocInfo,
  };
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    results = {}
    for width in (375, 1440):
        page = browser.new_context(viewport={"width": width, "height": 900}).new_page()
        page.goto(BASE + NOTE + "&theme=light", wait_until="load", timeout=30000)
        page.wait_for_timeout(1200)
        results[width] = page.evaluate(JS)
        page.close()
    out = os.path.join(OUT, "note-metrics.json")
    with open(out, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    for width, data in results.items():
        print(f"== {width} ==")
        for key in ("bodyWidth", "fontSize", "lineHeight", "color", "scrollW", "clientW", "overflowX", "tocInfo"):
            print(f"  {key}: {data[key]}")
    print("widest@1440:", json.dumps(results[1440]["widest"], ensure_ascii=False))
    browser.close()
