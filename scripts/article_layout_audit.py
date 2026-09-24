# 文章页布局程序化审计：改前基线 + 改后复验共用同一测法。
# 测量项（design-craft 硬规则的代码可判部分）：
#   1. 首屏正文起点：reader-body 第一个元素距离视口顶部的像素（越小越好，标题之后正文立即开始）
#   2. 正文字号 / 行高 / 行宽（.reader-body p）
#   3. 同模块胶囊（reader-siblings）与来源区（reader-sources）占的首屏高度
#   4. 目录（reader-toc）是否可见、sticky 生效
#   5. 横向溢出
#   6. 标题/正文对比度（从 CSS 变量换算）
# 用 chrome-headless-shell --dump-dom + title 回传，同 layout_audit.py 的测法。
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
CHROME = Path("/data/code/AIagent/.playwright-browsers/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell")
INDEX = ROOT / "index.html"

# 每个领域挑一篇代表作（长文优先，看正文排版才有意义）
ARTICLES = [
    ("总览-知识库首页", "/?path=知识库首页.md"),
    ("缺陷分析-代表性长文", None),  # 运行时从 /api/notes 选每个领域最长的一篇
]

PROBE = r"""
<script>
(function(){
  if(location.search.indexOf('__probe=1') === -1) return;
  var waited = 0;
  (function settle(){
    var body = document.querySelector('#reader-body');
    var hasHead = body && body.children.length > 0;
    var exhausted = waited > 150;
    if((hasHead && waited > 3) || exhausted){ done(); return; }
    waited++;
    setTimeout(settle, 40);
  })();
  function done(){ document.title = '@@' + JSON.stringify(measure()); }
  function measure(){
    var out = {};
    var body = document.querySelector('#reader-body');
    var title = document.querySelector('#reader-title');
    var meta = document.querySelector('#reader-meta');
    var sources = document.querySelector('#reader-sources');
    var siblings = document.querySelector('#reader-siblings');
    var toc = document.querySelector('#reader-toc');
    var relations = document.querySelector('#reader-relations');
    var head = document.querySelector('.reader-head');
    var layout = document.querySelector('.reader-layout');

    out.pageTitle = title ? title.textContent.trim().slice(0, 40) : null;
    out.bodyChildren = body ? body.children.length : 0;

    // 1a. 头部呼吸：sticky 顶栏下缘到标题上缘的距离。
    // 只有 0 也算违规（标题顶格贴框架），下限是呼吸不是压缩。
    var topbar = document.querySelector('.topbar');
    if(topbar && title){
      out.headGap = Math.round(title.getBoundingClientRect().top - topbar.getBoundingClientRect().bottom);
    }

    // 1. 首屏正文起点
    if(body && body.firstElementChild){
      var r = body.firstElementChild.getBoundingClientRect();
      out.bodyStartY = Math.round(r.top);
    }
    // head 区各块高度
    out.headHeights = {};
    [title, meta, sources, siblings].forEach(function(el){
      if(!el) return;
      var key = el.id.replace('reader-','');
      var st = getComputedStyle(el);
      out.headHeights[key] = (st.display === 'none' || el.hidden) ? 0 : Math.round(el.getBoundingClientRect().height);
    });
    if(head){ out.headTotal = Math.round(head.getBoundingClientRect().height); }

    // 2. 正文字号/行高/行宽
    var p = body ? body.querySelector('p') : null;
    if(p){
      var st = getComputedStyle(p);
      out.prose = {
        fontSize: st.fontSize, lineHeight: st.lineHeight,
        colWidth: Math.round(p.getBoundingClientRect().width)
      };
    }
    // h2 间距核对
    var h2 = body ? body.querySelector('h2') : null;
    if(h2){
      var hs = getComputedStyle(h2);
      out.h2 = { fontSize: hs.fontSize, marginTop: hs.marginTop };
    }
    // 3. 目录状态
    if(toc){
      var ts = getComputedStyle(toc);
      out.toc = { hidden: toc.hidden, display: ts.display,
        position: ts.position, top: ts.top, entries: toc.querySelectorAll('a').length };
    } else { out.toc = null; }

    // 4. 图谱区位置（应在正文之后）
    if(relations && body){
      out.relationsAfterBody = relations.getBoundingClientRect().top > body.getBoundingClientRect().bottom - 200;
    }

    // 5. 横向溢出
    out.overflow = {
      docScrollWidth: document.documentElement.scrollWidth,
      innerWidth: innerWidth
    };
    // 6. siblings 胶囊数量与折叠态
    if(siblings){
      out.siblings = {
        collapsed: siblings.classList.contains('collapsed'),
        count: siblings.querySelectorAll('.rail-list a').length
      };
    }
    return out;
  }
})();
</script>
"""

