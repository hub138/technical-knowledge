import argparse
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import sync_playwright

from note_verify_shots import DEFAULT_PATHS

ROOT = Path(__file__).resolve().parents[1]


def settle(page):
    page.evaluate("""() => new Promise(resolve => {
      let frames=8;
      const tick=()=>{if(--frames)requestAnimationFrame(tick);else resolve()};
      requestAnimationFrame(tick);
    })""")


def measure(browser, base, output, width, theme):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    page.set_default_timeout(90000)
    failures = []
    results = {'width': width, 'theme': theme, 'failures': failures}
    start = DEFAULT_PATHS[0]
    url = f"{base}/?{urlencode({'path': start, 'theme': theme})}"

    def check(ok, message):
        if not ok:
            failures.append(message)

    def load():
        page.goto('about:blank')
        response = page.goto(url, wait_until='domcontentloaded')
        assert response.status == 200
        page.locator('#reader-body a[data-note]').first.wait_for()
        page.evaluate('document.fonts.ready')
        settle(page)

    def state():
        return page.evaluate("""() => ({view:state.view,path:state.selected,
          url:location.href,title:document.title,heading:document.querySelector('#reader-title').textContent,
          busy:document.querySelector('#reader').getAttribute('aria-busy')})""")

    load()
    links = page.locator('#reader-body a[data-note]').evaluate_all("""els =>
      [...new Set(els.map(a=>a.dataset.note))]""")
    assert len(links) >= 2
    first, second = links[:2]
    expected = {}
    for path in (start, first, second):
        response = page.request.get(f"{base}/api/note?{urlencode({'path': path})}")
        assert response.status == 200
        expected[path] = response.json()['title']
    check(expected[start] in page.title(), '初次打开文章未同步浏览器标题')

    pending = {}

    def pause(route):
        path = parse_qs(urlsplit(route.request.url).query)['path'][0]
        pending[path] = route

    def wait_pending(path):
        for _ in range(100):
            if path in pending:
                return
            page.wait_for_timeout(20)
        raise AssertionError(f'真实文章请求未到达: {path}')

    def release(path):
        route = pending.pop(path)
        with page.expect_event('requestfinished', predicate=lambda request: request == route.request):
            route.continue_()
        settle(page)

    def click(path):
        page.locator('#reader-body a[data-note=' + json.dumps(path, ensure_ascii=False) + ']').first.click()
        wait_pending(path)

    page.route('**/api/note?*', pause)
    click(first)
    check(page.locator('#reader').get_attribute('aria-busy') == 'true', '文章加载缺少忙碌状态')
    status = page.locator('#reader-loading')
    check(status.count() == 1 and status.is_visible(), '文章加载缺少可见反馈')
    if status.count():
        check(expected[first] in status.inner_text(), '加载反馈没有说明目标文章')
        geometry = status.evaluate("""el => ({left:el.getBoundingClientRect().left,
          right:el.getBoundingClientRect().right,bottom:el.getBoundingClientRect().bottom,
          font:parseFloat(getComputedStyle(el).fontSize),button:el.querySelector('button').getBoundingClientRect().height})""")
        check(geometry['left'] >= 0 and geometry['right'] <= width and geometry['bottom'] <= 900, '加载提示超出视口')
        check(geometry['font'] >= 16 and geometry['button'] >= 44, '加载提示字号或点击区域不足')
        original_path, original_url = state()['path'], page.url
        page.locator('[data-tk-lang-toggle]').click()
        page.wait_for_function("() => window.TKI18N.lang === 'en'")
        check(page.locator('#reader-load-cancel').inner_text() == 'Cancel loading', '加载取消按钮未跟随英文')
        check(page.locator('#reader-loading-message').inner_text().startswith('Opening: '), '加载说明未跟随英文')
        page.locator('[data-tk-lang-toggle]').click()
        page.wait_for_function("() => window.TKI18N.lang === 'zh'")
        check(state()['path'] == original_path and page.url == original_url, '加载反馈语言切换改变了当前文章')
        page.screenshot(path=str(output / f'{theme}-{width}-loading.png'))
        results['loadingGeometry'] = geometry
    click(second)
    release(second)
    check(state()['path'] == second, '后选文章未正常打开')
    check(page.evaluate('document.activeElement.id') == 'reader-title', '切换文章后焦点未交给标题')
    winning = state()
    release(first)
    check(state()['path'] == second and page.url == winning['url'], '较早请求覆盖了后来选择的文章')
    check(expected[second] in page.title(), '切换文章未更新浏览器标题')
    check(page.locator('#reader').get_attribute('aria-busy') != 'true', '文章加载结束仍保持忙碌状态')
    results['latestSelection'] = state()
    page.unroute('**/api/note?*', pause)

    load()
    page.route('**/api/note?*', pause)
    click(first)
    page.locator('#reader-back').click()
    settle(page)
    returned = state()
    check(returned['view'] != 'reader', '返回目录没有离开文章')
    release(first)
    check(state()['view'] == returned['view'] and page.url == returned['url'], '加载期间返回被旧请求撤销')
    results['returnDuringLoad'] = state()
    page.unroute('**/api/note?*', pause)

    load()
    page.route('**/api/note?*', pause)
    click(first)
    cancel = page.locator('#reader-load-cancel')
    if cancel.count():
        cancel.click()
        settle(page)
        check(page.locator('#reader').get_attribute('aria-busy') != 'true', '取消后忙碌状态未解除')
        release(first)
        check(state()['path'] == start, '取消的请求仍打开文章')
        check(page.evaluate('document.activeElement.id') == 'reader-body', '取消加载后焦点没有回到正文')
    else:
        check(False, '加载状态缺少取消入口')
        release(first)
    page.unroute('**/api/note?*', pause)

    load()
    page.route('**/api/note?*', pause)
    click(first)
    release(first)
    page.go_back(wait_until='domcontentloaded')
    wait_pending(start)
    page.locator('#reader-back').click()
    settle(page)
    returned = state()
    release(start)
    check(state()['view'] == returned['view'] and page.url == returned['url'], '历史恢复请求覆盖了返回操作')
    page.unroute('**/api/note?*', pause)

    load()
    page.route('**/api/note?*', pause)
    click(first)
    if width < 1200:
        page.locator('#reader-outline-trigger').click()
        page.locator('#reader-outline-list a').nth(1).click()
    else:
        page.locator('#reader-toc .toc-list a').nth(1).click()
    chosen_url = page.url
    release(first)
    check(state()['path'] == start and page.url == chosen_url, '待打开文章覆盖了读者选择的当前章节')
    page.unroute('**/api/note?*', pause)

    session = context.new_cdp_session(page)
    session.send('Network.enable')
    session.send('Network.setCacheDisabled', {'cacheDisabled': True})

    def offline(value):
        session.send('Network.emulateNetworkConditions', {
            'offline': value, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1,
        })

    def fail_offline(path):
        offline(True)
        route = pending.pop(path)
        with page.expect_event('requestfailed', predicate=lambda request: request == route.request):
            route.continue_()
        settle(page)
        offline(False)

    load()
    page.route('**/api/note?*', pause)
    click(first)
    click(second)
    release(second)
    winning = state()
    fail_offline(first)
    check(state() == winning, '较早请求失败后覆盖了新文章或其状态')
    page.unroute('**/api/note?*', pause)

    load()
    learned = page.locator('#reader-learned')
    if learned.get_attribute('aria-pressed') != 'true':
        learned.click()
    page.route('**/api/note?*', pause)
    click(first)
    fail_offline(first)
    retry = page.locator('#reader-retry')
    check(page.locator('#reader').get_attribute('aria-busy') != 'true', '失败后未解除忙碌状态')
    check(not page.locator('#reader-loading').is_visible(), '失败后仍显示加载提示')
    check(page.locator('#reader-body [role="alert"]').count() == 1, '加载失败缺少持久错误说明')
    check(page.evaluate('document.activeElement.id') == 'reader-title', '错误页焦点未交给标题')
    check(learned.is_disabled() and learned.get_attribute('aria-pressed') == 'false', '错误页保留上一篇已读状态')
    check(page.locator('#reader-download').is_disabled(), '错误页下载按钮未禁用')
    check(not page.locator('#reader-study').is_visible(), '错误页仍显示主题学习入口')
    saved_time = page.evaluate('path => readingTime.total(path)', start)
    settle(page)
    check(page.evaluate('path => readingTime.total(path)', start) == saved_time, '错误页继续给上一篇累计阅读时间')
    if retry.count():
        sizes = page.locator('.reader-load-error .empty-hint,.reader-load-error button').evaluate_all('els => els.map(el=>parseFloat(getComputedStyle(el).fontSize))')
        check(all(size >= 16 for size in sizes), '错误说明或按钮文字低于16px')
        page.screenshot(path=str(output / f'{theme}-{width}-error.png'))
        retry.focus()
        page.keyboard.press('Enter')
        wait_pending(first)
        release(first)
        check(state()['path'] == first and expected[first] in page.title(), '重新加载没有恢复目标文章')
        check(page.evaluate('document.activeElement.id') == 'reader-title', '重试成功后焦点未交给标题')
        check(learned.is_enabled() and page.locator('#reader-download').is_enabled(), '重试成功后文章操作没有恢复')
    else:
        check(False, '错误页没有原路径重试入口')
    page.unroute('**/api/note?*', pause)
    session.detach()
    results['offlineRetry'] = state()

    load()
    if width >= 1200:
        for selector in ('#reader-body a[data-note]', '#reader-siblings a[data-note]:not([aria-current])', '#reader-pager a[data-note]'):
            for modifier in ('Control', 'Shift'):
                before = state()
                count = len(context.pages)
                link = page.locator(selector).first
                link.click(modifiers=[modifier])
                settle(page)
                opened = context.pages[count:]
                check(bool(opened), f'{selector}: {modifier}点击未打开新页面')
                check(state()['path'] == before['path'] and page.url == before['url'], f'{selector}: 修饰键点击改变了当前文章')
                for tab in opened:
                    tab.wait_for_load_state('domcontentloaded')
                    tab.close()
                if not opened:
                    load()
                if selector.startswith('#reader-siblings'):
                    # rail 默认展开，但上一次交互可能把它收起，且收起后焦点礼让会把
                    # 焦点拽回标题。这里不依赖按压次数 parity：直接读 aria-expanded，
                    # 非 true 就聚焦开关按一次 Enter 翻到展开态并复核。
                    toggle = page.locator('#reader-siblings .rail-toggle')
                    if toggle.get_attribute('aria-expanded') != 'true':
                        toggle.focus()
                        page.keyboard.press('Enter')
                        settle(page)
                    assert toggle.get_attribute('aria-expanded') == 'true', 'siblings rail 未能重新展开'
        results['modifiedLinks'] = True
    context.close()
    return results


def main():
    parser = argparse.ArgumentParser(description='真实文章请求顺序、加载反馈与新标签页行为检查')
    parser.add_argument('--base', default='http://127.0.0.1:18796')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'article-loading')
    parser.add_argument('--width', type=int, action='append')
    parser.add_argument('--theme', choices=('light', 'dark'), action='append')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width in args.width or (375, 1440):
            for theme in args.theme or ('light', 'dark'):
                result = measure(browser, args.base, args.out, width, theme)
                reports.append(result)
                (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'{width} {theme}: {result["failures"]}', flush=True)
        browser.close()
    failures = sum(len(report['failures']) for report in reports)
    print(f'{len(reports)} article-loading cases; {failures} failures')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
