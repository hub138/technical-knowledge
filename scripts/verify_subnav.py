import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('/learn', '/learn/history', '/learn/openmaic', '/learn/intuition', '/learn/transfer')

MEASURE = """button => {
  const row=button.closest('.tk-nav-row');
  const label=row.querySelector('a > span:last-child');
  const style=getComputedStyle(button);
  const textStyle=getComputedStyle(label);
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  const rgba=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data]};
  const rect=label.getBoundingClientRect();
  return {label:label.textContent.trim(),background:style.backgroundColor,
    alpha:rgba(style.backgroundColor)[3],image:style.backgroundImage,
    textColor:textStyle.color,opacity:textStyle.opacity,visibility:textStyle.visibility,
    textWidth:rect.width,textHeight:rect.height,expanded:button.getAttribute('aria-expanded')};
}"""


def check_page(browser, base, path, width, theme, output):
    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    response = page.goto(f'{base}{path}?theme={theme}', wait_until='domcontentloaded')
    assert response.status == 200
    toggle = page.locator('.tk-subnav-toggle[data-subgroup="projects"]')
    toggle.wait_for(state='visible')
    page.wait_for_function('theme => document.documentElement.dataset.theme === theme', arg=theme)
    page.evaluate('document.fonts.ready')
    failures = []
    snapshots = []
    original_url = page.url

    def measure(state):
        toggle.scroll_into_view_if_needed()
        data = toggle.evaluate(MEASURE)
        data['state'] = state
        snapshots.append(data)
        if not data['label'] or data['textWidth'] <= 0 or data['textHeight'] <= 0:
            failures.append(f'{state}: 父导航文字没有可见尺寸')
        if data['opacity'] != '1' or data['visibility'] != 'visible':
            failures.append(f'{state}: 父导航文字隐藏')
        if data['alpha'] != 0 or data['image'] != 'none':
            failures.append(f'{state}: 折叠按钮背景遮挡导航文字')

    measure('initial')
    other = 'light' if theme == 'dark' else 'dark'
    page.locator('[data-tk-theme-toggle]').click()
    page.wait_for_function('theme => document.documentElement.dataset.theme === theme', arg=other)
    measure('theme-switched')
    page.locator('[data-tk-theme-toggle]').click()
    page.wait_for_function('theme => document.documentElement.dataset.theme === theme', arg=theme)
    measure('theme-restored')

    if toggle.get_attribute('aria-expanded') != 'true':
        toggle.click()
    group = page.locator('#subgroup-projects')
    assert group.is_visible()
    assert group.locator('.tk-subnav-overview').count() == 1
    toggle.click(position={'x': 8, 'y': 8})
    assert toggle.get_attribute('aria-expanded') == 'false' and group.is_hidden()
    measure('collapsed')
    toggle.focus()
    page.keyboard.press('Enter')
    assert toggle.get_attribute('aria-expanded') == 'true' and group.is_visible()
    measure('expanded')
    assert page.url == original_url, '折叠导航意外跳转页面'
    screenshot = path.strip('/').replace('/', '-') + f'-{width}-{theme}.png'
    if width >= 1200:
        page.locator('#tk-sidebar').screenshot(path=str(output / screenshot))
    else:
        toggle.scroll_into_view_if_needed()
        page.screenshot(path=str(output / screenshot))

    child = group.locator('a[href="/learn/history"]' if path != '/learn/history' else 'a[href="/learn"]')
    destination = child.get_attribute('href')
    child.click()
    page.wait_for_url(f'**{destination}')
    page.locator('#subgroup-projects a[aria-current="page"]').wait_for()
    assert page.locator('#subgroup-projects a[aria-current="page"]').get_attribute('href') == destination
    report = {'path': path, 'width': width, 'theme': theme, 'measurements': snapshots,
              'screenshot': screenshot, 'failures': failures}
    context.close()
    return report