def sample(url: str, width: int) -> dict | None:
    original = INDEX.read_text(encoding="utf-8")
    restore = (INDEX, original)
    cleaned = re.sub(
        r"<script>\s*\n?\(function\(\)\{\s*\n?\s*var waited = 0;", "",
        original, flags=re.S,
    )
    seeded = original.replace("</body>", PROBE + "</body>", 1)
    INDEX.write_text(seeded, encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as profile:
            proc = subprocess.run(
                [str(CHROME), "--headless", "--disable-gpu", "--no-first-run",
                 "--no-sandbox",
                 f"--user-data-dir={profile}", f"--window-size={width},900",
                 "--virtual-time-budget=12000", "--dump-dom", url],
                capture_output=True, text=True, timeout=120,
            )
    finally:
        restore[0].write_text(restore[1], encoding="utf-8")
    match = re.search(r"<title>@@(.*?)</title>", proc.stdout, re.S)
    if not match:
        return None
    return json.loads(match.group(1))

def main():
    base = "http://127.0.0.1:8787"
    # 从 API 拿每个领域最长的一篇
    import urllib.request
    payload = json.loads(urllib.request.urlopen(base + "/api/notes", timeout=10).read())
    notes = payload["notes"] if isinstance(payload, dict) else payload
    by_domain = {}
    for n in notes:
        d = n.get("category", "?")
        w = n.get("words", 0) or 0
        if d not in by_domain or w > by_domain[d][1]:
            by_domain[d] = (n["path"], w)
    paths = [(d, p) for d, (p, w) in by_domain.items()]
    print("代表篇（每领域最长）：" + ", ".join(d for d, _ in paths))
    for width in (1440, 768, 390):
        for d, path in paths:
            url = f"{base}/?path={urllib.parse.quote(path)}&__probe=1"
            data = sample(url, width)
            if not data:
                print(f"  ?     {d}@{width}: no reading")
                continue
            flag = []
            if data["overflow"]["docScrollWidth"] > data["overflow"]["innerWidth"] + 1:
                flag.append(f"横向溢出 {data['overflow']['docScrollWidth']}>{data['overflow']['innerWidth']}")
            if width >= 1200 and data.get("toc") and not data["toc"]["hidden"] and data["toc"]["position"] != "sticky":
                flag.append(f"目录未 sticky（{data['toc']['position']}）")
            gap = data.get("headGap")
            if gap is not None and gap < 16:
                flag.append(f"标题顶格贴顶栏（顶栏到标题 {gap}px < 16px，站点头部规范要求 26px）")
            print(f"  {d[:12]}@{width}  正文起点 {str(data.get('bodyStartY')).rjust(4)}px | 顶栏→标题 {str(gap).rjust(4)}px | head {str(data.get('headTotal')).rjust(4)}px (meta {data['headHeights'].get('meta',0)} + 来源 {data['headHeights'].get('sources',0)} + 同模块 {data['headHeights'].get('siblings',0)}) | 正文 {data.get('prose',{}).get('fontSize','?')}/{data.get('prose',{}).get('lineHeight','?')} 宽 {data.get('prose',{}).get('colWidth','?')}px | 目录 {'有' if data.get('toc') and not data['toc']['hidden'] else '无'}{data.get('toc',{}).get('entries','')}条 | 同模块 {data.get('siblings',{}).get('count','?')}篇{' 折叠' if data.get('siblings',{}).get('collapsed') else ''}")
            if flag:
                for f in flag:
                    print(f"        !! {f}")

if __name__ == "__main__":
    import urllib.parse
    main()
