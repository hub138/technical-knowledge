from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
ROUTES = [
    ("/", "首页"),
    ("/learn", "学习中心"),
    ("/papers", "论文"),
    ("/sources", "来源"),
    ("/projects", "项目"),
    ("/insights", "访问与反馈"),
    ("/apps/panorama", "全景"),
    ("/apps/agent-evaluation", "Agent 评测"),
    ("/apps/engineer-evaluation", "工程师评测"),
    ("/apps/learning", "学习 App"),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    print(f"{'路由':<28}{'状态':<6}{'搜索框':<10}{'顶栏':<8}")
    print("-" * 56)
    for path, name in ROUTES:
        r = pg.goto(BASE + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(1200)
        has = pg.evaluate("() => !!document.querySelector('.tk-search input[type=\"search\"], input[type=\"search\"], .tk-search')")
        top = pg.evaluate("() => !!document.querySelector('.topbar')")
        print(f"{path:<28}{r.status if r else '?':<6}{'有' if has else '无':<10}{'有' if top else '无':<8}")
    b.close()
