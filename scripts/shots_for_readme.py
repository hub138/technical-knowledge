"""README 成套截图采集（2026-09-25）。

README 原来只有 4 张（首页/文章/图谱/暗色），漏掉全景、进度、论文、
来源、学习中心。这里一次采齐，统一 1440x900（16:10，README 里显示不裁切）。
第三方 CDN 图需等 5s 否则误判空白（knowledge-site-dev 已记录）。
"""
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
OUT = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/docs/shots"
NOTE = ("工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/"
        "NUMA让跨槽访问付出带宽与延迟代价.md")

SHOTS = [
    ("home", "/", False),
    ("note", "/?path=" + NOTE.replace(" ", "%20"), False),
    ("graph", "/?view=graph", False),
    ("panorama", "/?view=panorama", False),
    ("progress", "/?view=progress", False),
    ("papers", "/papers", False),
    ("sources", "/sources", False),
    ("learn", "/learn", False),
    ("projects", "/projects", False),
    ("home-dark", "/", True),
    ("note-dark", "/?path=" + NOTE.replace(" ", "%20"), True),
    ("graph-dark", "/?view=graph", True),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    for name, path, dark in SHOTS:
        pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        pg.goto(BASE + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        if dark:
            pg.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
            pg.wait_for_timeout(1500)
        pg.wait_for_timeout(5000)
        pg.evaluate("() => window.scrollTo(0,0)")
        pg.wait_for_timeout(800)
        pg.screenshot(path=f"{OUT}/{name}.png")
        print("shot:", name)
        pg.close()
    b.close()
