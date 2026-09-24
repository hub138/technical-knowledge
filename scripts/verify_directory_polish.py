from urllib.parse import quote
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/polish-round"

PAGES = [
    ("all", BASE + "/?domain=all"),
    ("domain", BASE + "/?domain=" + quote("数据系统：在并发与故障中保存事实")),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    for name, url in PAGES:
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(3200)
        m = pg.evaluate("""() => {
            const row=document.querySelector('.note-row');
            if(!row)return {err:'no row'};
            const h3=row.querySelector('h3'), p=row.querySelector('p'), pa=row.querySelector('.path');
            const rail=document.querySelector('.dir-rail');
            const rh=document.querySelector('.dir-rail .rail-head');
            const h2=document.querySelector('.directory-head h2');
            const cs=e=>e?getComputedStyle(e):null;
            return {
              h3_fs: cs(h3).fontSize, p_fs: cs(p).fontSize,
              path_text: pa?pa.textContent:'none',
              rail_head: rh?rh.textContent:'none',
              rh_top: rh?Math.round(rh.getBoundingClientRect().top):'none',
              h2_top: h2?Math.round(h2.getBoundingClientRect().top):'none',
              rows: document.querySelectorAll('.note-row').length,
              sections: document.querySelectorAll('.topic-section').length,
            };
        }""")
        print(f"--- {name} ---")
        for k, v in m.items():
            print(f"  {k}: {v}")
        pg.evaluate("() => document.getElementById('directory').scrollIntoView()")
        pg.wait_for_timeout(600)
        pg.screenshot(path=f"{S}/01_{name}.png")

    # 首页
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=f"{S}/02_home.png")
    print("--- home --- hscroll:", pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))

    # 移动端主题页
    c2 = b.new_context(viewport={"width": 390, "height": 844})
    p2 = c2.new_page()
    p2.goto(BASE + "/?domain=" + quote("数据系统：在并发与故障中保存事实") + "&topic=" + quote("事务与存储"), wait_until="domcontentloaded")
    p2.wait_for_timeout(3200)
    p2.evaluate("() => document.getElementById('directory').scrollIntoView()")
    p2.wait_for_timeout(600)
    p2.screenshot(path=f"{S}/03_mobile_topic.png")
    print("--- mobile --- hscroll:", p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    print("mobile h3:", p2.evaluate("() => { const h=document.querySelector('.note-row h3'); return h?getComputedStyle(h).fontSize:'none'; }"))

    # 暗色
    p2b = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    p2b.goto(BASE + "/?domain=" + quote("数据系统：在并发与故障中保存事实") + "&topic=" + quote("事务与存储"), wait_until="domcontentloaded")
    p2b.wait_for_timeout(3200)
    p2b.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    p2b.wait_for_timeout(1000)
    p2b.evaluate("() => document.getElementById('directory').scrollIntoView()")
    p2b.wait_for_timeout(600)
    p2b.screenshot(path=f"{S}/04_dark_topic.png")
    print("dark note p color:", p2b.evaluate("() => { const p=document.querySelector('.note-row p'); return p?getComputedStyle(p).color:'none'; }"))

    print("errors:", errs[:3] if errs else "none")
    b.close()
