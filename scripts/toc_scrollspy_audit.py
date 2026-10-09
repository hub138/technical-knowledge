import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from note_verify_shots import DEFAULT_PATHS

ROOT = Path(__file__).resolve().parents[1]


def settle(page):
    page.evaluate("""() => new Promise(resolve => {
      let remaining=6;
      const tick=()=>{if(--remaining===0)resolve();else requestAnimationFrame(tick)};
      requestAnimationFrame(tick);
    })""")


def current(page):
    return page.evaluate("""() => {
      const active = selector => [...document.querySelectorAll(selector+' a[aria-current]')]
        .map(a => ({id:a.getAttribute('href').slice(1), current:a.getAttribute('aria-current'),
          color:getComputedStyle(a).color, background:getComputedStyle(a).backgroundColor,
          shadow:getComputedStyle(a).boxShadow}));
      const body=document.querySelector('#reader-body');
      return {desktop:active('#reader-toc'), mobile:active('#reader-outline-list'), scrollY:scrollY,
        bottomGap:document.documentElement.scrollHeight-innerHeight-scrollY,
        bodyBottom:body.getBoundingClientRect().bottom,
        lastHeading:[...body.querySelectorAll('h2,h3,h4')].at(-1).getBoundingClientRect().top};
    }""")


def verify(browser, base, path, width, theme, output, index):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    url = f"{base.rstrip('/')}/?{urlencode({'path': path, 'theme': theme})}"
    response = page.goto(url, wait_until='domcontentloaded')
    assert response.status == 200
    page.locator('#reader-body h2').first.wait_for()
    page.evaluate('document.fonts.ready')
    for image in page.locator('#reader-body img').all():
        image.scroll_into_view_if_needed()
        page.wait_for_function('img => img.complete && img.naturalWidth > 0', arg=image.element_handle())
    page.wait_for_function("() => !document.querySelector('#reader-body pre.mermaid:not([data-processed])')")
    heads = page.locator('#reader-body h2,#reader-body h3,#reader-body h4').evaluate_all(
        'els => els.map(el=>({id:el.id,text:el.textContent.trim()}))')
    assert len(heads) >= 4
    report = {'path': path, 'width': width, 'theme': theme, 'failures': [], 'samples': []}

    def check(condition, message):
        if not condition:
            report['failures'].append(message)

    def expect(ident, label):
        state = current(page)
        report['samples'].append({'label': label, 'expected': ident, **state})
        for kind in ('desktop', 'mobile'):
            actual = state[kind]
            check([item['id'] for item in actual] == ([ident] if ident else []),
                  f'{label} {kind}: expected {ident}, got {[item["id"] for item in actual]}')
            if ident and actual:
                check(actual[0]['current'] == 'location', f'{label} {kind}: wrong aria-current')
                check(actual[0]['background'] != 'rgba(0, 0, 0, 0)', f'{label} {kind}: missing current background')
                check(actual[0]['shadow'] != 'none', f'{label} {kind}: missing non-color marker')
        return state

    indexes = list(range(min(8, len(heads))))
    for heading_index in indexes + list(reversed(indexes)):
        ident = heads[heading_index]['id']
        placement = page.evaluate("""id => {
          const heading=document.getElementById(id);
          const inset=document.querySelector('.topbar').getBoundingClientRect().height+16;
          const requested=scrollY+heading.getBoundingClientRect().top-inset;
          window.scrollTo({top:requested,behavior:'instant'});
          return {requested,max:document.documentElement.scrollHeight-innerHeight};
        }""", ident)
        settle(page)
        if placement['requested'] <= placement['max']:
            expect(ident, f'heading-{heading_index}')

    position = page.evaluate("""() => {
      const heads=[...document.querySelectorAll('#reader-body h2,#reader-body h3,#reader-body h4')];
      const inset=document.querySelector('.topbar').getBoundingClientRect().height+16;
      const i=heads.findIndex((h,i)=>i>0&&h.getBoundingClientRect().top-heads[i-1].getBoundingClientRect().top>450);
      if(i<0)return null;
      const requested=scrollY+heads[i].getBoundingClientRect().top-inset-240;
      window.scrollTo({top:requested,behavior:'instant'});
      return heads[i-1].id;
    }""")
    assert position, 'No real long section for boundary check'
    settle(page)
    expect(position, 'next-heading-visible')
    page.evaluate('window.scrollTo({top:document.documentElement.scrollHeight,behavior:"instant"})')
    settle(page)
    expect(heads[-1]['id'], 'article-end')
    page.evaluate('window.scrollTo({top:0,behavior:"instant"})')
    settle(page)
    expect(None, 'article-opening')

    def select(heading_index):
        if width < 1200:
            page.locator('#reader-outline-trigger').click()
            page.locator('#reader-outline-list a').nth(heading_index).click()
        else:
            page.locator('#reader-toc .toc-list a').nth(heading_index).click()
        settle(page)

    select(1)
    expect(heads[1]['id'], 'clicked-section')
    first_url = page.url
    history_length = page.evaluate('history.length')
    select(1)
    check(page.evaluate('history.length') == history_length, 'Repeated current section adds history')
    select(2)
    second_url = page.url
    page.go_back(wait_until='domcontentloaded')
    settle(page)
    check(page.url == first_url, 'Back did not restore previous section')
    select(1)
    page.go_forward(wait_until='domcontentloaded')
    settle(page)
    check(page.url == second_url, 'Repeated section selection discarded forward history')

    select(2)
    before = page.evaluate('window.scrollY')
    if width < 1200:
        page.locator('#reader-outline-trigger').click()
        settle(page)
        expect(heads[2]['id'], 'opened-outline')
        page.screenshot(path=str(output / f'{index}-{theme}-{width}-current.png'))
        page.keyboard.press('Escape')
        settle(page)
        check(abs(page.evaluate('window.scrollY')-before) <= 1, 'Opening directory moved article')
    else:
        page.screenshot(path=str(output / f'{index}-{theme}-{width}-current.png'))
        check(abs(before-page.evaluate('window.scrollY')) <= 1, 'Directory tracking moved article')
    other = DEFAULT_PATHS[3]
    other_url = f"{base.rstrip('/')}/?{urlencode({'path': other, 'theme': theme})}"
    peer = page.locator('#reader-body a[data-note]').filter(has_text='可靠生成').first
    if path == DEFAULT_PATHS[0] and peer.count():
        peer.click()
        page.wait_for_function('old => new URLSearchParams(location.search).get("path") !== old', arg=path)
    else:
        page.goto(other_url, wait_until='domcontentloaded')
        page.locator('#reader-body h2').first.wait_for()
    settle(page)
    state = current(page)
    check(not state['desktop'] and not state['mobile'], 'Previous article current-section state leaked')
    check(not errors, f'Page errors: {errors}')
    context.close()
    return report


def main():
    parser = argparse.ArgumentParser(description='真实文章当前章节与浏览历史检查')
    parser.add_argument('--base', default='http://127.0.0.1:18793')
    parser.add_argument('--path', action='append')
    parser.add_argument('--width', type=int, action='append')
    parser.add_argument('--theme', choices=('light', 'dark'), action='append')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'toc-current')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for index, path in enumerate(args.path or DEFAULT_PATHS[:2]):
            for width in args.width or (375, 768, 1199, 1440):
                for theme in args.theme or ('light', 'dark'):
                    report = verify(browser, args.base, path, width, theme, args.out, index)
                    reports.append(report)
                    (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(f'{path} {width} {theme}: {len(report["failures"])} failures', flush=True)
                    for failure in report['failures'][:8]:
                        print(f'  {failure}', flush=True)
        browser.close()
    failures = sum(len(report['failures']) for report in reports)
    print(f'{len(reports)} current-section cases; {failures} failures')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
