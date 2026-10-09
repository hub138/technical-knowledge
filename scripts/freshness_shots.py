# 新鲜度改动的截图取证：首页、文章页、/insights、/sources 四个页面，
# 桌面与窄屏各一张，中英两种语言，顺带把控制台错误收齐。
#
# 为什么要脚本而不是手点：控制台错误只在页面运行时出现，改完 innerHTML 拼接串
# 之后最容易留下的就是一个静默的 TypeError——页面看着正常，某一块不渲染。
# 每个页面都挂 console 与 pageerror 监听，有错就非零退出。
#
# 用法：
#   python3 scripts/freshness_shots.py --base http://127.0.0.1:18788 --out audit-shots/freshness
#   [--lang zh,en] [--note 文章相对路径]

import argparse
import json
import os
import pathlib
import urllib.parse

from playwright.sync_api import sync_playwright

CHROMIUM = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "narrow": {"width": 390, "height": 844}}
DEFAULT_NOTE = ("工程知识/AI 系统工程：从模型能力到生产能力/生态与选型/"
                "MCP接入必须验证协议、身份与工具约定.md")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="新鲜度页面截图与控制台检查")
    ap.add_argument("--base", default="http://127.0.0.1:18788")
    ap.add_argument("--out", default="audit-shots/freshness")
    ap.add_argument("--lang", default="zh,en")
    ap.add_argument("--note", default=DEFAULT_NOTE)
    ap.add_argument("--only", default="", help="只截某一页（home/note/insights/sources）")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    out = (root / args.out) if not os.path.isabs(args.out) else pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    note = urllib.parse.quote(args.note, safe="/")
    # 首页目录要带 domain 参数才落在目录视图上：裸 / 是入口页（欢迎区与推荐），
    # 排序按钮属于目录视图。两者都要截：入口页看整体，目录页看排序与剩余天数。
    pages = [
        ("home", "/"),
        ("directory", "/?domain=all"),
        ("note", "/?path=" + note),
        ("insights", "/insights"),
        ("sources", "/sources"),
    ]
    if args.only:
        pages = [p for p in pages if p[0] == args.only]
    problems = []
    facts = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        for lang in args.lang.split(","):
            for label, viewport in VIEWPORTS.items():
                context = browser.new_context(viewport=viewport)
                # 语言存在 localStorage 的 tk-lang 里，页面加载前写入才来得及生效
                context.add_init_script(
                    "window.localStorage.setItem('tk-lang', %s)" % json.dumps(lang))
                page = context.new_page()
                page.on("console", lambda message, tag=(lang, label): (
                    problems.append("%s/%s 控制台 %s: %s" % (tag[0], tag[1], message.type, message.text))
                    if message.type == "error" else None))
                page.on("pageerror", lambda error, tag=(lang, label): problems.append(
                    "%s/%s 页面异常: %s" % (tag[0], tag[1], error)))
                for name, path in pages:
                    page.goto(args.base + path, wait_until="load", timeout=45000)
                    page.wait_for_timeout(2500)
                    shot = out / ("%s-%s-%s.png" % (name, label, lang))
                    page.screenshot(path=str(shot), full_page=True)
                    print("截图 %s" % shot.relative_to(root) if shot.is_relative_to(root) else shot)
                    if name == "note":
                        facts["note-meta-%s" % lang] = page.inner_text("#reader-meta").strip()
                    if name == "directory":
                        page.click('[data-sort="due"]')
                        page.wait_for_timeout(1000)
                        page.screenshot(path=str(out / ("directory-due-%s-%s.png" % (label, lang))),
                                        full_page=True)
                        rows = page.query_selector_all(".note-row .path")
                        facts["directory-due-first-%s-%s" % (label, lang)] = [
                            r.inner_text().strip() for r in rows[:3]]
                    if name == "insights" and label == "desktop":
                        facts["insights-fresh-%s" % lang] = page.inner_text("#freshness").strip()[:400]
                    if name == "sources" and label == "desktop":
                        node = page.query_selector(".src-feed-fetched")
                        facts["sources-fetched-%s" % lang] = node.inner_text().strip() if node else ""
                context.close()
        browser.close()

    print()
    for key, value in facts.items():
        print("%s: %s" % (key, value))
    print()
    if problems:
        for problem in problems:
            print("问题 %s" % problem)
        return 1
    print("四个页面 × 桌面与窄屏 × %s：控制台无错误" % args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
