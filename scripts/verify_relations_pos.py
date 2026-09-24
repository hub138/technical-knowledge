from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"
NOTE = "工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/NUMA让跨槽访问付出带宽与延迟代价.md"

with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    pg = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/?path=" + NOTE.replace(" ", "%20"), wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)

    m = pg.evaluate("""() => {
      const r=(id)=>{const e=document.getElementById(id); if(!e)return null;
        const b=e.getBoundingClientRect();
        return {top:Math.round(b.top+window.scrollY),bot:Math.round(b.bottom+window.scrollY),h:Math.round(b.height)}};
      const rel=document.getElementById('reader-relations');
      return {title:(document.getElementById('reader-title')||{}).textContent,
              hasSvg: !!rel.querySelector('svg'),
              counter: (rel.querySelector('.article-relations-heading span')||{}).textContent,
              order: [...document.querySelector('.reader-maincol').children].map(c=>c.id),
              head:r('reader-head'), rel:r('reader-relations'),
              body:r('reader-body'), pager:r('reader-pager')};
    }""")
    print("标题:", m["title"])
    print("图谱计数:", m["counter"], "| 有图:", m["hasSvg"])
    print("maincol 顺序:", m["order"])
    print("head:", m["head"])
    print("rel :", m["rel"])
    print("body:", m["body"])
    print("pager:", m["pager"])

    pg.evaluate("() => window.scrollTo(0,0)")
    pg.wait_for_timeout(800)
    pg.screenshot(path=f"{S}/91_relations_after.png")
    print("errors:", errs[:3] if errs else "none")
    b.close()
