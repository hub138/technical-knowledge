# -*- coding: utf-8 -*-
"""论文卡四问改写（2026-09-25）。

左卡去掉「它」之后，右卡四条仍有 4 个「它」（它想解决什么 / 核心机制
是什么 / 声称的问题，与它真正适用的场景 / 边界与怎么复核…）。同一片区域
一半有代词一半没有，读起来不齐。

改写原则与左卡一致：把主语写进条目。四条分别对应解析的真实章节
（问题 / 机制 / 可复用部分 / 边界与复核清单），改后仍一一对应。
"""
from pathlib import Path

SRC = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge/index.html")
text = SRC.read_text(encoding="utf-8")

REPL = [
    # 条目名：去掉「它」，写成读者要拿走的东西
    ("t_('它想解决什么', 'What it solves')",
     "t_('解决什么问题', 'The problem it tackles')"),

    ("t_('声称的问题，与它真正适用的场景', 'The claimed problem, and where it actually applies')",
     "t_('声称解决的，与它真正适用的场景', 'What it claims to solve, and where it actually applies')"),

    ("t_('核心机制是什么', 'The core mechanism')",
     "t_('机制靠什么成立', 'What the mechanism rests on')"),

    ("t_('边界与怎么复核', 'Bounds and verification')",
     "t_('边界与复核清单', 'Limits and a verification checklist')"),
]

for old, new in REPL:
    if new in text:
        continue
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"hit {n} times: {old[:60]}")
    text = text.replace(old, new)

SRC.write_text(text, encoding="utf-8")
print(f"paper claim copy rewritten: {len(REPL)} strings")
