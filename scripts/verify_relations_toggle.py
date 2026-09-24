from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"
NOTE = "工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/NUMA让跨槽访问付出带宽与延迟代价.md"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.goto(BASE + "/?path=" + NOTE.replace(" ", "%20"), wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)

    st = "() => document.getElementById('reader-relations').classList.contains('collapsed')"
    print("初始 collapsed:", pg.evaluate(st))

    # 点折叠按钮
    pg.locator(".relation-collapse").click()
    pg.wait_for_timeout(700)
    print("点按钮后 collapsed:", pg.evaluate(st))

    # 点标题行
    pg.locator(".article-relations-head").click()
    pg.wait_for_timeout(700)
    print("点标题行后 collapsed:", pg.evaluate(st))

    # 再展开，确认顺序不变
    pg.locator(".article-relations-head").click()
    pg.wait_for_timeout(700)
    print("展开后 collapsed:", pg.evaluate(st))
    print("顺序:", pg.evaluate("() => [...document.querySelector('.reader-maincol').children].map(c=>c.id)"))

    # 切到另一篇，确认记忆折叠态
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(500)
    pg.screenshot(path=f"{S}/94_relations_expanded.png")
    b.close()
