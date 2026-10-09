import re
import subprocess
import sys
from pathlib import Path

V = Path("vault/工程知识")


def stat(f):
    text = f.read_text(encoding="utf-8")
    body = re.sub(r"^---.*?---", "", text, flags=re.S)
    cn = len(re.findall(r"[\u4e00-\u9fa5]", body))
    en = len(re.findall(r"[A-Za-z]+", body))
    words = cn + en
    imgs = len(re.findall(r"!\[", body)) + len(re.findall(r"```mermaid", body))
    return words, imgs, body


def check(f):
    words, imgs, body = stat(f)
    density = imgs / (words / 1000) if words else 0
    r = subprocess.run(
        [sys.executable, "/data/code/AIagent/.agent/skills/knowledge-governor/scripts/article_selfcheck.py", str(f)],
        capture_output=True, text=True,
    )
    out = (r.stdout or "") + (r.stderr or "")
    err = "ERROR" in out
    if err:
        verdict = "FAIL"
    elif density < 0.3:
        verdict = "PASS 偏薄"
    elif density > 0.5:
        verdict = "PASS 偏热"
    else:
        verdict = "PASS"
    return verdict, density, err, out


files = [Path(a) for a in sys.argv[1:]] or sorted(V.rglob("*.md"))
fails = []
for f in files:
    if not f.exists():
        print(f"MISS  {f}")
        continue
    verdict, density, err, out = check(f)
    print(f"{verdict:<10} 密{density:.2f}  {str(f)[-58:]}")
    if err:
        fails.append((f, out))

print("-" * 60)
print(f"已检查 {len(files)} 个文件  FAIL: {len(fails)}")
for f, out in fails:
    print(f"\n### {f}")
    print("\n".join(l for l in out.splitlines() if "ERROR" in l)[:1200])
