import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = [
    "工程知识/AI 系统工程：从模型能力到生产能力/模型基础与训练/解码采样决定生成行为而不是知识本身.md",
    "工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/批处理、KV缓存、量化与并行如何改变服务容量.md",
    "工程知识/AI 系统工程：从模型能力到生产能力/知识与检索/RAG的核心是选择可引用证据.md",
    "工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论.md",
]

MEASURE = r"""() => {
  const body = document.querySelector('#reader-body');
  const rect = el => {
    const r = el.getBoundingClientRect();
    return {left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width};
  };
  const style = el => {
    const s = getComputedStyle(el);
    return {font:parseFloat(s.fontSize), line:parseFloat(s.lineHeight),
      color:s.color, background:s.backgroundColor, display:s.display};
  };
  const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const failures = [];
  const check = (ok, message) => { if (!ok) failures.push(message); };
  const base = style(body);
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const painter = canvas.getContext('2d', {willReadFrequently:true});
  const rgba = color => {
    painter.clearRect(0,0,1,1);
    painter.fillStyle = color;
    painter.fillRect(0,0,1,1);
    return [...painter.getImageData(0,0,1,1).data];
  };
  const blend = (front, back) => front.slice(0,3).map((v,i) =>
    v * front[3]/255 + back[i] * (1-front[3]/255));
  const background = el => {
    const color = rgba(getComputedStyle(el).backgroundColor);
    return color[3] === 255 ? color.slice(0,3) :
      blend(color, el.parentElement ? background(el.parentElement) : [255,255,255]);
  };
  const luminance = rgb => rgb.map(v => v/255).map(v =>
    v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4)
    .reduce((sum,v,i) => sum + v * [.2126,.7152,.0722][i], 0);
  const contrasts = [];
  const groups = {};
  for (const selector of ['p','li','th','td','blockquote','h2','h3','h4','code']) {
    const nodes = [...body.querySelectorAll(selector)].filter(el => visible(el) &&
      !el.closest('.mermaid,.mermaid-shell,.katex,svg'));
    groups[selector] = [...new Set(nodes.map(el => style(el).font))];
    for (const el of nodes) {
      const s = style(el);
      const name = `${selector} ${el.textContent.trim().slice(0,32)}`;
      if (['p','li','th','td','blockquote'].includes(selector)) {
        check(s.font >= 16 && Math.abs(s.font-base.font) < .5, `${name}: font ${s.font}, body ${base.font}`);
        check(s.line / s.font >= 1.6, `${name}: line-height ${s.line / s.font}`);
      }
      if (selector === 'code') {
        check(s.font >= 16 && s.font / base.font >= .875, `${name}: code font ${s.font}`);
      }
      const bg = background(el);
      const a = luminance(blend(rgba(s.color), bg));
      const b = luminance(bg);
      const contrast = (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
      contrasts.push(contrast);
      check(contrast >= 4.5, `${name}: contrast ${contrast.toFixed(2)}`);
    }
  }
  check(base.font >= 16, `body font ${base.font}`);
  check(rect(body).width <= 760, `body width ${rect(body).width}`);
  check(document.documentElement.scrollWidth <= innerWidth + 1, 'page horizontal overflow');
  const tables = [...body.querySelectorAll('table')].map((table, index) => {
    const wrap = table.parentElement;
    const headers = [...table.querySelectorAll('thead th')];
    const rows = [...table.querySelectorAll('tbody tr')];
    const widths = headers.map(el => rect(el).width);
    const drift = Math.max(0, ...rows.flatMap(row => [...row.cells].map((cell, i) =>
      headers[i] ? Math.max(Math.abs(rect(cell).left-rect(headers[i]).left),
        Math.abs(rect(cell).right-rect(headers[i]).right)) : Infinity)));
    check(wrap.classList.contains('table-wrap'), `table ${index}: missing scroll wrapper`);
    check(style(table).display === 'table', `table ${index}: table display ${style(table).display}`);
    check(drift <= 1, `table ${index}: column drift ${drift.toFixed(1)}px`);
    check(rect(wrap).right <= rect(body).right + 1, `table ${index}: wrapper exceeds body`);
    check(rows.length > 0 && headers.length > 0, `table ${index}: empty content`);
    check(rows.every(row => row.cells.length === headers.length), `table ${index}: inconsistent column count`);
    check(style(table.tHead).display === 'table-header-group', `table ${index}: header layout`);
    check(style(table.tBodies[0]).display === 'table-row-group', `table ${index}: body layout`);
    for (const cell of table.querySelectorAll('th,td')) {
      check(cell.scrollWidth <= cell.clientWidth + 1, `table ${index}: clipped cell ${cell.textContent.slice(0,24)}`);
      check(rect(cell).width >= 96, `table ${index}: narrow cell ${rect(cell).width.toFixed(1)}px`);
    }
    return {columns:headers.length, rows:rows.length, widths, drift,
      wrapperWidth:wrap.clientWidth, scrollWidth:wrap.scrollWidth,
      tableDisplay:style(table).display, headerDisplay:style(table.tHead).display,
      bodyDisplay:style(table.tBodies[0]).display};
  });
  const headings = [...body.querySelectorAll('h2,h3,h4')].filter(visible).map(el => ({
    tag:el.tagName, text:el.textContent.trim(), font:style(el).font}));
  const tokens = getComputedStyle(body);
  const headingSizes = {H2:parseFloat(tokens.getPropertyValue('--text-h2')),
    H3:parseFloat(tokens.getPropertyValue('--text-h3')), H4:base.font};
  for (const heading of headings) {
    check(heading.font === headingSizes[heading.tag], `${heading.tag}: unexpected font ${heading.font}`);
  }
  return {title:document.querySelector('#reader-title').textContent.trim(),
    theme:document.documentElement.dataset.theme, body:base, bodyWidth:rect(body).width,
    groups, tables, headings, minimumContrast:Math.min(...contrasts), failures};
}"""


