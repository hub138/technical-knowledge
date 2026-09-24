from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
S = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/audit-shots/nav-round"
NOTE = "工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/NUMA让跨槽访问付出带宽与延迟代价.md"

def order(pg):
    return pg.evaluate("() => [...document.querySelector('.reader-maincol').children].map(c=>c.id)")

with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # 折叠交互
    pg.goto(BASE + "/?path=" + NOTE.replace(" ", "%20"), wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    print("初始 collapsed:", pg.evaluate("() => document.getElementById('reader-relations').classList.contains('collapsed')"))
    pg.locator(".article-relations-head").click()
    pg.wait_for_timeout(800)
    print("点击后 collapsed:", pg.evaluate("() => document.getElementById('reader-relations').classList.contains('collapsed')"))
    print("点击后顺序:", order(pg))

    # 暗色
    pg.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    pg.wait_for_timeout(900)
    pg.evaluate("() => window.scrollTo(0,0)")
    pg.screenshot(path=f"{S}/92_relations_dark.png")

    # 移动端
    p2 = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    p2.goto(BASE + "/?path=" + NOTE.replace(" ", "%20"), wait_until="domcontentloaded")
    p2.wait_for_timeout(3000)
    m = p2.evaluate("""() => {
      const rel=document.getElementById('reader-relations'), body=document.getElementById('reader-body');
      const rb=rel.getBoundingClientRect(), bb=body.getBoundingClientRect();
      return {ov: document.documentElement.scrollWidth - document.documentElement.clientWidth,
              relTop: Math.round(rb.top+window.scrollY), bodyTop: Math.round(bb.top+window.scrollY),
              relW: Math.round(rb.width), vw: document.documentElement.clientWidth};
    }""")
    print("移动端:", m)
    p2.evaluate("() => window.scrollTo(0,0)")
    p2.wait_for_timeout(600)
    p2.screenshot(path=f"{S}/93_relations_mobile.png")

    print("errors:", errs[:3] if errs else "none")
    b.close()
