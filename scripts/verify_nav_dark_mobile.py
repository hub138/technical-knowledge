from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"
ART = "/?path=" + "工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/AI辅助研发必须形成证据闭环.md"

with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []

    # 暗色
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + ART, wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    pg.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    pg.wait_for_timeout(1200)
    print("=== 暗色模式 ===")
    print("  domain active:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))
    print("  sub current:", pg.evaluate("() => [...document.querySelectorAll('.tk-subtopic[aria-current=\"page\"]')].map(a=>a.textContent.trim())"))
    print("  domain shadow:", pg.evaluate("() => { const d=document.querySelector('.tk-domain.active'); return d?getComputedStyle(d).boxShadow.slice(0,60):'none' }"))
    pg.locator("#tk-sidebar").screenshot(path=f"{S}/70_sidebar_dark.png")

    # 移动端
    p2 = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    p2.goto(BASE + ART, wait_until="domcontentloaded")
    p2.wait_for_timeout(3500)
    print("=== 移动端 ===")
    print("  hscroll:", p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    print("  domain active:", p2.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))
    p2.screenshot(path=f"{S}/71_mobile.png")

    # 返回首页后不应残留文章的当前态
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    print("=== 首页（回归）===")
    print("  domain active:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))
    print("  sub current:", pg.evaluate("() => [...document.querySelectorAll('.tk-subtopic[aria-current=\"page\"]')].map(a=>a.textContent.trim())"))

    # 全景视图
    pg.goto(BASE + "/?view=panorama", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    print("=== 全景 ===")
    print("  domain active:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))

    print("errors:", errs[:5] if errs else "none")
    b.close()
