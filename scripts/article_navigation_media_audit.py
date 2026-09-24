import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from note_verify_shots import DEFAULT_PATHS

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PATH = '工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能剖析与火焰图.md'
CALLOUT_PATH = '知识库管理/归档/来源/实践证据/AI研发迭代框架案例.md'


def open_article(page, base, path, theme):
    response = page.goto(f"{base}/?{urlencode({'path': path, 'theme': theme})}", wait_until='domcontentloaded')
    assert response.status == 200
    page.wait_for_function("() => document.querySelector('#reader-body')?.children.length > 0")
    page.evaluate('document.fonts.ready')


def navigation(browser, args, width, theme):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce',
                                  has_touch=width <= 760, is_mobile=width <= 760)
    page = context.new_page()
    open_article(page, args.base, DEFAULT_PATHS[0], theme)
    page.wait_for_function("() => document.querySelectorAll('#reader-toc .toc-list a').length > 2")
    failures = []
    report = {'width': width, 'theme': theme, 'failures': failures}
    for control in page.locator('#reader-actions button:visible,#reader-actions a:visible').all():
        control.scroll_into_view_if_needed()
        bounds = control.evaluate('el => ({left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right})')
        if bounds['left'] < -1 or bounds['right'] > width + 1:
            failures.append(f'阅读工具不可完整访问: {control.get_attribute("id")} {bounds}')
    page.locator('#reader-actions').evaluate('el => el.scrollTo({left:0,behavior:"instant"})')
    if width < 1200:
        trigger = page.locator('#reader-outline-trigger')
        if not trigger.count() or not trigger.is_visible():
            failures.append('窄屏缺少本文目录入口')
        else:
            trigger.focus()
            page.keyboard.press('Enter')
            dialog = page.locator('#reader-outline')
            page.wait_for_function("() => document.querySelector('#reader-outline').open")
            assert page.evaluate("document.querySelector('#reader-outline').contains(document.activeElement)")
            for key in ('Shift+Tab', 'Tab', 'Tab'):
                page.keyboard.press(key)
                assert page.evaluate("document.querySelector('#reader-outline').contains(document.activeElement)"), key
            page.screenshot(path=str(args.out / f'{theme}-{width}-outline.png'))
            page.keyboard.press('Escape')
            page.wait_for_function("() => !document.querySelector('#reader-outline').open")
            assert trigger.evaluate('el => el === document.activeElement')
            assert page.locator('#reader').evaluate("el => el.classList.contains('open')")
            trigger.click()
            link = dialog.locator('nav a').nth(2)
            target = link.get_attribute('href')[1:]
            link.click()
            page.wait_for_function('id => document.activeElement.id === id', arg=target)
            assert not dialog.evaluate('el => el.open')
            assert page.evaluate('decodeURIComponent(location.hash)') == '#' + target
            assert page.evaluate('window.scrollX') == 0
            top = page.locator('[id="' + target + '"]').evaluate('el => el.getBoundingClientRect().top')
            bar = page.locator('.topbar').evaluate('el => el.getBoundingClientRect().bottom')
            assert top >= bar + 8, (top, bar)
            report['headingTop'] = top
            start_y = page.evaluate('window.scrollY')
            page.keyboard.press('ArrowDown')
            page.wait_for_function('y => window.scrollY > y', arg=start_y)
            report['nativeArrowScroll'] = True
            page.screenshot(path=str(args.out / f'{theme}-{width}-section.png'))
            trigger.click()
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.wait_for_function("() => !document.querySelector('#reader-outline').open")
            assert not trigger.is_visible()
            report['responsiveClose'] = True
    else:
        for selector in ('#reader-toc', '#reader-siblings'):
            rail = page.locator(selector)
            button = rail.locator('.rail-toggle')
            before = button.get_attribute('aria-expanded')
            button.focus()
            page.keyboard.press('Enter')
            after = button.get_attribute('aria-expanded')
            if before == after:
                failures.append(f'{selector}: Enter重复切换')
            page.keyboard.press('Space')
            if button.get_attribute('aria-expanded') != before:
                failures.append(f'{selector}: Space未恢复')
            rail.locator('.rail-head > span').click()
            if button.get_attribute('aria-expanded') == before:
                failures.append(f'{selector}: 标题文字点击无效')
            rail.locator('.rail-head > span').click()
        report['keyboardCollapse'] = not failures
    context.close()
    return report


