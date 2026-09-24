from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    navs = []
    page.on("framenavigated", lambda f: navs.append(f.url) if f == page.main_frame else None)

    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    print("toggle_box:", page.locator('.tk-subnav-toggle[data-subgroup="panorama"]').bounding_box())
    print("row_box:", page.locator('.tk-nav-row').first.bounding_box())

    print("=== click 整行中间（非箭头处） ===")
    expanded_before = page.locator('.tk-subnav-toggle[data-subgroup="panorama"]').get_attribute("aria-expanded")
    print("expanded_before:", expanded_before)
    box = page.locator('.tk-nav-row').first.bounding_box()
    page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
    page.wait_for_timeout(1200)
    print("expanded_after_rowclick:", page.locator('.tk-subnav-toggle[data-subgroup="panorama"]').get_attribute("aria-expanded"))
    print("navs_after_rowclick:", len(navs))

    print("=== 组内总览入口 ===")
    print("overview_exists:", page.locator('.tk-subnav-overview').count())
    print("overview_text:", page.locator('.tk-subnav-overview').first.inner_text() if page.locator('.tk-subnav-overview').count() else "none")

    print("=== 点系统阅读路线子项 ===")
    navs.clear()
    page.locator('.tk-subnav-inline[href="/panorama/path"]').first.click()
    page.wait_for_timeout(2500)
    print("url:", page.url)
    print("navs:", len(navs))
    print("current_page_highlight:", page.evaluate("""() => {
        const a = document.querySelector('a[aria-current="page"]');
        return a ? a.textContent.trim() : 'none';
    }"""))
    print("h1:", page.locator("h1").first.inner_text())
    print("lp_stages:", page.evaluate("() => document.querySelectorAll('.lp-stage').length"))

    print("=== 点我的阅读子项 ===")
    page.goto(BASE + "/panorama/reading", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("current_page_highlight:", page.evaluate("""() => {
        const a = document.querySelector('a[aria-current="page"]');
        return a ? a.textContent.trim() : 'none';
    }"""))
    print("h1:", page.locator("h1").first.inner_text())
    print("h1_top:", page.evaluate("() => Math.round(document.querySelector('h1').getBoundingClientRect().top)"))
    print("first_section_h2:", page.locator(".rd-sec h2").first.inner_text())
    print("route_card:", page.evaluate("() => !!document.querySelector('.pg-route')"))
    browser.close()
