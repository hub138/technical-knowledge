#!/usr/bin/env python3
"""把内嵌 .knowledge-skills/ 副本与聚合层主副本做成可对账、可晋升的双向工具。

为什么存在：skill 文档存两处——技术仓内嵌副本（跟着站点走，AI 在站点工作时
直接读）与聚合层主副本（skills/knowledge-site/ 下，Knot 平台加载用）。两边
都改是常态，靠人脑记谁新谁旧必然失同步；check_skill_drift.py 能报差异但
不做处理。本脚本补上处理的一半：

  diff       逐文件对比，列出谁新谁旧（按 mtime）
  promote    内嵌 → 主副本（站点侧改完，发布到平台侧）
  pull       主副本 → 内嵌（平台侧改完，发回站点侧）
  sync       双向收敛到较新的一方（逐文件按 mtime 胜出）

三个动作都只覆盖三个内嵌 skill 的文档文件（.md/.py/.sh），不碰其他内容；
写入前打印每一步，写完自动跑 check_skill_drift 的副本同步面确认归零。

用法：
    python3 scripts/sync_skill_copies.py diff
    python3 scripts/sync_skill_copies.py promote   # 内嵌 → 主副本
    python3 scripts/sync_skill_copies.py pull      # 主副本 → 内嵌
    python3 scripts/sync_skill_copies.py sync      # 双向收敛（按 mtime）
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMBED = REPO / ".knowledge-skills"
AGGREGATE_CANDIDATES = [
    REPO.parent,  # skills/knowledge-site（主副本与 technical-knowledge 同级）
    REPO.parent.parent,  # 更上层的聚合布局（容错）
]

DOC_SUFFIXES = {".md", ".py", ".sh"}


def aggregate_root() -> Path:
    for cand in AGGREGATE_CANDIDATES:
        if (cand / "knowledge-governor" / "SKILL.md").exists():
            return cand
    print("ERROR  找不到聚合层主副本目录（skills/knowledge-site/）")
    sys.exit(1)


def doc_files(root: Path):
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in DOC_SUFFIXES and "__pycache__" not in p.parts:
            yield p


def pairs():
    agg = aggregate_root()
    out = []
    for skill_dir in sorted(EMBED.iterdir()):
        if not skill_dir.is_dir():
            continue
        out.append((skill_dir, agg / skill_dir.name))
    return out


def describe(p: Path) -> str:
    try:
        return f"embed {time.strftime('%m-%d %H:%M', time.localtime(p.stat().st_mtime))}"
    except OSError:
        return "embed 无"


def diff_report() -> int:
    total = 0
    for embed_dir, main_dir in pairs():
        for f in doc_files(embed_dir):
            other = main_dir / f.relative_to(embed_dir)
            if not other.exists():
                print(f"仅内嵌有  {embed_dir.name}/{f.relative_to(embed_dir)}")
                total += 1
                continue
            if f.read_bytes() != other.read_bytes():
                newer = "内嵌较新" if f.stat().st_mtime > other.stat().st_mtime else "主副本较新"
                print(f"内容不同  {embed_dir.name}/{f.relative_to(embed_dir)}（{newer}）")
                total += 1
        for f in doc_files(main_dir):
            if not (embed_dir / f.relative_to(main_dir)).exists():
                print(f"仅主副本有  {embed_dir.name}/{f.relative_to(main_dir)}")
                total += 1
    print(f"\n{total} 处差异" if total else "\n两侧完全一致")
    return 1 if total else 0


def copy_side(src_root: Path, dst_root: Path, action: str) -> int:
    if not src_root.is_dir():
        print(f"ERROR  {src_root} 不存在")
        return 1
    n = 0
    for f in doc_files(src_root):
        dst = dst_root / f.relative_to(src_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and f.read_bytes() == dst.read_bytes():
            continue
        shutil.copy2(f, dst)
        print(f"  {action}  {src_root.name}/{f.relative_to(src_root)}")
        n += 1
    return n


def do_promote() -> int:
    agg = aggregate_root()
    n = sum(copy_side(e, m, "内嵌→主副本") for e, m in pairs())
    print(f"\n{n} 个文件晋升到主副本 {agg}")
    return 0


def do_pull() -> int:
    n = sum(copy_side(m, e, "主副本→内嵌") for e, m in pairs())
    print(f"\n{n} 个文件发回内嵌 {EMBED}")
    return 0


def do_sync() -> int:
    n = 0
    for embed_dir, main_dir in pairs():
        for f in doc_files(embed_dir):
            other = main_dir / f.relative_to(embed_dir)
            if not other.exists():
                shutil.copy2(f, other)
                print(f"  内嵌→主副本（新建）  {embed_dir.name}/{f.relative_to(embed_dir)}")
                n += 1
            elif f.read_bytes() != other.read_bytes():
                src, dst, label = ((f, other, "内嵌→主副本") if f.stat().st_mtime > other.stat().st_mtime
                                   else (other, f, "主副本→内嵌"))
                shutil.copy2(src, dst)
                print(f"  {label}（取较新）  {embed_dir.name}/{f.relative_to(embed_dir)}")
                n += 1
        for f in doc_files(main_dir):
            dst = embed_dir / f.relative_to(main_dir)
            if not dst.exists():
                shutil.copy2(f, dst)
                print(f"  主副本→内嵌（新建）  {embed_dir.name}/{f.relative_to(main_dir)}")
                n += 1
    print(f"\n{n} 个文件收敛完成")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="内嵌 skill 副本与聚合层主副本的对账与晋升")
    parser.add_argument("action", choices=["diff", "promote", "pull", "sync"])
    args = parser.parse_args()
    if not EMBED.is_dir():
        print(f"ERROR  内嵌副本目录不存在 {EMBED}")
        return 1
    if args.action == "diff":
        return diff_report()
    if args.action == "promote":
        return do_promote()
    if args.action == "pull":
        return do_pull()
    return do_sync()


if __name__ == "__main__":
    raise SystemExit(main())
