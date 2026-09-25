import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from note_verify_shots import DEFAULT_PATHS

ROOT = Path(__file__).resolve().parents[1]


def load(page, url):
    page.goto('about:blank')
    response = page.goto(url, wait_until="domcontentloaded")
    assert response.status == 200, response.status
    page.locator('#reader-body .code-block').first.wait_for()
    page.evaluate("document.fonts.ready")
    page.wait_for_function("() => document.querySelectorAll('#reader-body h2').length > 2")


def measure(context, base, width, theme, output):
    page = context.new_page()
    # mermaid 渲染要走一遍图形布局，CPU 忙时（check_all 连续跑多个浏览器）
    # 30 秒默认超时不够，会在 svg 出现之前判失败。
    page.set_default_timeout(90000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    url = f"{base}/?{urlencode({'path': DEFAULT_PATHS[0], 'theme': theme})}"
    load(page, url)
    failures = []
    report = {"width": width, "theme": theme, "failures": failures}

    def check(condition, message):
        if not condition:
            failures.append(message)

    links = page.locator('#reader-body a')
    decorations = links.evaluate_all("els => els.map(el => getComputedStyle(el).textDecorationLine)")
    check(bool(decorations) and all('underline' in item for item in decorations), '正文链接缺少默认下划线')
    report["linkCount"] = len(decorations)
    report['bodyStart'] = page.locator('#reader-body').evaluate('el => el.getBoundingClientRect().top')
    if width <= 760:
        check(0 < report['bodyStart'] < 700, f'手机正文未进入首屏: {report["bodyStart"]}')
        toggle = page.locator('.relation-collapse')
        check(toggle.get_attribute('aria-expanded') == 'false', '手机图谱默认未收起')
        toggle.click()
        page.wait_for_function("() => document.querySelector('.relation-collapse').getAttribute('aria-expanded') === 'true'")
        check(page.locator('.relation-graph').is_visible(), '展开后图谱不可见')
        toggle.click()
        page.wait_for_function("() => document.querySelector('.relation-collapse').getAttribute('aria-expanded') === 'false'")
        check(not page.locator('.relation-graph').is_visible(), '收起后图谱仍占位')
    page.screenshot(path=str(output / f"{theme}-{width}-opening.png"))

    scroll = page.locator('#reader-body .table-wrap').first
    pre = page.locator('#reader-body .code-block').first
    for element, name in [(scroll, "table"), (pre, "code")]:
        overflow = element.evaluate("el => el.scrollWidth > el.clientWidth + 1")
        if overflow:
            check(element.get_attribute('tabindex') == '0', f'{name}: 横向内容缺少键盘入口')
            check(bool(element.get_attribute('aria-label')), f'{name}: 缺少可访问名称')
            if element.get_attribute('tabindex') == '0':
                page.locator('#reader-body').focus()
                reached = False
                for _ in range(80):
                    page.keyboard.press('Tab')
                    if element.evaluate('el => el === document.activeElement'):
                        reached = True
                        break
                check(reached, f'{name}: Tab 未到达滚动容器')
                if reached:
                    page.keyboard.press('ArrowRight')
                    page.wait_for_function("el => el.scrollLeft > 0", arg=element.element_handle())
                    check(page.evaluate('window.scrollX') == 0, f'{name}: 页面整体横移')
                    outline = element.evaluate('el => getComputedStyle(el).outlineStyle')
                    check(outline != 'none', f'{name}: 焦点不可见')
                report[f"{name}Keyboard"] = reached
        element.evaluate("""el => new Promise((resolve,reject) => {
          let previous=el.scrollLeft, stable=0, frames=0;
          const tick=()=>{
            const current=el.scrollLeft;
            stable=current===previous?stable+1:0;
            previous=current;
            if(stable>=6){resolve();return;}
            if(++frames>180){reject(new Error('Scroll did not settle'));return;}
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        })""")
        element.evaluate('el => el.scrollTo({left:0,behavior:"instant"})')
        page.wait_for_function('el => el.scrollLeft === 0', arg=element.element_handle())

    copy = page.locator('.code-copy').first
    check(copy.count() == 1, '代码块缺少复制入口')
    if copy.count():
        expected = pre.locator('code').inner_text()
        context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=base)
        copy.click()
        page.wait_for_function("() => document.querySelector('.code-copy-status').textContent === '已复制'")
        actual = page.evaluate('navigator.clipboard.readText()')
        check(actual == expected, '复制内容与代码不一致')
        report['codeCopied'] = actual == expected
        session = context.new_cdp_session(page)
        context_id = session.send('Target.getTargetInfo')['targetInfo']['browserContextId']
        for unrestricted in (False, True):
            session.send('Browser.setPermission', {
                'permission': {'name': 'clipboard-write', 'allowWithoutSanitization': unrestricted},
                'setting': 'denied', 'origin': base, 'browserContextId': context_id,
            })
        permission = page.evaluate("async () => (await navigator.permissions.query({name:'clipboard-write'})).state")
        assert permission == 'denied', f'Permission was not denied: {permission}'
        copy.click()
        page.wait_for_function("() => document.querySelector('.code-copy-status').textContent.includes('失败')")
        check(not copy.is_disabled(), '复制失败后无法重试')
        report['copyDenied'] = page.locator('.code-copy-status').first.inner_text()
        page.locator('.reader-code').first.screenshot(path=str(output / f'{theme}-{width}-copy-denied.png'))
        context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=base)
        copy.click()
        page.wait_for_function("() => document.querySelector('.code-copy-status').textContent === '已复制'")
        check(page.evaluate('navigator.clipboard.readText()') == expected, '重新授权后复制失败')
        session.detach()

    if width >= 1200:
        toc = page.locator('#reader-toc .toc-list a')
        target = toc.nth(2).get_attribute('href')
        toc.nth(2).click()
        check(page.evaluate('decodeURIComponent(location.hash)') == target, '目录点击没有写入文章锚点')
        if page.evaluate('decodeURIComponent(location.hash)') == target:
            shared = page.url
            first_hash = toc.nth(0).get_attribute('href')
            toc.nth(0).click()
            page.go_back(wait_until='domcontentloaded')
            page.wait_for_function('hash => decodeURIComponent(location.hash) === hash', arg=target)
            page.wait_for_function('id => document.activeElement.id === id', arg=target[1:])
            report['anchorHistory'] = True
            check(first_hash != target, '历史测试目标相同')
            load(page, shared)
            page.wait_for_function('id => document.activeElement.id === id', arg=target[1:])
            top = page.locator('[id="' + target[1:] + '"]').evaluate('el => el.getBoundingClientRect().top')
            toolbar = page.locator('.topbar').evaluate('el => el.getBoundingClientRect().bottom')
            check(top >= toolbar + 8, f'锚点标题被顶栏遮挡: {top}/{toolbar}')
            report['anchorTop'] = top
            page.screenshot(path=str(output / f'{theme}-{width}-anchor.png'))
            page.set_viewport_size({'width': 375, 'height': 900})
            load(page, shared)
            page.wait_for_function('id => document.activeElement.id === id', arg=target[1:])
            top = page.locator('[id="' + target[1:] + '"]').evaluate('el => el.getBoundingClientRect().top')
            toolbar = page.locator('.topbar').evaluate('el => el.getBoundingClientRect().bottom')
            check(top >= toolbar + 8, f'手机锚点标题被顶栏遮挡: {top}/{toolbar}')
            report['mobileAnchorTop'] = top
            page.screenshot(path=str(output / f'{theme}-{width}-mobile-anchor.png'))
    if copy.count():
        page.locator('[data-tk-lang-toggle]').click()
        page.wait_for_function("() => window.TKI18N.lang === 'en'")
        check(copy.inner_text() == 'Copy code', '语言切换未更新复制按钮')
        check(copy.get_attribute('aria-label') == 'Copy code block 1', '语言切换未更新复制名称')
        page.locator('[data-tk-lang-toggle]').click()
        page.wait_for_function("() => window.TKI18N.lang === 'zh'")
        check(copy.inner_text() == '复制代码', '中文复制按钮未恢复')
    page.set_viewport_size({'width': 794, 'height': 1123})
    page.locator('#reader-pager').scroll_into_view_if_needed()
    page.wait_for_function("() => document.querySelector('#reader-reward').classList.contains('on')")
    check(page.locator('#reader-pager').is_visible() and page.locator('#reader-reward').is_visible(), '屏幕阅读辅助功能未显示')
    page.emulate_media(media='print')
    for selector in ('#reader-pager', '#reader-reward', '#reader-actions'):
        check(page.locator(selector).evaluate('el => getComputedStyle(el).display') == 'none', f'打印仍包含辅助区域: {selector}')
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
    page.screenshot(path=str(output / f'{theme}-{width}-print-ending.png'))
    page.wait_for_function("() => matchMedia('print').matches && innerWidth === 794")
    page.locator('.reader-code').first.screenshot(path=str(output / f'{theme}-{width}-print-code.png'))
    print_state = page.evaluate("""() => {
      const pre = document.querySelector('#reader-body .code-block');
      const wrap = document.querySelector('#reader-body .table-wrap');
      return {codeWrap:getComputedStyle(pre).whiteSpace, codeOverflow:pre.scrollWidth-pre.clientWidth,
        tableOverflow:wrap.scrollWidth-wrap.clientWidth, toolbar:getComputedStyle(document.querySelector('.code-tools')).display,
        minCell:getComputedStyle(wrap.querySelector('td')).minWidth, color:getComputedStyle(pre).color};
    }""")
    check(print_state['codeWrap'] == 'pre-wrap', '打印代码未换行')
    check(print_state['codeOverflow'] <= 1 and print_state['tableOverflow'] <= 1, '打印内容横向裁切')
    check(print_state['toolbar'] == 'none' and print_state['minCell'] == '0px', '打印工具栏或列宽未调整')
    check(print_state['color'] == 'rgb(0, 0, 0)', '打印代码文字颜色错误')
    report['print'] = print_state
    report['pageErrors'] = errors
    check(all('clipboard' in error.lower() or 'write' in error.lower() for error in errors), '出现非预期页面错误')
    page.close()
    return report