def media(browser, args, theme):
    context = browser.new_context(viewport={'width': 1024, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    open_article(page, args.base, IMAGE_PATH, theme)
    image = page.locator('#reader-body img').first
    image.scroll_into_view_if_needed()
    page.wait_for_function('img => img.complete', arg=image.element_handle(), timeout=60000)
    assert image.evaluate('el => el.naturalWidth > 0'), '真实图片初次加载失败'
    failures = []
    frame = image.locator('xpath=..')
    original = frame.locator('.reader-image-open')
    if not original.count():
        failures.append('正文图片缺少查看原图入口')
    else:
        assert original.get_attribute('href') == image.get_attribute('src')
        assert original.get_attribute('target') == '_blank'
        assert 'noopener' in original.get_attribute('rel')
        original.focus()
        with context.expect_page() as opened:
            page.keyboard.press('Enter')
        opened.value.wait_for_load_state()
        assert opened.value.url == original.get_attribute('href')
        opened.value.close()
        frame.screenshot(path=str(args.out / f'{theme}-image-ready.png'))
        page.set_viewport_size({'width': 375, 'height': 900})
        frame.screenshot(path=str(args.out / f'{theme}-image-mobile.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        session = context.new_cdp_session(page)
        session.send('Network.enable')
        session.send('Network.setCacheDisabled', {'cacheDisabled': True})
        session.send('Network.emulateNetworkConditions', {'offline': True, 'latency': 0, 'downloadThroughput': 0, 'uploadThroughput': 0})
        image.evaluate('el => {el.src = el.getAttribute("src")}')
        page.wait_for_function("() => document.querySelector('.reader-image').dataset.state === 'error'")
        assert frame.locator('.reader-image-status').inner_text()
        assert frame.locator('.reader-image-retry').is_visible()
        assert frame.locator('.reader-image-status').evaluate('el => parseFloat(getComputedStyle(el).fontSize) >= 16')
        frame.screenshot(path=str(args.out / f'{theme}-image-offline.png'))
        session.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        frame.locator('.reader-image-retry').click()
        page.wait_for_function("() => document.querySelector('.reader-image').dataset.state === 'ready'", timeout=60000)
        assert image.evaluate('el => el.complete && el.naturalWidth > 0')
        assert not frame.locator('.reader-image-retry').is_visible()
        assert original.evaluate('el => el === document.activeElement'), '重试完成后焦点应回到原图入口'
        session.detach()
    open_article(page, args.base, CALLOUT_PATH, theme)
    callout = page.locator('#reader-body .callout').first
    title = callout.locator('.callout-title')
    if not title.count() or title.inner_text() != '证据边界':
        failures.append('提示块自定义标题没有独立显示')
    else:
        assert '这是项目时期的证据快照' in callout.inner_text()
        assert title.evaluate('el => getComputedStyle(el).display') == 'block'
    callout.screenshot(path=str(args.out / f'{theme}-callout.png'))
    context.close()
    return {'theme': theme, 'failures': failures}


def main():
    parser = argparse.ArgumentParser(description='真实文章目录、折叠、图片与提示块检查')
    parser.add_argument('--base', default='http://127.0.0.1:18790')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'navigation-media')
    parser.add_argument('--navigation-only', action='store_true')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for theme in ('light', 'dark'):
            for width in (375, 768, 1199, 1440):
                result = navigation(browser, args, width, theme)
                reports.append(result)
                print(result, flush=True)
            if not args.navigation_only:
                result = media(browser, args, theme)
                reports.append(result)
                print(result, flush=True)
            (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
    failures = sum(len(report['failures']) for report in reports)
    print(f'{len(reports)} navigation/media cases; {failures} failures')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
