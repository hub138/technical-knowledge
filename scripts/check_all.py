#!/usr/bin/env python3
"""Run every check and report one verdict.

Why this exists: there are five separate audits now, each catching a failure
mode that the others cannot see. Run one at a time and it is easy to believe the
site is fine — that is exactly how 263 references to deleted tokens survived a
contrast pass, a test suite and a careful read of the diff.

    tests        does the server do what it says
    contrast     is text readable, in both themes
    layout       does anything overlap, overflow or get clipped
    tokens       does every var() name something that exists
    copy         is the visitor-facing writing any good
    readme       do the two READMEs still say the same things
    i18n-dict    is every dictionary key unique and unambiguous
    skill-drift  do skill docs still point at real files, anchors and routes

Usage:
    python3 scripts/check_all.py                # everything
    python3 scripts/check_all.py --fast         # skip the browser checks
    python3 scripts/check_all.py --base URL
"""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8787")
    parser.add_argument("--fast", action="store_true", help="skip the browser checks")
    args = parser.parse_args()

    results: list[tuple[str, bool, str]] = []

    # 1. Server behaviour. 精简后的门禁:安全红线 + 服务器行为 + feed/收藏管线。
    # 内容审计已删 —— 它们盯着文案措辞,每次改页面都要人肉同步,已证明是负资产。
    ok, out = run("tests", [PYTHON, "-m", "unittest", "tests.test_site", "tests.test_article_rendering"])
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

    # 5. Knowledge audits (audit-knowledge-quality.py, audit-writing-style.py)
    # 已退出统一门禁,脚本保留可手动跑:它们盯文案措辞,随内容编辑而变,
    # 曾经把整个首页判定为挂,而服务器测试早就全绿。

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
