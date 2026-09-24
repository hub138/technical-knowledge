from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
SHOTS = "/data/code/AIagent/audit-shots"
OUT = []


def log(n, v):
    OUT.append(f"{n}: {v}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)

    page.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    log("console_errors", errs[:3] if errs else "none")
    log("h1", page.locator("h1").first.inner_text())
    log("rd_jump_links", page.locator(".rd-jump a").count())
    log("jump_current", page.evaluate("""() => { const a=document.querySelector('.rd-jump a[aria-current=page]'); return a?a.textContent.trim():'none'; }"""))
    log("section_h2s", page.evaluate("() => [...document.querySelectorAll('.rd-sec h2')].map(e=>e.textContent).join(' | ')"))
    log("progress_rows", page.locator("#progress-body a").count())
    log("lp_items", page.locator("#lp-sections .lp-item").count())
    log("lp_stages", page.locator(".lp-stage").count())
    log("read_minutes", "分钟" in page.locator("#lp-sections").inner_text())
    log("progress_label", page.evaluate("() => document.getElementById('lp-progress-label').textContent"))

    boxes = page.locator("#lp-sections .lp-check")
    for i in range(min(3, boxes.count())):
        b = page.locator("#lp-sections .lp-check").nth(i)
        b.scroll_into_view_if_needed()
        b.click()
        page.wait_for_timeout(400)
    page.wait_for_timeout(1000)
    log("after_check_label", page.evaluate("() => document.getElementById('lp-progress-label').textContent"))
    log("sync_to_reading", "已读" in page.locator("#progress-body").inner_text())

    page.click("#lp-hide-learned")
    page.wait_for_timeout(1000)
    log("hide_learned_items", page.locator("#lp-sections .lp-item").count())
    page.click("#lp-hide-learned")
    page.wait_for_timeout(800)

    page.select_option("#lp-domain", index=2)
    page.wait_for_timeout(1500)
    log("domain2_items", page.locator("#lp-sections .lp-item").count())

    log("subnav_font_size", page.evaluate("""() => { const a=document.querySelector('.tk-subnav-inline'); return a?getComputedStyle(a).fontSize:'none'; }"""))
    log("subnav_min_height", page.evaluate("""() => { const a=document.querySelector('.tk-subnav-inline'); return a?getComputedStyle(a).minHeight:'none'; }"""))
    log("hscroll_1440", page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    page.screenshot(path=SHOTS + "/rd_final_desktop.png", full_page=True)

    page.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    page.wait_for_timeout(1000)
    page.screenshot(path=SHOTS + "/rd_final_dark.png", full_page=True)
    log("dark_bg", page.evaluate("() => getComputedStyle(document.body).backgroundColor"))

    ctx2 = browser.new_context(viewport={"width": 390, "height": 844})
    p2 = ctx2.new_page()
    p2.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    p2.wait_for_timeout(2500)
    log("hscroll_390", p2.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth"))
    log("mobile_items", p2.locator("#lp-sections .lp-item").count())
    p2.screenshot(path=SHOTS + "/rd_final_mobile.png", full_page=True)

    ctx3 = browser.new_context(viewport={"width": 1440, "height": 900})
    p3 = ctx3.new_page()
    p3.goto(BASE + "/", wait_until="domcontentloaded")
    p3.wait_for_timeout(2500)
    p3.evaluate("() => { const b=document.querySelector('[data-view=panorama]'); if(b) b.click(); }")
    p3.wait_for_timeout(1500)
    p3.evaluate("() => { const e=document.getElementById('pano-tab-mine'); if(e) e.click(); }")
    p3.wait_for_timeout(2000)
    log("index_mine_jump", p3.url.split("?")[0])

    browser.close()

print("=== SUMMARY ===")
for l in OUT:
    print(l)
