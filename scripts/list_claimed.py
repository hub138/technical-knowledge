"""列出已认领文章的质量指标，决定每篇改什么（2026-09-25）。

四件事的力度由现状决定：短且无图的补内容加图，长但无图的只补图，
模板腔重的只做表达修补。不看指标一律重写会破坏本就好的部分。
"""
import re
from pathlib import Path

REPO = Path("/data/code/AIagent/skills/knowledge-site/technical-knowledge")
CLAIMS = REPO / ".editorial" / "claims"


def split_body(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def count_images(body):
    return len(re.findall(r"```mermaid", body)) + len(re.findall(r"!\[[^\]]*\]\(", body))


def has_dim(body, title_kw):
    return "有" if title_kw in body else "无"


paths = sorted(CLAIMS.glob("*.json")) if CLAIMS.exists() else []
if not paths:
    paths = sorted((REPO / ".editorial").rglob("*")) if (REPO / ".editorial").exists() else []

seen = set()
for p in paths:
    try:
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        note = data.get("path") or data.get("note") or ""
    except Exception:
        continue
    if not note or note in seen:
        continue
    seen.add(note)
    f = REPO / note if not note.startswith("/") else Path(note)
    if not f.exists():
        continue
    body = split_body(f.read_text(encoding="utf-8", errors="ignore"))
    n = len(body)
    imgs = count_images(body)
    density = imgs / (n / 1000) if n else 0
    flag = []
    if n < 2200:
        flag.append("短")
    if imgs == 0:
        flag.append("无图")
    elif density < 0.3:
        flag.append("图薄")
    print(f'{n:>5}字 图{imgs} 密{density:<5.2f} {"".join(flag):<6} {f.name[:52]}')