def verify_mermaid(context, base):
    page = context.new_page()
    load(page, f"{base}/?{urlencode({'path': DEFAULT_PATHS[2], 'theme': 'light'})}")
    page.locator('.mmd-figure svg').first.wait_for()
    source = page.locator('pre.mermaid').first.evaluate('el => el.dataset.mermaidSource')
    context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=base)
    page.locator('.mmd-btn[data-act="copy"]').first.click()
    page.wait_for_function("() => document.querySelector('.mmd-copy-status')?.textContent === '已复制'")
    assert page.evaluate('navigator.clipboard.readText()') == source, 'Mermaid copied rendered labels instead of source'
    svg = page.locator('pre.mermaid svg').first
    previous = svg.element_handle()
    page.locator('[data-tk-theme-toggle]').click()
    page.wait_for_function("node => !node.isConnected", arg=previous)
    svg.wait_for()
    page.locator('.mmd-btn[data-act="in"]').first.click()
    maximum = svg.evaluate('el => parseFloat(el.style.maxHeight)')
    assert maximum >= 200, 'Theme switch broke graph resize control'
    page.locator('.mmd-btn[data-act="copy"]').first.click()
    page.wait_for_function("() => document.querySelector('.mmd-copy-status').textContent === '已复制'")
    assert page.evaluate('navigator.clipboard.readText()') == source, 'Theme switch changed copied source'
    page.close()
    return True


