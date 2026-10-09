import argparse
import json
import os
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('/projects/DeepTutor/README-zh', '/projects/DeepTutor/CONTAINERIZATION.md')


def verify(context, base, path, width, theme, output, index):
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    response = page.goto(f'{base}{path}?theme={theme}', wait_until='domcontentloaded')
    assert response.status == 200
    page.locator('.doc-body h1').wait_for()
    page.evaluate('document.fonts.ready')
    page.wait_for_function('theme => document.documentElement.dataset.theme === theme', arg=theme)
    failures = []
    report = {'path': path, 'width': width, 'theme': theme, 'failures': failures}

    def check(condition, message):
        if not condition:
            failures.append(message)

    measured = page.evaluate("""() => {
      const body=document.querySelector('.doc-body'), style=getComputedStyle(body);
      const fonts=selector => [...body.querySelectorAll(selector)].map(el=>parseFloat(getComputedStyle(el).fontSize));
      const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
      const painter=canvas.getContext('2d',{willReadFrequently:true});
      const color=value=>{painter.clearRect(0,0,1,1);painter.fillStyle=value;painter.fillRect(0,0,1,1);return [...painter.getImageData(0,0,1,1).data]};
      const blend=(fg,bg)=>fg.slice(0,3).map((v,i)=>v*fg[3]/255+bg[i]*(1-fg[3]/255));
      const background=el=>{const c=color(getComputedStyle(el).backgroundColor);return c[3]===255?c.slice(0,3):blend(c,el.parentElement?background(el.parentElement):[255,255,255])};
      const light=rgb=>rgb.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
      const contrasts=[...body.querySelectorAll('p,li,td,th,a,code')].map(el=>{
        const bg=background(el),a=light(blend(color(getComputedStyle(el).color),bg)),b=light(bg);
        return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
      });
      const tables=[...body.querySelectorAll('table')].map(table=>{
        const headers=[...table.querySelectorAll('thead th')];
        return Math.max(0,...[...table.querySelectorAll('tbody tr')].flatMap(row=>
          [...row.cells].map((cell,i)=>headers[i]?Math.abs(cell.getBoundingClientRect().left-headers[i].getBoundingClientRect().left):Infinity)));
      });
      return {contentWidth:body.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight),
        font:parseFloat(style.fontSize),line:parseFloat(style.lineHeight)/parseFloat(style.fontSize),
        prose:fonts('p,li,td,th'), code:fonts('.code-block code'), tableDrift:tables,
        overflow:document.documentElement.scrollWidth-innerWidth,minimumContrast:Math.min(...contrasts),
        links:[...body.querySelectorAll('a')].map(el=>getComputedStyle(el).textDecorationLine)};
    }""")
    report['layout'] = measured
    check(measured['contentWidth'] <= 760, '正文行宽超过760px')
    check(measured['overflow'] <= 1, '页面横向溢出')
    check(measured['line'] >= 1.6, '正文行高不足')
    check(measured['minimumContrast'] >= 4.5, '正文对比度不足4.5:1')
    check(all(font >= 16 for font in measured['prose'] + measured['code']), '正文或代码字号低于16px')
    check(all(value <= 1 for value in measured['tableDrift']), '表格列边界不一致')
    check(all('underline' in value for value in measured['links']), '正文链接没有下划线')
    if index == 0:
        logo = page.locator('.doc-body img[alt="DeepTutor 标志"]')
        assert logo.count() == 1
        logo.scroll_into_view_if_needed()
        page.wait_for_function('el => el.complete && el.naturalWidth > 0', arg=logo.element_handle())
        check(abs(logo.bounding_box()['height']-56) <= 2, '标志图片未保持原显示尺寸')
        banner = page.locator('.doc-body img[alt="DeepTutor"]').first
        page.wait_for_function('el => el.complete && el.naturalWidth > 0', arg=banner.element_handle())
        if width == 1440 and theme == 'light':
            sources = page.locator('.doc-body img[src^="/projects/"]').evaluate_all('els=>els.map(el=>el.getAttribute("src"))')
            for src in sources:
                image_response = page.request.get(base + src)
                check(image_response.status == 200, f'本地图片不可访问: {src} ({image_response.status})')
            report['localImagesChecked'] = len(sources)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(output / f'{index}-{theme}-{width}-opening.png'))
    code = page.locator('.doc-body .code-block').first
    if code.count():
        code.screenshot(path=str(output / f'{index}-{theme}-{width}-code.png'))
        check(code.get_attribute('tabindex') == '0', '代码缺少键盘入口')
        if code.evaluate('el => el.scrollWidth > el.clientWidth + 1'):
            code.focus()
            page.keyboard.press('ArrowRight')
            page.wait_for_function('el => el.scrollLeft > 0', arg=code.element_handle())
            check(page.evaluate('window.scrollX') == 0, '代码滚动带动整页')
            code.evaluate("""el=>new Promise(resolve=>{
              let last=el.scrollLeft,stable=0;
              const tick=()=>{const now=el.scrollLeft;stable=now===last?stable+1:0;last=now;
                if(stable>=6){el.scrollTo({left:0,behavior:'instant'});resolve()}else requestAnimationFrame(tick)};
              requestAnimationFrame(tick);
            })""")
    if index == 0:
        toc = page.locator('.doc-body a[href^="#"]').filter(has_text='快速开始').first
        toc.click()
        ident = unquote(toc.get_attribute('href')[1:])
        page.wait_for_function('id => document.activeElement.id === id', arg=ident)
        check(page.locator('[id="' + ident + '"]').evaluate('el=>el.getBoundingClientRect().top') >= 16, '目标章节缺少顶部间距')
        page.screenshot(path=str(output / f'{theme}-{width}-quick-start.png'))
        container = page.locator('.doc-body a').filter(has_text='CONTAINERIZATION.md').first
        check(container.get_attribute('href') == '/projects/DeepTutor/CONTAINERIZATION.md', '相对链接未映射源目录')
        with page.expect_navigation(wait_until='domcontentloaded') as navigation:
            container.click()
        check(navigation.value.status == 200, '目标文档无法打开')
        page.locator('.doc-body h1').wait_for()
    check(not errors, f'页面脚本错误: {errors}')
    page.close()
    return report


def main():
    parser = argparse.ArgumentParser(description='真实项目文章的图片、章节导航与排版验证')
    parser.add_argument('--base', default='http://127.0.0.1:18794')
    parser.add_argument('--out', type=Path, default=ROOT / 'audit-shots' / 'project-reading')
    args = parser.parse_args()
    temporary = ROOT / '.agent' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for index, path in enumerate(PAGES):
            for width in (375, 768, 1024, 1440):
                for theme in ('light', 'dark'):
                    context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                    report = verify(context, args.base, path, width, theme, args.out, index)
                    reports.append(report)
                    (args.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(f'{path} {width} {theme}: {report["failures"]}', flush=True)
                    context.close()
        browser.close()
    failures = sum(len(report['failures']) for report in reports)
    print(f'{len(reports)} project-reading cases; {failures} failures')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
