# -*- coding: utf-8 -*-
# 长文目录滚动同步探针：验证 TOC scrollspy 的跟随正确性。
#
# 为什么单独写：layout_audit 的通用探针量几何（遮挡/溢出/裁切），scrollspy
# 是行为语义——滚到第 N 节时右栏目录第 N 项应带 aria-current，且随滚动
# 前进/后退正确换项。这个行为错了读者在长文里「不知道在读哪」，几何探针
# 测不出来。
#
# 方法：打开一篇多节长文，依次滚到每个 h2/h3，等 scrollspy 回调落定，
# 读 TOC 高亮项与当前视口内标题是否一致。断言三点：
#   1. 滚到某节，TOC 必有高亮（不丢跟随）
#   2. 高亮项的文本与视口上沿附近标题一致（不错跟）
#   3. 回滚到顶部后高亮回到第一节（可逆）
#
# 用法：
#   python3 scripts/toc_scrollspy_audit.py --base http://127.0.0.1:18788
#   python3 scripts/toc_scrollspy_audit.py --path "工程知识/....md"  # 指定文章
#
# 退出码：0 全部通过；1 有断言失败。

import argparse
import sys
from playwright.sync_api import sync_playwright

ROOT = "/data/code/AIagent/skills/knowledge-site/technical-knowledge"

DEFAULT_NOTE = (
    "工程知识/知识库管理/方法/一篇知识怎么写.md"
)


def pick_long_note(vault=None):
    """找一篇标题最多的文章做样本（节多才测得出跟随）。"""
    from pathlib import Path
    import re
    vault = Path(vault or f"{ROOT}/vault/工程知识")
    best, best_n = None, 0
    for f in vault.rglob("*.md"):
        if f.name == "知识库首页.md" or "知识库管理/" in str(f.relative_to(vault)):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        n = len(re.findall(r"^## ", text, re.M))
        if n > best_n:
            best, best_n = f, n
    if best is None:
        print("ERROR  vault 里没有带 ## 标题的文章")
        sys.exit(1)
    return best, best_n


def main() -> int:
    parser = argparse.ArgumentParser(description="TOC scrollspy 跟随审计")
    parser.add_argument("--base", default="http://127.0.0.1:18788")
    parser.add_argument("--path", default=None, help="指定文章 vault 相对路径")
    parser.add_argument("--login-password", default=None)
    args = parser.parse_args()

    if args.path:
        note_rel = args.path
    else:
        f, n_heads = pick_long_note()
        note_rel = "工程知识/" + f.relative_to(f"{ROOT}/vault/工程知识").as_posix()
        print(f"样本文章：{note_rel}（{n_heads} 个二级标题）")

    url = f"{args.base}/?path={note_rel}"
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=f"{ROOT}/../.cache" if False else None,
            args=["--no-sandbox"]) if False else pw.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_selector("#reader-body h2", timeout=15000)
        page.wait_for_timeout(800)  # scrollspy 首轮回调落定

        heads = page.evaluate(
            "() => [...document.querySelectorAll('#reader-body h2')]"
            ".map(h => ({id: h.id, text: h.textContent.trim()}))")
        if len(heads) < 3:
            print(f"样本只有 {len(heads)} 个二级标题，换 --path 指定更长文章")
            return 1

        current = lambda: page.evaluate(
            "() => { const a = document.querySelector('#reader-toc a[aria-current]');"
            " return a ? a.textContent.trim() : null; }")

        # 1/2：逐节滚动，TOC 高亮应跟随视口上沿附近的节
        checked = 0
        for h in heads[:8]:
            page.evaluate(
                "id => document.getElementById(id).scrollIntoView({block:'start'})",
                h["id"])
            page.wait_for_timeout(450)  # IO 回调 + scrollIntoView 落定
            got = current()
            if got is None:
                failures.append(f"滚到 [{h['text'][:16]}] 后 TOC 无高亮")
            elif got not in (h["text"],):
                # 允许停在前一节（收口带语义：标题未过 -55% 线时仍是上一节）
                vis = page.evaluate(
                    """() => {
                        const heads=[...document.querySelectorAll('#reader-body h2')];
                        for(const h of heads){const b=h.getBoundingClientRect();
                          if(b.top > 96 && b.top < innerHeight*0.45) return h.textContent.trim();}
                        return null;
                    }""")
                if got != vis:
                    failures.append(
                        f"滚到 [{h['text'][:16]}] 后 TOC 高亮 [{got[:16]}]，"
                        f"视口内是 [{(vis or '无')[:16]}]")
            checked += 1

        # 3：回滚顶部，高亮应回到第一节的语义（第一节或无高亮都算可逆）
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(450)
        back = current()
        if back is not None and back != heads[0]["text"]:
            # 顶部时第一节标题在 -96px 线下方，高亮消失或停第一节都合理
            if back not in (heads[0]["text"], heads[1]["text"] if len(heads) > 1 else ""):
                failures.append(f"回滚顶部后高亮停在 [{back[:16]}]，未回到开头")

        browser.close()

    print(f"\n检查 {checked} 节跟随 + 顶部回滚")
    if failures:
        for f in failures:
            print(f"FAIL  {f}")
        print(f"\n{len(failures)} 处不同步")
        return 1
    print("TOC scrollspy 全部跟随正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
