from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"
ART = "/?path=" + "工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/AI辅助研发必须形成证据闭环.md"

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    pg.goto(BASE + ART, wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)

    m = pg.evaluate("""() => {
      const dom = document.querySelector('#domains .tk-domain.active');
      const sub = document.querySelector('.tk-subtopic[aria-current="page"]');
      const nav = document.querySelector('.tk-nav a[aria-current="page"]');
      const cs = e => e ? getComputedStyle(e) : null;
      return {
        domain_active: dom ? dom.dataset.domain : 'none',
        domain_shadow: cs(dom) ? cs(dom).boxShadow : 'none',
        domain_border: cs(dom) ? cs(dom).borderLeftWidth + ' ' + cs(dom).borderLeftColor : 'none',
        subtopic: sub ? sub.textContent.trim() : 'none',
        subtopic_shadow: cs(sub) ? cs(sub).boxShadow : 'none',
        nav_current: nav ? nav.textContent.trim() : 'none',
        nav_shadow: cs(nav) ? cs(nav).boxShadow : 'none',
        expanded_count: document.querySelectorAll('.tk-domain[aria-expanded="true"]').length,
      };
    }""")
    print("=== 文章页导航态 ===")
    for k, v in m.items():
        print(f"  {k}: {v}")
    pg.screenshot(path=f"{S}/50_article_nav.png")
    # 侧栏局部放大
    pg.locator("#tk-sidebar").screenshot(path=f"{S}/51_sidebar_zoom.png")

    # 对比：目录页（原高亮场景）没被破坏
    pg.goto(BASE + "/?domain=" + "AI 系统工程：从模型能力到生产能力", wait_until="domcontentloaded")
    pg.wait_for_timeout(3200)
    print("=== 目录页（回归）===")
    print("  展开:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain[aria-expanded=\"true\"]')].map(r=>r.dataset.domain)"))
    print("  active:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))
    pg.screenshot(path=f"{S}/52_directory.png")

    # 文章内跳转：换一篇同域不同主题
    pg.goto(BASE + ART, wait_until="domcontentloaded")
    pg.wait_for_timeout(3200)
    pg.evaluate("""() => { const a=[...document.querySelectorAll('.tk-subtopic')].find(x=>!x.hasAttribute('aria-current')&&!x.classList.contains('tk-subtopic--all')); if(a) a.click(); }""")
    pg.wait_for_timeout(2500)
    print("=== 点侧栏其它主题 ===")
    print("  url:", pg.url[:90])
    print("  active:", pg.evaluate("() => [...document.querySelectorAll('.tk-domain.active')].map(r=>r.dataset.domain)"))

    print("errors:", errs[:5] if errs else "none")
    b.close()
