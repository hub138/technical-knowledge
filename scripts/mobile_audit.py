import json
import urllib.parse
from playwright.sync_api import sync_playwright

ARTICLE = urllib.parse.quote(
    "工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理.md"
)
PAGES = [
    ("home", "/"),
    ("article", "/?path=" + ARTICLE),
    ("panorama", "/?view=panorama"),
    ("papers", "/papers"),
    ("projects", "/projects"),
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
    )
    for name, path in PAGES:
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)[:120]))
        pg.goto("http://127.0.0.1:28788" + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(7000)
        st = pg.evaluate(
            """() => {
              const overflow = [];
              const w = document.documentElement.clientWidth;
              document.querySelectorAll('body *').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 1 && (r.right > w + 1 || r.left < -1)) {
                  const cs = getComputedStyle(el);
                  if (cs.position !== 'fixed' || r.left < -1) {
                    overflow.push(el.tagName + '.' + String(el.className).slice(0, 40) + ' right=' + Math.round(r.right) + ' left=' + Math.round(r.left));
                  }
                }
              });
              return {
                chars: document.body.innerText.length,
                scrollW: document.documentElement.scrollWidth,
                clientW: w,
                overflowCount: overflow.length,
                overflowTop: overflow.slice(0, 6),
                skeleton: document.querySelectorAll('.skeleton').length,
                sample: document.body.innerText.slice(0, 50).replace(/\\n/g, ' '),
              };
            }"""
        )
        pg.screenshot(path="audit-shots/mobile_" + name + ".png", full_page=False)
        print(name, json.dumps(st, ensure_ascii=False))
        print("   errors:", errors[:2])
        pg.close()
    b.close()
print("shots saved to audit-shots/")
