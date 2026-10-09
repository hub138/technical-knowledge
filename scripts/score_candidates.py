"""给未优化文章按表达问题打分，挑出最该改的（2026-09-25）。

全库 452 篇里 298 篇已有 editorial_pass 标记，剩下一批要挑「不好的」。
不好的判定不能只靠长度：篇幅短、无图、生成痕迹重三者各有各的坏法。
这里把三个信号合成一个分，排序后取前 N 篇。
"""
import json
import re
import subprocess
from pathlib import Path

REPO = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
VAULT = REPO / "vault" / "工程知识"
SKILL = Path("/data/code/AIagent/.agent/skills/knowledge-governor")


def split_body(text):
    """取正文，去掉 frontmatter。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def count_images(body):
    """mermaid 代码块 + markdown 图都算图。"""
    mermaid = len(re.findall(r"```mermaid", body))
    md_img = len(re.findall(r"!\[[^\]]*\]\(", body))
    return mermaid + md_img


def ai_flavor_hits(path):
    """调生成痕迹扫描脚本，取命中数。"""
    try:
        out = subprocess.run(
            ["python3", str(SKILL / "scripts" / "scan_ai_flavor.py"), str(path)],
            capture_output=True, text=True, timeout=60,
        ).stdout
        return len(re.findall(r"(?m)^\s*(?:L[234]|\d+)\s*[:：]|命中", out))
    except Exception:
        return 0


rows = []
for f in VAULT.rglob("*.md"):
    text = f.read_text(encoding="utf-8", errors="ignore")
    if "editorial_pass" in text.split("\n---")[0]:
        continue
    body = split_body(text)
    n = len(body)
    imgs = count_images(body)
    # 图密度：每千字几张，目标 0.3 到 0.5
    density = imgs / (n / 1000) if n else 0
    score = 0
    if n < 2200:
        score += 3
    if imgs == 0 and n > 1500:
        score += 3
    if 0 < density < 0.3:
        score += 2
    score += min(ai_flavor_hits(f), 4)
    rows.append({
        "path": str(f.relative_to(REPO)),
        "chars": n, "imgs": imgs,
        "density": round(density, 3), "score": score,
    })

rows.sort(key=lambda r: (-r["score"], r["chars"]))
out = REPO / "scripts" / "optimize_candidates.json"
out.write_text(json.dumps(rows[:40], ensure_ascii=False, indent=2), encoding="utf-8")

for r in rows[:20]:
    print(f'{r["score"]:>2}  {r["chars"]:>5}字 图{r["imgs"]} 密{r["density"]:<5} '
          f'{r["path"][:78]}')
print(f"\n候选写入 {out.relative_to(REPO)}")
