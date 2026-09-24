from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"

with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))

    for path, sid, name in [("/projects", "proj-search", "项目页"), ("/learn", "learn-search", "学习中心")]:
        pg.goto(BASE + path, wait_until="domcontentloaded")
        pg.wait_for_timeout(2000)
        m = pg.evaluate("""(sid) => {
          const i = document.getElementById(sid);
          if (!i) return {mounted: false};
          const cs = getComputedStyle(i);
          const r = i.getBoundingClientRect();
          return {mounted: true, w: Math.round(r.width), h: Math.round(r.height),
                  ph: i.placeholder, hasIcon: !!document.querySelector('#'+sid.replace('-search','-search'))?.closest('.tk-search')?.querySelector('svg')};
        }""", sid)
        print(f"=== {name} ({path}) ===")
        print(f"  {m}")
        pg.screenshot(path=f"{S}/80_{sid}.png")

        # 回车跳转
        pg.fill(f"#{sid}", "RAG")
        pg.press(f"#{sid}", "Enter")
        pg.wait_for_timeout(2500)
        print(f"  跳转后 url: {pg.url[:70]}")
        print(f"  结果条数: {pg.evaluate('() => document.querySelectorAll(\".note-row\").length')}")
        print(f"  搜索框回填: {pg.evaluate('() => (document.querySelector(\"#search\")||{}).value')}")

    print("errors:", errs[:5] if errs else "none")
    b.close()
