from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/audit-shots/verify-round"
OUT = []


def log(n, v):
    OUT.append(f"{n}: {v}")


with sync_playwright() as p:
    b = p.chromium.launch()

    # 1. 侧栏展开态（知识全景 + 项目与教学）
    c = b.new_context(viewport={"width": 1440, "height": 900})
    pg = c.new_page()
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    pg.locator('.tk-subnav-toggle[data-subgroup="panorama"]').click()
    pg.wait_for_timeout(600)
    pg.locator('.tk-subnav-toggle[data-subgroup="projects"]').click()
    pg.wait_for_timeout(800)
    pg.screenshot(path=f"{S}/01_nav_expanded.png")
    log("subnav_font", pg.evaluate("() => getComputedStyle(document.querySelector('.tk-subnav-inline')).fontSize"))
    log("subnav_h", pg.evaluate("() => getComputedStyle(document.querySelector('.tk-subnav-inline')).minHeight"))
    log("parent_font", pg.evaluate("""() => {
        const a=[...document.querySelectorAll('.tk-nav a')].find(x=>x.querySelector('.tk-nav-icon') && !x.classList.contains('tk-subnav-inline'));
        return a?getComputedStyle(a).fontSize:'none';
    }"""))
    log("subnav_items", pg.evaluate("() => [...document.querySelectorAll('.tk-subnav-inline')].map(a=>a.textContent.trim()).join(' | ')"))

    # 2. 侧栏收起态
    pg.locator('.tk-subnav-toggle[data-subgroup="panorama"]').click()
    pg.wait_for_timeout(500)
    pg.locator('.tk-subnav-toggle[data-subgroup="projects"]').click()
    pg.wait_for_timeout(600)
    pg.screenshot(path=f"{S}/02_nav_collapsed.png")
    log("collapsed_hidden", pg.evaluate("""() => [...document.querySelectorAll('.tk-subnav-group')].every(g=>g.hidden)"""))

    # 3. 我的阅读（默认锚点）
    pg.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=f"{S}/03_reading_top.png")
    log("h1_reading", pg.locator("h1").first.inner_text())
    log("jump_cur_reading", pg.evaluate("() => { const a=document.querySelector('.rd-jump a[aria-current=page]'); return a?a.textContent.trim():'none'; }"))
    log("nav_cur_reading", pg.evaluate("() => { const a=document.querySelector('.tk-subnav-inline[aria-current=page]'); return a?a.textContent.trim():'none'; }"))
    log("rd_top_offset", pg.evaluate("() => Math.round(document.getElementById('rd-reading').getBoundingClientRect().top)"))
    log("h1_to_h2_gap", pg.evaluate("""() => {
        const h1=document.querySelector('h1'); const h2=document.querySelector('#rd-reading h2');
        return Math.round(h2.getBoundingClientRect().top - h1.getBoundingClientRect().bottom);
    }"""))

    # 4. 我的阅读 首屏完整
    pg.screenshot(path=f"{S}/04_reading_full.png", full_page=True)

    # 5. 学习路线（锚点）
    pg.goto(BASE + "/panorama/reading#rd-path", wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    pg.screenshot(path=f"{S}/05_path_anchor.png")
    log("h1_path", pg.locator("h1").first.inner_text())
    log("jump_cur_path", pg.evaluate("() => { const a=document.querySelector('.rd-jump a[aria-current=page]'); return a?a.textContent.trim():'none'; }"))
    log("nav_cur_path", pg.evaluate("() => { const a=document.querySelector('.tk-subnav-inline[aria-current=page]'); return a?a.textContent.trim():'none'; }"))
    log("scroll_y_path", pg.evaluate("() => Math.round(window.scrollY)"))
    log("rd_path_top", pg.evaluate("() => Math.round(document.getElementById('rd-path').getBoundingClientRect().top)"))

    # 6. 学习路线 全页
    pg.screenshot(path=f"{S}/06_path_full.png", full_page=True)

    # 7. 勾选后状态
    pg.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    n_all = pg.locator("#lp-sections .lp-check").count()
    for i in range(min(4, n_all)):
        bx = pg.locator("#lp-sections .lp-check").nth(i)
        bx.scroll_into_view_if_needed()
        bx.click()
        pg.wait_for_timeout(350)
    pg.wait_for_timeout(1200)
    pg.screenshot(path=f"{S}/07_checked_sync.png", full_page=True)
    log("label_after", pg.evaluate("() => document.getElementById('lp-progress-label').textContent"))
    log("reading_has_learned", "已读" in pg.locator("#progress-body").inner_text())

    # 8. 段完成徽标：把余下的一并勾满
    n_left = pg.locator("#lp-sections .lp-check").count()
    for i in range(n_left):
        bx = pg.locator("#lp-sections .lp-check").nth(i)
        bx.scroll_into_view_if_needed()
        bx.click()
        pg.wait_for_timeout(300)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{S}/08_stage_done.png", full_page=True)
    log("done_badge", pg.evaluate("() => { const e=document.querySelector('.lp-stage-done'); return e?e.textContent:'none'; }"))
    log("is_done", pg.evaluate("() => !!document.querySelector('.lp-stage.is-done')"))
    log("label_full", pg.evaluate("() => document.getElementById('lp-progress-label').textContent"))

    # 9. 隐藏已读
    pg.click("#lp-hide-learned")
    pg.wait_for_timeout(1200)
    pg.screenshot(path=f"{S}/09_hide_learned.png", full_page=True)
    log("items_hide", pg.locator("#lp-sections .lp-item").count())
    log("all_read_ph", pg.evaluate("() => { const e=document.querySelector('.lp-all-read'); return e?e.textContent:'none'; }"))

    # 10. 暗色
    c2 = b.new_context(viewport={"width": 1440, "height": 900})
    p2 = c2.new_page()
    p2.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p2.wait_for_timeout(3000)
    p2.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    p2.wait_for_timeout(1000)
    p2.screenshot(path=f"{S}/10_dark.png", full_page=True)
    log("dark_bg", p2.evaluate("() => getComputedStyle(document.body).backgroundColor"))
    log("dark_jump_cur_bg", p2.evaluate("() => { const a=document.querySelector('.rd-jump a[aria-current=page]'); return a?getComputedStyle(a).backgroundColor:'none'; }"))

    # 11. 移动端
    c3 = b.new_context(viewport={"width": 390, "height": 844})
    p3 = c3.new_page()
    p3.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p3.wait_for_timeout(3000)
    p3.screenshot(path=f"{S}/11_mobile.png", full_page=True)
    log("hscroll_390", p3.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    log("mobile_jump_wrap", p3.evaluate("() => document.querySelector('.rd-jump').getBoundingClientRect().height > 40"))

    # 12. 200% 缩放
    c4 = b.new_context(viewport={"width": 720, "height": 900})
    p4 = c4.new_page()
    p4.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p4.wait_for_timeout(3000)
    p4.screenshot(path=f"{S}/12_zoom200.png", full_page=True)
    log("hscroll_720", p4.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))

    # 13. 矮视口
    c5 = b.new_context(viewport={"width": 740, "height": 360})
    p5 = c5.new_page()
    p5.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p5.wait_for_timeout(3000)
    p5.screenshot(path=f"{S}/13_short.png")
    log("hscroll_740", p5.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))

    # 14. 键盘 focus
    c6 = b.new_context(viewport={"width": 1440, "height": 900})
    p6 = c6.new_page()
    p6.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p6.wait_for_timeout(2500)
    for _ in range(6):
        p6.keyboard.press("Tab")
        p6.wait_for_timeout(150)
    p6.screenshot(path=f"{S}/14_focus.png")
    log("focus_visible", p6.evaluate("""() => {
        const e=document.activeElement; const s=getComputedStyle(e);
        return e.tagName + '|' + (s.outlineStyle!=='none' || s.boxShadow!=='none');
    }"""))

    b.close()

print("=== SUMMARY ===")
for l in OUT:
    print(l)
