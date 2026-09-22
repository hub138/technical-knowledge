import json
from playwright.sync_api import sync_playwright
import urllib.parse

# 渲染验证：逐页确认正文真的渲染出来（非骨架屏/加载中），
# 同时收集 pageerror。语法兼容已由静态扫描与 Node 解析验证保证。

ARTICLE = urllib.parse.quote("工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理.md")
pages = [
    ("home", "/"),
    ("article", "/?path=" + ARTICLE),
    ("panorama", "/?view=panorama"),
    ("papers", "/papers"),
    ("projects", "/projects"),
]

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    for name, path in pages:
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)[:120]))
        pg.goto("http://127.0.0.1:28788" + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        st = pg.evaluate("""() => ({
          bodyChars: document.body.innerText.length,
          hasSkeleton: !!document.querySelector('.skeleton'),
          sample: document.body.innerText.slice(0, 60).replace(/\\n/g, ' '),
        })""")
        print(name, json.dumps(st, ensure_ascii=False), "errors:", errors[:2])
        pg.close()
    b.close()
