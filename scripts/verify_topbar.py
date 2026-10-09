import argparse
import json
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

PAGES = [('home', '/'), ('graph', '/?view=graph'), ('papers', '/papers'), ('sources', '/sources')]


def probe(page):
    return page.evaluate("""() => {
      const bar = document.querySelector('.topbar');
      const input = bar.querySelector('input[type=search]');
      const title = bar.querySelector('.topbar-title');
      const search = input.closest('.search');
      const sidebar = document.querySelector('.tk-sidebar');
      const controls = document.querySelector('.tk-controls');
      const rect = el => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {x:r.x, y:r.y, right:r.right, bottom:r.bottom, w:r.width, h:r.height};
      };
      const b = rect(bar), side = rect(sidebar);
      const left = getComputedStyle(sidebar).position === 'fixed' ? side.right : 0;
      const y = Math.min(innerHeight - 1, Math.max(0, b.y + 4));
      const edgeCovered = [left + 1, document.documentElement.clientWidth - 1].map(x => {
        const el = document.elementFromPoint(x, y);
        return !!el && (el === bar || bar.contains(el));
      });
      return {
        bar: b, search: rect(search), controls: rect(controls),
        expectedLeft: left, viewport: document.documentElement.clientWidth,
        scrollY: scrollY, scrollWidth: document.documentElement.scrollWidth,
        position: getComputedStyle(bar).position,
        background: getComputedStyle(bar).backgroundColor,
        theme: document.documentElement.dataset.theme,
        font: parseFloat(getComputedStyle(title).fontSize),
        title: title.textContent.trim(), titleHidden: title.hidden,
        titleOpacity: Number(getComputedStyle(title).opacity),
        searchOpacity: Number(getComputedStyle(search).opacity), edgeCovered,
        count: document.querySelectorAll('.topbar input[type=search]').length,
        condensed: bar.classList.contains('is-condensed')
      };
    }""")


def capture(page, directory, state, metrics):
    path = directory / f'{state}.png'
    page.screenshot(path=str(path))
    with Image.open(path) as shot:
        top = max(0, min(shot.height - 1, int(metrics['bar']['y']) - 8))
        shot.crop((0, top, shot.width, min(shot.height, top + 200))).save(
            directory / f'{state}-header.png')


def issues(top, scrolled, restored, theme):
    errors = []
    for state, metrics in [('initial', top), ('scrolled', scrolled), ('restored', restored)]:
        b = metrics['bar']
        if abs(b['x'] - metrics['expectedLeft']) > 1 or abs(b['right'] - metrics['viewport']) > 1:
            errors.append(f'{state}: 顶栏背景未覆盖侧栏之外的完整宽度')
        if not all(metrics['edgeCovered']):
            errors.append(f'{state}: 顶栏边缘露出其他容器')
        if metrics['scrollWidth'] > metrics['viewport'] + 1:
            errors.append(f'{state}: 页面存在横向溢出')
        if metrics['count'] != 1 or metrics['theme'] != theme:
            errors.append(f'{state}: 搜索框数量或主题不正确')
    search = top['search']
    if search['x'] < top['bar']['x'] or search['right'] > top['bar']['right'] + 1:
        errors.append('搜索框超出顶栏')
    if top['viewport'] >= 1024 and search['x'] < (top['expectedLeft'] + top['viewport']) / 2 - 310:
        errors.append('桌面搜索框未位于顶栏右侧')
    if abs(scrolled['bar']['y']) > 1 or scrolled['position'] != 'sticky':
        errors.append('下滑后的顶栏未保持置顶')
    if not scrolled['condensed'] or scrolled['titleHidden'] or not scrolled['title']:
        errors.append('下滑后没有显示当前页面标题')
    if scrolled['titleOpacity'] < 0.99 or scrolled['searchOpacity'] > 0.01:
        errors.append('标题与搜索框的转换未完成')
    if scrolled['font'] < 22:
        errors.append(f"标题字号只有 {scrolled['font']}px，要求至少22px")
    if restored['condensed'] or restored['searchOpacity'] < 0.99:
        errors.append('返回顶部后搜索框未恢复')
    if abs(top['bar']['h'] - scrolled['bar']['h']) > 1:
        errors.append('滚动时顶栏高度变化')
    return errors


def contact_sheet(root, width, theme):
    tiles = []
    for name, _ in PAGES:
        for state in ('initial', 'scrolled'):
            with Image.open(root / f'{width}-{theme}-{name}' / f'{state}-header.png') as image:
                tile = image.convert('RGB')
                tile.thumbnail((720, 200))
                tiles.append(tile)
    row_height = max(tile.height for tile in tiles)
    sheet = Image.new('RGB', (1440, row_height * len(PAGES)), 'white')
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 2) * 720, (index // 2) * row_height))
    sheet.save(root / f'{width}-{theme}-headers.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default=os.environ.get('BASE', 'http://127.0.0.1:18788'))
    parser.add_argument('--widths', type=int, nargs='+', default=[int(os.environ['VIEWPORT'])] if 'VIEWPORT' in os.environ else [390, 768, 1024, 1440, 1920])
    parser.add_argument('--themes', nargs='+', choices=['light', 'dark'], default=['light', 'dark'])
    parser.add_argument('--out', type=Path, default=Path('.agent/tmp/topbar-visual/current'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in args.widths:
            for theme in args.themes:
                for name, path in PAGES:
                    context = browser.new_context(viewport={'width': width, 'height': 900}, color_scheme=theme)
                    page = context.new_page()
                    runtime_errors = []
                    page.on('pageerror', lambda error: runtime_errors.append(str(error)))
                    separator = '&' if '?' in path else '?'
                    response = page.goto(args.base + path + separator + 'theme=' + theme, wait_until='domcontentloaded', timeout=45000)
                    assert response.ok, f'{name}: HTTP {response.status}'
                    page.wait_for_selector('.topbar input[type=search]')
                    page.wait_for_timeout(2200)
                    directory = args.out / f'{width}-{theme}-{name}'
                    directory.mkdir(parents=True, exist_ok=True)
                    top = probe(page)
                    capture(page, directory, 'initial', top)
                    page.evaluate('window.scrollTo(0, 600)')
                    page.wait_for_timeout(700)
                    scrolled = probe(page)
                    capture(page, directory, 'scrolled', scrolled)
                    page.evaluate('window.scrollTo(0, 0)')
                    page.wait_for_timeout(700)
                    restored = probe(page)
                    errors = issues(top, scrolled, restored, theme) + runtime_errors
                    report.append({'page': name, 'width': width, 'theme': theme,
                                   'initial': top, 'scrolled': scrolled, 'restored': restored,
                                   'errors': errors})
                    print(f'{width} {theme} {name}: ' + ('; '.join(errors) if errors else 'PASS'), flush=True)
                    context.close()
                contact_sheet(args.out, width, theme)
        browser.close()
    (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    failed = sum(bool(case['errors']) for case in report)
    print(f'{len(report) - failed}/{len(report)} 通过；截图与报告：{args.out}')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
