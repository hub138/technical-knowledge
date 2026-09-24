from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"

with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # 亮色截图
    for path, name in [("/projects", "proj"), ("/learn", "learn")]:
        pg.goto(BASE + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(2000)
        pg.locator(".hero").screenshot(path=f"{S}/81_{name}_hero.png")

    # 暗色
    pg.goto(BASE + "/learn", wait_until="domcontentloaded")
    pg.wait_for_timeout(1800)
    pg.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    pg.wait_for_timeout(1000)
    pg.locator(".hero").screenshot(path=f"{S}/82_learn_dark.png")

    # 移动端
    p2 = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    for path, name in [("/projects", "proj"), ("/learn", "learn")]:
        p2.goto(BASE + path, wait_until="domcontentloaded")
        p2.wait_for_timeout(2000)
        ov = p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        w = p2.evaluate("""(n) => { const i=document.getElementById(n); return i?Math.round(i.getBoundingClientRect().width):0 }""", f"{name}-search")
        print(f"  {name} 390px: 横滚={ov} 搜索宽={w}")

    # ⌘K 聚焦
    pg.goto(BASE + "/learn", wait_until="domcontentloaded")
    pg.wait_for_timeout(1800)
    pg.keyboard.press("Control+k")
    pg.wait_for_timeout(600)
    print("  ⌘K 聚焦:", pg.evaluate("() => document.activeElement && document.activeElement.id"))

    # 空词不应跳转
    pg.goto(BASE + "/learn", wait_until="domcontentloaded")
    pg.wait_for_timeout(1800)
    pg.press("#learn-search", "Enter")
    pg.wait_for_timeout(1200)
    print("  空词回车后 url:", pg.url[:50])

    print("errors:", errs[:5] if errs else "none")
    b.close()