def check_group_overview(browser, base, path, group_key, child_href, output):
    """父项页与子项页都要展开折叠组，且组内链接真的可见。

    这是 2026-09-25 的真实现象：在子项页点组内第一项「总览」，跳到父项页后
    整组收回，总览和两个子项一起消失。DOM 里链接还在，只是 hidden，所以
    断言必须量实际渲染高度，不能只查 count。
    """
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page = context.new_page()
    failures = []
    cases = []
    for target in (path, child_href):
        response = page.goto(f'{base}{target}', wait_until='domcontentloaded')
        assert response.status == 200, f'{target} 返回 {response.status}'
        group = page.locator(f'.tk-subnav-group[data-subgroup="{group_key}"]')
        group.wait_for(state='attached')
        page.wait_for_timeout(1200)
        state = page.evaluate(
            """key => {
                const g = document.querySelector(`.tk-subnav-group[data-subgroup="${key}"]`);
                const links = Array.from(g.querySelectorAll('a'));
                return {
                    hidden: g.hidden,
                    expanded: document.querySelector(`.tk-subnav-toggle[data-subgroup="${key}"]`).getAttribute('aria-expanded'),
                    total: links.length,
                    visible: links.filter(a => a.getBoundingClientRect().height > 0).map(a => a.getAttribute('href')),
                    current: Array.from(g.querySelectorAll('a[aria-current]')).map(a => a.getAttribute('href')),
                };
            }""",
            group_key,
        )
        state['path'] = target
        cases.append(state)
        if state['hidden'] or state['expanded'] != 'true':
            failures.append(f'{target}: 折叠组 {group_key} 未展开（hidden={state["hidden"]}）')
        if len(state['visible']) != state['total']:
            failures.append(f'{target}: 组内链接不可见 {state["visible"]}/{state["total"]}')
        if not state['current']:
            failures.append(f'{target}: 组内没有当前项高亮')
    # 子项页 → 点「总览」→ 父项页，组必须仍展开
    page.goto(f'{base}{child_href}', wait_until='domcontentloaded')
    page.wait_for_timeout(1200)
    page.locator(f'.tk-subnav-group[data-subgroup="{group_key}"] .tk-subnav-overview').click()
    page.wait_for_timeout(2000)
    after = page.evaluate(
        """key => {
            const g = document.querySelector(`.tk-subnav-group[data-subgroup="${key}"]`);
            const links = Array.from(g.querySelectorAll('a'));
            return { url: location.pathname + location.search, hidden: g.hidden,
                     visible: links.filter(a => a.getBoundingClientRect().height > 0).length, total: links.length };
        }""",
        group_key,
    )
    cases.append({**after, 'path': 'click overview'})
    if after['hidden'] or after['visible'] != after['total']:
        failures.append(f'点总览后 {after["url"]}: 组收回（hidden={after["hidden"]}, 可见 {after["visible"]}/{after["total"]}）')
    screenshot = f'group-{group_key}-overview.png'
    page.locator('#tk-sidebar').screenshot(path=str(output / screenshot))
    context.close()
    return {'group': group_key, 'cases': cases, 'screenshot': screenshot, 'failures': failures}


def main():
    parser = argparse.ArgumentParser(description='学习页面侧栏父导航可见性、双主题与展开交互回归')
    parser.add_argument('--base', default='http://127.0.0.1:18796')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'subnav')
    parser.add_argument('--path', action='append')
    parser.add_argument('--width', type=int, action='append')
    parser.add_argument('--theme', choices=('light', 'dark'), action='append')
    parser.add_argument('--group', help='额外校验某个折叠组在父项页与子项页都展开，例如 panorama')
    parser.add_argument('--child-href', help='配合 --group 的子项页地址，例如 /panorama/reading')
    parser.add_argument('--group-path', default='/?view=panorama', help='配合 --group 的父项页地址')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        if args.group:
            report = check_group_overview(
                browser, args.base.rstrip('/'), args.group_path, args.group,
                args.child_href or '/panorama/reading', args.out,
            )
            reports.append(report)
            (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'group {args.group}: {report["failures"]}', flush=True)
        for path in args.path or PAGES:
            for width in args.width or (375, 1440):
                for theme in args.theme or ('light', 'dark'):
                    report = check_page(browser, args.base.rstrip('/'), path, width, theme, args.out)
                    reports.append(report)
                    (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(f'{path} {width} {theme}: {report["failures"]}', flush=True)
        browser.close()
    failures = sum(len(report['failures']) for report in reports)
    print(f'{len(reports)} subnav cases; {failures} failures', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
