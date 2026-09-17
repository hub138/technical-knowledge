#!/usr/bin/env python3
"""Repoint wikilinks that broke when folders were reorganised.

Background: the 2026-09 知识库管理 consolidation moved a batch of pages into
归档/, and the skill tracks were folded into 工程知识/. Links written against
the old paths still parse as wikilinks but resolve to nothing, so clicking one
in the site 404s. There were 60 such links.

The fix is mechanical and should stay that way: for each unresolvable target,
look the basename up in the vault index, and if exactly one page carries that
name, rewrite the link to its real path. Guessing at anything ambiguous is not
this script's job — it reports those and leaves them alone.

Usage:
    python3 scripts/fix-wikilinks.py            # report only
    python3 scripts/fix-wikilinks.py --apply    # rewrite the files
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knowledge_site_server", ROOT / "site" / "server.py")
SERVER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SERVER)


def plan(vault: SERVER.Vault) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, list[str]]]]:
    """Return (fixable, ambiguous) link rewrites.

    fixable: (source_note, old_target, new_target)
    ambiguous: (source_note, old_target, candidates)
    """
    fixable: list[tuple[str, str, str]] = []
    ambiguous: list[tuple[str, str, list[str]]] = []
    for relative, note in vault.notes.items():
        for target, _label in SERVER.WIKILINK_RE.findall(str(note["body"])):
            if vault.resolve_note(target, relative):
                continue
            bare = target.split("#")[0].strip()
            stem = Path(bare).stem
            candidates = vault.by_stem.get(stem, [])
            if len(candidates) == 1:
                fixable.append((relative, target, candidates[0]))
            elif len(candidates) > 1:
                ambiguous.append((relative, target, sorted(candidates)))
    return fixable, ambiguous


# Only ever rewrite the target half of [[target|label]] or [[target#heading]].
def rewrite(body: str, old: str, new: str) -> tuple[str, int]:
    pattern = re.compile(r"\[\[" + re.escape(old) + r"(?=[\]|#])")
    return pattern.subn("[[" + new, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    vault = SERVER.Vault(ROOT / "vault")
    fixable, ambiguous = plan(vault)

    if not fixable and not ambiguous:
        print("没有断链需要处理。")
        return 0

    print(f"可修复 {len(fixable)} 条，有歧义 {len(ambiguous)} 条\n")

    by_file: dict[str, list[tuple[str, str]]] = {}
    for source, old, new in fixable:
        by_file.setdefault(source, []).append((old, new))

    for source, pairs in sorted(by_file.items()):
        print(f"── {source}")
        for old, new in pairs:
            print(f"     {old}\n       -> {new}")

    if ambiguous:
        print("\n── 有歧义，需人工判断（脚本不动）")
        for source, old, candidates in ambiguous:
            print(f"   {source}\n     {old} 候选: {', '.join(candidates)}")

    if not args.apply:
        print(f"\n（未写入。加 --apply 执行 {len(by_file)} 个文件的修改。）")
        return 0

    changed = 0
    for source, pairs in by_file.items():
        path = ROOT / "vault" / source
        body = path.read_text(encoding="utf-8")
        original = body
        for old, new in pairs:
            body, count = rewrite(body, old, new)
            changed += count
        if body != original:
            path.write_text(body, encoding="utf-8")

    print(f"\n已重写 {changed} 处链接，涉及 {len(by_file)} 个文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