def verify(page, base, path, theme, width, output, index):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    api = page.request.get(f"{base.rstrip('/')}/api/note?{urlencode({'path': path})}")
    assert api.status == 200, f"Article HTTP {api.status}: {path}"
    expected = api.json()
    assert expected["html"].strip(), f"Empty article: {path}"
    url = f"{base.rstrip('/')}/?{urlencode({'path': path, 'theme': theme})}"
    response = page.goto(url, wait_until="domcontentloaded")
    assert response.status == 200, f"Page HTTP {response.status}: {url}"
    page.wait_for_function("""() => {
      const body = document.querySelector('#reader-body');
      return body && body.children.length > 0 &&
        document.querySelector('#reader-title').textContent.trim().length > 0;
    }""")
    page.evaluate("document.fonts.ready")
    images = page.locator('#reader-body img')
    for image_index in range(images.count()):
        image = images.nth(image_index)
        image.scroll_into_view_if_needed()
        page.wait_for_function("img => img.complete", arg=image.element_handle())
        assert image.evaluate("img => img.naturalWidth > 0"), f"Image failed: {image.get_attribute('src')}"
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_function("""() => !document.querySelector('#reader-body pre.mermaid:not([data-processed])')""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    report = page.evaluate(MEASURE)
    assert report["title"] == expected["title"], f"Unexpected article: {report['title']}"
    assert report["theme"] == theme, f"Theme not applied: {report['theme']}"
    counts = page.evaluate("""html => {
      const expected = new DOMParser().parseFromString(html, 'text/html');
      const body = document.querySelector('#reader-body');
      return Object.fromEntries(['table','blockquote','li','.code-block','.mermaid'].map(selector =>
        [selector, [expected.querySelectorAll(selector).length, body.querySelectorAll(selector).length]]));
    }""", expected["html"])
    report["elementCounts"] = counts
    for selector, (wanted, actual) in counts.items():
        assert wanted == actual, f"Missing article elements: {selector} {actual}/{wanted}"
    report.update(path=path, url=url, width=width, screenshots=[])
    report["failures"].extend(f"pageerror: {error}" for error in errors)
    prefix = f"{index:02d}-{theme}-{width}"
    page.screenshot(path=str(output / f"{prefix}-full.png"), full_page=True)
    page.screenshot(path=str(output / f"{prefix}-opening.png"))
    report["screenshots"].extend([f"{prefix}-full.png", f"{prefix}-opening.png"])
    tables = page.locator('#reader-body .table-wrap')
    for table_index in range(tables.count()):
        wrapper = tables.nth(table_index)
        wrapper.scroll_into_view_if_needed()
        if table_index == 0:
            wrapper.evaluate("el => window.scrollBy(0, el.getBoundingClientRect().top - 180)")
            page.screenshot(path=str(output / f"{prefix}-table-context.png"))
            report["screenshots"].append(f"{prefix}-table-context.png")
        shot = f"{prefix}-table-{table_index}.png"
        wrapper.screenshot(path=str(output / shot))
        report["screenshots"].append(shot)
        scrollable = wrapper.evaluate("el => el.scrollWidth > el.clientWidth + 1")
        if scrollable:
            wrapper.evaluate("el => el.scrollLeft = el.scrollWidth")
            moved = wrapper.evaluate("el => el.scrollLeft > 0")
            if not moved:
                report["failures"].append(f"table {table_index}: cannot scroll to last column")
            shot = f"{prefix}-table-{table_index}-end.png"
            wrapper.screenshot(path=str(output / shot))
            report["screenshots"].append(shot)
            wrapper.evaluate("el => el.scrollLeft = 0")
    report["failures"] = list(dict.fromkeys(report["failures"]))
    return report


def main():
    parser = argparse.ArgumentParser(description="真实文章排版测量与截图，不修改站点源码。")
    parser.add_argument("--base", default="http://127.0.0.1:18788")
    parser.add_argument("--path", action="append", help="相对 vault 的真实文章路径，可重复")
    parser.add_argument("--width", action="append", type=int)
    parser.add_argument("--theme", choices=("light", "dark"), action="append")
    parser.add_argument("--out", type=Path, default=ROOT / "audit-shots" / "note-detail")
    parser.add_argument("--browser", default=os.environ.get("CHROME_BIN"))
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / ".agent" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(temporary)
    reports = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.browser)
        for index, path in enumerate(args.path or DEFAULT_PATHS):
            assert (ROOT / "vault" / path).is_file(), f"Article missing: {path}"
            for theme in args.theme or ("light", "dark"):
                for width in args.width or (375, 768, 1024, 1440):
                    context = browser.new_context(viewport={"width": width, "height": 900},
                                                  reduced_motion="reduce")
                    report = verify(context.new_page(), args.base, path, theme, width, output, index)
                    reports.append(report)
                    (output / "report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"{len(report['failures'])} failures: {path} {theme} {width}px", flush=True)
                    for failure in report["failures"][:8]:
                        print(f"  {failure}", flush=True)
                    context.close()
        browser.close()
    if not args.path:
        for selector in ("table", "blockquote", "li", ".code-block", ".mermaid"):
            assert any(report["elementCounts"][selector][1] for report in reports), f"Uncovered element: {selector}"
        columns = {table["columns"] for report in reports for table in report["tables"]}
        assert 2 in columns and any(count >= 4 for count in columns), "Missing two-column or wide-table coverage"
    failures = sum(len(report["failures"]) for report in reports)
    print(f"{len(reports)} article/theme/width cases; {failures} failures; evidence: {output}")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
