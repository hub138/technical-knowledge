# 发布门禁的两份记录：给人看的 Markdown 与给页面读的 json。
#
# 为什么不由 shell 直接拼 json：原因文本里有引号、换行和路径，shell 里手工转义
# 迟早写出一份解析不了的 json，而中台读不到 json 就等于「被拦下」这件事没人知道。
#
# 用法：
#   python3 write_deploy_report.py --repo <仓库根> --stage <阶段> --result blocked|passed
#       --reason <一句话原因> [--detail <详细输出>] [--detail-file <文件>]
#       [--old <旧版本>] [--new <新版本>]
#
# 标准输出打印 Markdown 报告的路径。

import argparse
import json
import pathlib
import time

STAGE_TITLE = {
    "pytest": "站点测试（python3 -m pytest tests -q）",
    "knowledge-audit": "内容门禁（check_knowledge.sh）",
    "worktree": "临时 worktree 准备",
    "switch": "切换到新版本",
    "restart": "重启站点服务",
}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="写发布门禁的报告与状态文件")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--result", choices=["blocked", "passed"], required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--detail", default="")
    ap.add_argument("--detail-file", default="")
    ap.add_argument("--old", default="")
    ap.add_argument("--new", default="")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    repo = pathlib.Path(args.repo).resolve()
    reports = repo / ".editorial" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    blocked = args.result == "blocked"
    detail = args.detail
    if args.detail_file and pathlib.Path(args.detail_file).is_file():
        detail = pathlib.Path(args.detail_file).read_text(encoding="utf-8", errors="replace")

    target = reports / ("deploy-%s.md" % stamp)
    lines = ["# 发布%s %s" % ("被门禁拦下" if blocked else "通过门禁", stamp), ""]
    lines.append("- 仓库：%s" % repo)
    lines.append("- 阶段：%s" % STAGE_TITLE.get(args.stage, args.stage))
    lines.append("- 线上版本：%s" % (args.old or "未知"))
    lines.append("- 候选版本：%s" % (args.new or "未知"))
    if blocked:
        lines.append("- 结论：不切换、不重启，线上保持旧版本继续服务")
        lines.append("- 原因：%s" % (args.reason or "未写明"))
    else:
        lines.append("- 结论：已切换到候选版本并重启站点服务")
        if args.reason:
            lines.append("- 备注：%s" % args.reason)
    lines.append("")
    if detail.strip():
        lines.append("## 详细输出")
        lines.append("")
        lines.append("```")
        # 报告是给人读的，超长输出截到后 200 行：失败原因总在末尾
        tail = detail.strip().splitlines()[-200:]
        lines += tail
        lines.append("```")
        lines.append("")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (reports / "deploy-latest.json").write_text(json.dumps({
        "ts": time.time(),
        "blocked": blocked,
        "stage": args.stage,
        "reason": args.reason,
        "report": target.name,
        "revision": (args.new or "")[:12],
        "previous": (args.old or "")[:12],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
