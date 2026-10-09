"""核验 README 截图：非空白、非纯背景、无横向溢出（2026-09-25）。

截图可能因为 CDN 图未加载或路由空而变成一片底色，直接放进 README 会
被发现是空图。这里用像素方差与唯一色数判定是否真的有内容。
"""
from PIL import Image
import glob
import os

SHOTS = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/docs/shots"

for f in sorted(glob.glob(os.path.join(SHOTS, "*.png"))):
    im = Image.open(f).convert("RGB")
    w, h = im.size
    small = im.resize((160, 100))
    px = list(small.getdata())
    uniq = len(set(px))
    # 方差：纯色图接近 0
    mean = sum(sum(p) for p in px) / (len(px) * 3)
    var = sum((sum(p) / 3 - mean) ** 2 for p in px) / len(px)
    name = os.path.basename(f)
    size_kb = os.path.getsize(f) // 1024
    status = "OK " if uniq > 400 and var > 200 else "空图?"
    print(f"{status} {name:<16} {w}x{h} {w/h:.3f} {size_kb:>5}KB "
          f"uniq={uniq:<5} var={var:>8.0f}")
