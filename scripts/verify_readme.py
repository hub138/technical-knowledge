"""校验 README 引用的图片与文件都存在（2026-09-25）。

README 里的图片路径写错或图被删，在 GitHub 上会显示成裂图。这里把中英
两版所有 ![...](...) 与链接目标提取出来，逐个检查文件是否存在。
"""
from pathlib import Path
import re
import sys

ROOT = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
PATS = [re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)"), re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")]

bad = []
total = 0
for name in ("README.md", "README.zh.md"):
    text = (ROOT / name).read_text(encoding="utf-8")
    for pat in PATS:
        for target in pat.findall(text):
            total += 1
            # 站内锚点与徽章跳过
            if target.startswith(("#", "http", "mailto:")):
                continue
            if not (ROOT / target).exists():
                bad.append((name, target))

for name, target in bad:
    print(f"MISS {name}: {target}")

print(f"\n引用总数 {total}，缺失 {len(bad)}")
sys.exit(1 if bad else 0)
