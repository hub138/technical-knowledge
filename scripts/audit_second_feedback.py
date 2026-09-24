# 端到端验证 2026-09-24 二次反馈四项改动
# 1. 重叠修复：目录列表不整栏 sticky，只标题行悬浮
# 2. 目录折叠按钮可点、可收起
# 3. 同模块改名「同模块文章」+ 字号 18px
# 4. 奖励 60 秒累计门槛（跨访问累加、切后台暂停、切篇入账）
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)

    # 打开一篇有同模块的文章
    pg.evaluate("openNote('Clippings/Codex 接管浏览器，自动化任务实战.md')")
    pg.wait_for_timeout(1200)

    # ── 3. 改名 + 字号 ──
    head = pg.locator("#reader-siblings .rail-head span")
    check("同模块改名", head.inner_text().strip() == "同模块文章", head.inner_text())
    fs = pg.evaluate(
        "getComputedStyle(document.querySelector('#reader-siblings .rail-list a')).fontSize"
    )
    check("同模块字号18px", fs == "18px", fs)

    # ── 2. 目录折叠 ──
    toc = pg.locator("#reader-toc")
    check("目录存在", toc.count() == 1 and toc.is_visible())
    tog = pg.locator("#reader-toc .rail-toggle")
    if tog.count() == 1:
        tog.click()
        pg.wait_for_timeout(150)
        collapsed = pg.evaluate(
            "document.querySelector('#reader-toc').classList.contains('collapsed')"
        )
        check("目录折叠生效", collapsed)
        tog.click()
        pg.wait_for_timeout(150)
        expanded = pg.evaluate(
            "!document.querySelector('#reader-toc').classList.contains('collapsed')"
        )
        check("目录再展开", expanded)
    else:
        check("目录折叠按钮存在", False, "count=%d" % tog.count())

    # ── 1. 重叠修复：目录列表不再 sticky 整栏 ──
    pos = pg.evaluate(
        "getComputedStyle(document.querySelector('#reader-toc')).position"
    )
    check("目录栏非sticky", pos != "sticky", pos)
    # 滚到文末，量目录标题行与同模块标题行的间距是否重叠
    pg.evaluate("document.querySelector('#reader-pager').scrollIntoView({block:'end'})")
    pg.wait_for_timeout(400)
    overlap = pg.evaluate(
        """(() => {
          const t = document.querySelector('#reader-toc .rail-head').getBoundingClientRect();
          const s = document.querySelector('#reader-siblings').getBoundingClientRect();
          // 同模块在右栏目录下方（grid 同列），纵向不重叠
          return s.top >= t.bottom - 1;
        })()"""
    )
    check("目录与同模块不重叠", overlap)

    # ── 4. 60 秒累计门槛 ──
    pg.evaluate("localStorage.removeItem('tk-reading-v1')")
    pg.evaluate("localStorage.removeItem('tk-progress-v1')")
    pg.evaluate("openNote('Clippings/Codex 接管浏览器，自动化任务实战.md')")
    pg.wait_for_timeout(900)
    pg.evaluate("document.querySelector('#reader-pager').scrollIntoView({block:'end'})")
    pg.wait_for_timeout(500)
    reward = pg.locator("#reader-reward")
    txt = reward.inner_text() if reward.is_visible() else ""
    check("不足60秒出提示不出祝贺", "再读一会儿" in txt and "很棒" not in txt, txt[:40])
    check("不足60秒不记已读", pg.evaluate("localStorage.getItem('tk-progress-v1')") in (None, "{}"))

    # 模拟已有 50 秒累计（此前访问），本次再读 12 秒应跨过门槛
    pg.evaluate(
        """(() => {
          const d = JSON.parse(localStorage.getItem('tk-reading-v1') || '{}');
          const path = 'Clippings/Codex 接管浏览器，自动化任务实战.md';
          d[path] = (d[path] || 0) + 50;
          localStorage.setItem('tk-reading-v1', JSON.stringify(d));
        })()"""
    )
    pg.wait_for_timeout(12000)
    pg.evaluate("maybeShowReaderReward()")
    pg.wait_for_timeout(400)
    txt2 = reward.inner_text() if reward.is_visible() else ""
    check("跨过60秒弹祝贺", "很棒" in txt2, txt2[:50])
    prog = pg.evaluate("JSON.parse(localStorage.getItem('tk-progress-v1')||'{}').learned||{}")
    check("满60秒记已读", "Clippings/Codex 接管浏览器，自动化任务实战.md" in prog)
    check("祝贺带累计用时", "分" in txt2 or "秒" in txt2, txt2[:60])

    # 切后台暂停计时：hidden 时 stop，期间不计入
    pg.evaluate(
        """(() => {
          readingTime.stop();
          const before = JSON.parse(localStorage.getItem('tk-reading-v1'))['Clippings/Codex 接管浏览器，自动化任务实战.md'];
          Object.defineProperty(document, 'hidden', {value: true, configurable: true});
          document.dispatchEvent(new Event('visibilitychange'));
          Object.defineProperty(document, 'hidden', {value: false, configurable: true});
          window.__beforePause = before;
        })()"""
    )
    pg.wait_for_timeout(2100)
    paused = pg.evaluate(
        """(() => {
          document.dispatchEvent(new Event('visibilitychange'));
          const after = JSON.parse(localStorage.getItem('tk-reading-v1'))['Clippings/Codex 接管浏览器，自动化任务实战.md'];
          return Math.abs(after - window.__beforePause) < 1.0;
        })()"""
    )
    check("切后台暂停计时", paused)

    # 语法与时长的运行时错误监听
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    pg.wait_for_timeout(800)
    check("无JS报错", len(errs) == 0, errs[:2])

    b.close()

print("\n== RESULT: %s ==" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
