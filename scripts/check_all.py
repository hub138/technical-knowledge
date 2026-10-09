#!/usr/bin/env python3
"""Run every check and report one verdict.

Why this exists: there are five separate audits now, each catching a failure
mode that the others cannot see. Run one at a time and it is easy to believe the
site is fine — that is exactly how 263 references to deleted tokens survived a
contrast pass, a test suite and a careful read of the diff.

    tests             does the server do what it says
    contrast          is text readable, in both themes
    layout            does anything overlap, overflow or get clipped
    tokens            does every var() name something that exists
    copy              is the visitor-facing writing any good
    readme            do the two READMEs still say the same things
    i18n-dict         is every dictionary key unique and unambiguous
    skill-drift       do skill docs still point at real files, anchors and routes
    knowledge-quality do notes carry the frontmatter contract (ERROR blocks, rest warns)
    writing-style     prose findings, recorded only

Usage:
    python3 scripts/check_all.py                # everything
    python3 scripts/check_all.py --fast         # skip the browser checks
    python3 scripts/check_all.py --base URL
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

# Pages checked in both themes by the contrast audit, and the file each serves.
CONTRAST_PAGES = [
    ("/", "index.html"),
    ("/projects", "projects/index.html"),
    ("/insights", "site/insights.html"),
    ("/apps/learning/index.html", "apps/learning/index.html"),
    ("/apps/learning/openmaic.html", "apps/learning/openmaic.html"),
    ("/apps/learning/intuition.html", "apps/learning/intuition.html"),
    ("/apps/learning/transfer.html", "apps/learning/transfer.html"),
    ("/apps/learning/history.html", "apps/learning/history.html"),
    ("/apps/agent-evaluation/index.html", "apps/agent-evaluation/index.html"),
    ("/papers", "papers/index.html"),
    ("/sources", "sources/index.html"),
]


def run(label: str, argv: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    ok = proc.returncode == 0
    return ok, output


# 知识审计里算 ERROR 的发现：下游代码真的会读这几样东西。
# metadata:* 是 frontmatter 契约字段，source 是来源，两者缺了页面与复查闭环就失真。
BLOCKING_QUALITY = ("metadata:", "source")


def knowledge_quality() -> tuple[bool, str]:
    """知识契约审计：ERROR 阻断，其余只记录。"""
    _ok, out = run("knowledge-quality",
                   [PYTHON, str(ROOT / "scripts/audit-knowledge-quality.py"), "--json"])
    findings = json.loads(out)
    errors, warns = [], []
    for finding in findings:
        missing = finding.get("missing", [])
        blocking = [m for m in missing if m.startswith(BLOCKING_QUALITY)]
        (errors if blocking else warns).append(finding)
    note = f"ERROR {len(errors)} / WARN {len(warns)}（共 {len(findings)} 页有发现）"
    if errors:
        first = errors[0]
        note += f"；例：{first['path']} 缺 {', '.join(first['missing'])}"
    return not errors, note


def writing_style_note() -> str:
    """文风审计：全部按 WARN 记录。

    它判断的是措辞，随内容编辑天天变；拿它挡发布的结果是门禁永远关着，
    然后所有人学会忽略门禁。数量记在这里，明细自己跑脚本看。
    """
    _ok, out = run("writing-style",
                   [PYTHON, str(ROOT / "scripts/audit-writing-style.py"), "--json"])
    findings = json.loads(out)
    rules = sorted({f.get("rule", "?") for f in findings})
    note = f"WARN {len(findings)}（不阻断）"
    if rules:
        note += "；规则：" + "、".join(rules[:3])
    return note


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8787")
    parser.add_argument("--fast", action="store_true", help="skip the browser checks")
    args = parser.parse_args()

    results: list[tuple[str, bool, str]] = []

    # 1. Server behaviour. 精简后的门禁:安全红线 + 服务器行为 + feed/收藏管线。
    # 内容审计已删 —— 它们盯着文案措辞,每次改页面都要人肉同步,已证明是负资产。
    ok, out = run("tests", [PYTHON, "-m", "unittest", "tests.test_site", "tests.test_article_rendering", "tests.test_project_reading"])
    summary = next((l for l in out.splitlines() if l.startswith("Ran ")), "")
    results.append(("tests", ok, summary or out.splitlines()[-1] if out else ""))

    # 2. Static source checks (no browser needed).
    #
    # The paper registry and its Chinese renderings are checked here so that
    # adding a paper without a title, or citing one the registry does not know
    # about, fails the suite instead of silently shipping English into a
    # Chinese page.
    for label, script, argv in (
        ("tokens", "scripts/token_audit.py", []),
        ("links", "scripts/link_audit.py", []),
        ("copy", "scripts/copy_audit.py", []),
        ("readme", "scripts/readme_audit.py", []),
        ("i18n-dict", "scripts/i18n_dict_audit.py", []),
        ("papers", "scripts/fetch-papers.py", ["--check"]),
        # 只校验入库的索引文件可读且形状正确，**不联网** ——
        # PaperNotes 挂掉不该让这个仓库的检查变红。
        ("papernotes", "scripts/fetch-papernotes.py", ["--check"]),
        ("paper-titles", "scripts/paper-titles.py", []),
        ("paper-fields", "scripts/paper-fields-zh.py", []),
        # skill 文档与代码的漂移检测：路径引用、代码锚点、API 路由、
        # 契约字段消费、内嵌副本同步，五类失效面全部断言化
        ("skill-drift", "scripts/check_skill_drift.py", []),
        # frontmatter 数据质量。tags 写重两遍会渲染成两枚一模一样的 chip
        # （用户报过一次），而那一层 layout / contrast 都看不见 —— 它们只量
        # 渲染结果，前端 CSS 查不出"数据里同一个值出现了两次"。
        # 只能全库扫数据：这是唯一能提前发现它的地方。
        ("data-quality", "scripts/audit-data-quality.py", []),
        # 运行时 i18n：切到英文后页面上还留着多少中文。字典审计只查词典
        # 完整性，查不出"HTML 改了、字典没跟" —— 2026-09-27 改路线页文案就
        # 漏了两句，是运行时扫出来的。这个要开浏览器，慢，单独一项。
        ("i18n-runtime", "scripts/audit-i18n-runtime.py", ["--base", args.base]),
        ("design-baseline", "scripts/audit-design-baseline.py", ["--base", args.base]),
    ):
        script_arg = script
        ok, out = run(label, [PYTHON, str(ROOT / script_arg), *argv])
        if label == "copy":
            # copy_audit reports a score rather than passing or failing
            score = next((l for l in out.splitlines() if "总分" in l), "")
            results.append((label, True, score.strip() or "score reported"))
        elif label == "i18n-dict":
            note = next(
                (l.strip() for l in out.splitlines() if "maps back to exactly one" in l),
                "checked",
            )
            results.append((label, ok, note))
        elif label == "readme":
            note = next(
                (l.strip() for l in out.splitlines() if "agree on structure" in l),
                "checked",
            )
            results.append((label, ok, note))
        elif label == "links":
            note = next(
                (l.strip() for l in out.splitlines() if "broken:" in l),
                "checked",
            )
            results.append((label, ok, note))
        else:
            note = next(
                (l.strip() for l in out.splitlines() if "referenced custom" in l),
                "checked",
            )
            results.append((label, ok, note))

    if not args.fast:
        ok, out = run("article-typography", [
            PYTHON, str(ROOT / "scripts/note_verify_shots.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines()
                     if "article/theme/width cases" in line), out)
        results.append(("article-typography", ok, note))
        ok, out = run("article-interactions", [
            PYTHON, str(ROOT / "scripts/article_interaction_audit.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines() if "interaction cases" in line), out)
        results.append(("article-interactions", ok, note))
        ok, out = run("article-loading", [
            PYTHON, str(ROOT / "scripts/article_loading_audit.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines() if "article-loading cases" in line), out)
        results.append(("article-loading", ok, note))
        ok, out = run("article-navigation", [
            PYTHON, str(ROOT / "scripts/article_navigation_media_audit.py"),
            "--base", args.base, "--navigation-only",
        ])
        note = next((line for line in out.splitlines() if "navigation/media cases" in line), out)
        results.append(("article-navigation", ok, note))
        ok, out = run("article-current-section", [
            PYTHON, str(ROOT / "scripts/toc_scrollspy_audit.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines() if "current-section cases" in line), out)
        results.append(("article-current-section", ok, note))
        ok, out = run("project-reading", [
            PYTHON, str(ROOT / "scripts/project_reading_audit.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines() if "project-reading cases" in line), out)
        results.append(("project-reading", ok, note))
        ok, out = run("subnav", [
            PYTHON, str(ROOT / "scripts/verify_subnav.py"), "--base", args.base,
        ])
        note = next((line for line in out.splitlines() if "subnav cases" in line), out)
        results.append(("subnav", ok, note))

        # 3. Layout at three widths.
        ok, out = run("layout", [PYTHON, str(ROOT / "scripts/layout_audit.py"),
                                 "--base", args.base])
        note = next(
            (l.strip() for l in out.splitlines() if "no layout problems" in l
             or "layout problem" in l),
            "",
        )
        results.append(("layout", ok, note))

        # 4. Contrast, every page in both themes.
        failures = 0
        checked = 0
        for path, source in CONTRAST_PAGES:
            for theme in ("light", "dark"):
                checked += 1
                ok, out = run(
                    "contrast",
                    [PYTHON, str(ROOT / "scripts/contrast_audit.py"),
                     f"{args.base}{path}#{theme}", source, "1440"],
                )
                if not ok:
                    failures += 1
        results.append((
            "contrast", failures == 0,
            f"{checked - failures}/{checked} page-theme combinations",
        ))

    # 5. 知识审计接回门禁，但只有 ERROR 阻断。
    #
    # 它们当初被移出去是因为「有发现就退出码 1」：一句措辞不合规就让整个门禁变红，
    # 于是没人再看它的输出。问题不在审计本身，在于它没有分级——契约字段缺失
    # （没有 title、没有 updated、没有来源）和「这句话像命令读者」不是一类事。
    #
    # 分级判据：下游代码会读的事实算 ERROR（metadata:* 与 source 两类，页面、
    # 复查闭环、门禁脚本都依赖它们），其余语义信号与文风判断算 WARN 只记录。
    # 两个审计都支持 --json，按结构分类，不去解析给人看的那份输出。
    quality_ok, quality_note = knowledge_quality()
    results.append(("knowledge-quality", quality_ok, quality_note))
    results.append(("writing-style", True, writing_style_note()))

    width = max(len(label) for label, _, _ in results)
    print("verification")
    print()
    for label, ok, note in results:
        mark = "ok  " if ok else "FAIL"
        print(f"  {mark}  {label:<{width}}  {note}")

    failed = [label for label, ok, _ in results if not ok]
    print()
    if failed:
        print(f"  {len(failed)} check(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print(f"  all {len(results)} checks pass")


if __name__ == "__main__":
    main()