def verify_document_structure(context, base, output):
    page = context.new_page()
    list_path = '工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/任务分解的质量决定Agent的上限.md'
    repeated_path = '工程知识/缺陷分析：从个案到体系/安全/案例四十四：投毒不是写错，是写给你看——依赖投毒的三个真实剧本.md'
    sql_path = '工程知识/数据系统：在并发与故障中保存事实/查询与索引/列存与向量化执行：OLAP引擎快的两个来源.md'
    for theme in ('light', 'dark'):
        page.set_viewport_size({'width': 375, 'height': 900})
        response = page.goto(f"{base}/?{urlencode({'path': sql_path, 'theme': theme})}", wait_until='domcontentloaded')
        assert response.status == 200
        emphasis = page.locator('#reader-body strong').filter(has_text='SELECT * 是列存的反模式')
        emphasis.wait_for()
        assert emphasis.inner_text() == 'SELECT * 是列存的反模式'
        assert page.locator('#reader-title').evaluate('el => el.tagName') == 'H1'
        emphasis.locator('xpath=..').screenshot(path=str(output / f'{theme}-sql-emphasis.png'))
        load(page, f"{base}/?{urlencode({'path': list_path, 'theme': theme})}")
        nested = page.locator('#reader-body li > ul li').filter(has_text='可并行')
        assert nested.count() == 1, 'Nested list relation lost'
        parent = nested.locator('xpath=../..')
        assert '可恢复' in parent.inner_text(), 'Nested list has wrong parent'
        geometry = nested.evaluate("el => ({child:el.getBoundingClientRect().left,parent:el.parentElement.parentElement.getBoundingClientRect().left})")
        assert geometry['child'] >= geometry['parent'] + 20, 'Nested list indentation missing'
        parent.screenshot(path=str(output / f'{theme}-nested-list.png'))
        page.set_viewport_size({'width': 1440, 'height': 900})
        response = page.goto(f"{base}/?{urlencode({'path': repeated_path, 'theme': theme})}", wait_until='domcontentloaded')
        assert response.status == 200
        page.wait_for_function("() => [...document.querySelectorAll('#reader-body h3')].filter(h=>(h.firstChild?h.firstChild.textContent:h.textContent).trim()==='机制').length === 3")
        ids = page.locator('#reader-body h3').evaluate_all("els => els.filter(el=>(el.firstChild?el.firstChild.textContent:el.textContent).trim()==='机制').map(el=>el.id)")
        assert len(set(ids)) == 3, 'Repeated headings have duplicate ids'
        for index, ident in enumerate(ids):
            page.locator('#reader-toc a').filter(has_text='机制').nth(index).click()
            page.wait_for_function('id => document.activeElement.id === id && decodeURIComponent(location.hash) === "#"+id', arg=ident)
            assert page.locator('[id="' + ident + '"]').evaluate('el => el.getBoundingClientRect().top') > 70
            if index == 2:
                page.screenshot(path=str(output / f'{theme}-repeated-heading.png'))
                shared = page.url
                page.goto('about:blank')
                page.goto(shared, wait_until='domcontentloaded')
                page.wait_for_function('id => document.activeElement.id === id', arg=ident)
    page.close()
    print('Nested lists and repeated heading navigation: passed', flush=True)


def main():
    parser = argparse.ArgumentParser(description='真实文章链接、键盘、复制与锚点交互检查')
    parser.add_argument('--base', default='http://127.0.0.1:18789')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'article-interactions')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for theme in ('light', 'dark'):
            for width in (375, 1440):
                context = browser.new_context(viewport={'width': width, 'height': 900},
                                              reduced_motion='reduce', is_mobile=width <= 760,
                                              has_touch=width <= 760)
                report = measure(context, args.base, width, theme, args.out)
                reports.append(report)
                (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'{theme} {width}: {report["failures"]}', flush=True)
                context.close()
        if not args.baseline:
            context = browser.new_context(reduced_motion='reduce')
            assert verify_mermaid(context, args.base)
            verify_document_structure(context, args.base, args.out)
            context.close()
            print('Mermaid source clipboard: passed', flush=True)
        browser.close()
    failures = sum(len(item['failures']) for item in reports)
    print(f'{len(reports)} interaction cases; {failures} failures', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
