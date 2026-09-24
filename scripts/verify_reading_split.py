from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/split-round"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # 先去路线页，让它写入 tk.learn-path.last
    pg.goto(BASE + "/panorama/path", wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    print("=== 路线页 ===")
    print("  主题:", pg.evaluate("() => document.getElementById('lp-topic').value"))
    print("  last:", pg.evaluate("() => localStorage.getItem('tk.learn-path.last')"))
    print("  分区数:", pg.evaluate("() => document.querySelectorAll('#lp-sections > *').length"))
    print("  区块标题:", pg.evaluate("() => [...document.querySelectorAll('#lp-sections h3')].slice(0,6).map(e=>e.textContent.trim())"))
    pg.screenshot(path=f"{S}/20_path_top.png")
    pg.screenshot(path=f"{S}/20_path_full.png", full_page=True)

    # 勾选一篇，让进度有数据
    clicked = pg.evaluate("""() => {
      const c = document.querySelector('.pg-check, .lp-check, #lp-sections button');
      if(!c) return 'no button';
      c.click(); return c.className;
    }""")
    print("  勾选:", clicked)
    pg.wait_for_timeout(1200)
    print("  进度标签:", pg.evaluate("() => (document.getElementById('lp-progress-label')||{}).textContent || 'none'"))

    # 回到我的阅读，看路线卡
    pg.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    pg.wait_for_timeout(3200)
    print("=== 我的阅读（有路线进度后）===")
    m = pg.evaluate("""() => {
      const c = document.querySelector('.pg-route');
      return {
        route_card: !!c,
        topic: (document.querySelector('.pg-route-topic')||{}).textContent || 'none',
        num: (document.querySelector('.pg-route-num')||{}).textContent || 'none',
        next: (document.querySelector('.pg-route-next')||{}).textContent || 'none',
        link: (document.querySelector('.pg-route-link')||{}).getAttribute ? document.querySelector('.pg-route-link').getAttribute('href') : 'none',
        overall_before: document.querySelectorAll('.pg-overall').length,
        route_index: c ? [...document.querySelectorAll('#progress-body > *')].findIndex(e=>e.classList.contains('pg-route')) : -1,
        total_children: document.querySelectorAll('#progress-body > *').length,
      };
    }""")
    for k, v in m.items():
        print(f"  {k}: {v}")
    pg.screenshot(path=f"{S}/21_reading_route.png")
    pg.screenshot(path=f"{S}/21_reading_full.png", full_page=True)

    # 移动端
    c2 = b.new_context(viewport={"width": 390, "height": 844})
    p2 = c2.new_page()
    p2.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p2.wait_for_timeout(3000)
    print("=== 移动端阅读页 ===")
    print("  h1_top:", p2.evaluate("() => Math.round(document.querySelector('h1').getBoundingClientRect().top)"))
    print("  hscroll:", p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    p2.screenshot(path=f"{S}/22_mobile_reading.png")
    p2.goto(BASE + "/panorama/path", wait_until="domcontentloaded")
    p2.wait_for_timeout(3000)
    print("  路线页 h1_top:", p2.evaluate("() => Math.round(document.querySelector('h1').getBoundingClientRect().top)"))
    print("  路线页 hscroll:", p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    p2.screenshot(path=f"{S}/23_mobile_path.png")

    # 暗色
    p3 = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    p3.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p3.wait_for_timeout(3000)
    p3.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    p3.wait_for_timeout(1000)
    p3.screenshot(path=f"{S}/24_dark_reading.png")

    print("errors:", errs[:5] if errs else "none")
    b.close()
