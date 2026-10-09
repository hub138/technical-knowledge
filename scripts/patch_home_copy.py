# -*- coding: utf-8 -*-
"""首页主张卡文案改写（2026-09-25）。

原稿两张卡共用「它」作主语，左卡 4 次、右卡 4 次。卡片里「它」没有先行词，
读到「它为什么出现」要先猜指代的是技术还是这篇笔记。改为写进真实主语。
说明原是自问式短句（「之前卡在哪，没它的时候怎么办」），像目录说明；
改为说清读完拿到什么。

锚点取 `t_('中文','英文')` 完整形式：「它怎么运作」等串在 CSS 注释里也
出现（说明折行预算），只匹配中文会误伤；完整 t_() 调用在注释里不存在。
幂等：新串已在场则跳过，脚本可重复执行。
"""
from pathlib import Path

SRC = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge/index.html")
text = SRC.read_text(encoding="utf-8")

# (旧中文, 旧英文, 新中文, 新英文)
REPL = [
    ('四个问题，读到能自己下判断',
     'Four questions, until you can judge for yourself',
     '一篇只回答一件事，四步读完能自己拍板',
     'One note, one question, four steps to your own verdict'),

    ('每篇都按这套结构写——读的时候知道自己在哪一步，读完知道证据够不够',
     'Every note follows this structure — you always know which question you are on, and whether the evidence is enough',
     '每篇都从「没这套方案之前卡在哪」写到「什么情况下别用它」，数字带测试条件，结论带边界',
     'Every note runs from what was stuck before to when to leave it alone, numbers carrying test conditions, conclusions carrying limits'),

    ('它为什么出现', 'Why it exists', '卡在哪', 'What was stuck'),

    ('之前卡在哪，没它的时候怎么办', 'What was stuck before',
     '没这套方案之前，问题怎么被绕过去', 'How the problem was worked around before'),

    ('它怎么运作', 'How it works', '机制链条', 'The mechanism'),

    ('机制是什么，关键那一步发生了什么', 'The mechanism, and its key step',
     '从输入到输出的因果链，以及关键那一步发生了什么',
     'The causal chain, and what happens at the decisive step'),

    ('思路怎么来的', 'Where the idea comes from', '换掉什么假设', 'Which assumption it traded'),

    ('为什么这样设计，换了什么假设', 'Why this design, and which assumption it traded',
     '为什么这样设计，代价转嫁给了谁', 'Why this design, and who pays the cost'),

    ('什么时候不该用它', 'When not to use it', '别用它的场合', 'When to leave it alone'),

    ('代价是什么，边界在哪', 'Cost and limits',
     '边界、反例，以及失效时会怎么坏', 'Limits, counter-examples, and how it fails'),
]

# 论文卡 lead 是跨行调用，形式与上面不同，单独处理
LEADS = [
    ("const lead = t_('先扫解析，再决定读不读原文',\n"
     "                  'Skim the analysis, then pick what deserves the full paper');",
     "const lead = t_('三分钟判断这篇值不值得读原文',\n"
     "                  'Decide in three minutes whether the full paper is worth it');"),
]

# 论文卡 sub 用双引号且参数间带空格，与 REPL 的单引号紧凑形式不同
SUBS = [
    ('t_("收录的是最新研究，每篇都按同一套问题拆开：讲什么、代价在哪、能不能信。", '
     '"Recent research, each broken down along the same questions: what it claims, '
     'what it costs, whether to trust it")',
     't_("最新研究按同一套问题拆开：声称解决什么、机制靠不靠得住、数字在什么条件下测出来、能不能信。", '
     '"Recent research, taken apart along the same questions: what it claims, whether '
     'the mechanism holds, under what conditions the numbers were measured, and whether '
     'to trust it")'),
]

done = 0

for zh_old, en_old, zh_new, en_new in REPL:
    old = f"t_('{zh_old}','{en_old}')"
    new = f"t_('{zh_new}','{en_new}')"
    if new in text:
        continue
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"hit {n} times: {old[:70]}")
    text = text.replace(old, new)
    done += 1

for old, new in LEADS:
    if new in text:
        continue
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"lead hit {n} times")
    text = text.replace(old, new)
    done += 1

for old, new in SUBS:
    if new in text:
        continue
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"sub hit {n} times")
    text = text.replace(old, new)
    done += 1

SRC.write_text(text, encoding="utf-8")
print(f"home claim copy rewritten: {done} changed")
