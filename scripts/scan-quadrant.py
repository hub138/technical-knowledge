from pathlib import Path
import re, json, sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else
            "/Users/leoqqian/Developer/technical-knowledge/vault/工程知识")

docs = [p for p in ROOT.rglob("*.md") if p.is_file()]

def split(t):
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    return (m.group(1) if m else ""), (t[m.end():] if m else t)

# 案例页集合（用于证据回流检测）
cases = {}
for p in docs:
    if "缺陷分析" in str(p):
        cases[p.stem] = p

# 全库 wikilink 索引：目标 -> [来源]
inbound = {}
for p in docs:
    t = p.read_text(encoding="utf-8")
    for tgt in re.findall(r"\[\[([^\]|#]+)", t):
        key = tgt.strip().replace(".md", "").split("/")[-1]
        inbound.setdefault(key, []).append(p)

rows = []
for p in docs:
    t = p.read_text(encoding="utf-8")
    fm, body = split(t)
    stem = p.stem
    n = len(re.sub(r"\s", "", body))

    # 排除导航页
    is_nav = re.search(r"^type:\s*(overview|map|index)", fm, re.M)
    if is_nav:
        continue

    # ---- 纵深 9 信号（6 条可脚本扫）----
    depth = 0
    gaps = []
    has_code = "```" in body
    has_num = bool(re.search(r"\d", body))
    has_rel = "关系：" in t or "相关：" in t or "## 相关" in t
    has_verify = bool(re.search(r"验证|怎么测|断言|assert|复现|退出码|观测", body))
    has_date = bool(re.search(r"^review_after:", fm, re.M)) and \
               bool(re.search(r"^updated:", fm, re.M))
    has_src = bool(re.search(r"^sources:", fm, re.M))
    # 边界信号
    has_bound = bool(re.search(r"边界|不适用|不该用|会失效|失效|反例|何时不用|前提", body))

    for ok, name in ((has_code, "无例子"), (has_num, "无数字"),
                     (has_rel, "无关系行"), (has_verify, "无验证"),
                     (has_date, "无日期"), (has_src, "无来源"),
                     (has_bound, "无边界")):
        if ok:
            depth += 1
        else:
            gaps.append(name)

    # ---- 横向 4 信号 ----
    ins = len(inbound.get(stem, []))
    outs = [x for x in re.findall(r"\[\[([^\]|#]+)", t)]
    outs = [x for x in outs if x.strip() and "缺陷分析" not in str(p)]
    cross = 0
    for o in outs:
        op = ROOT / (o.strip() + ".md")
        if not op.exists():
            for q in docs:
                if q.stem == o.strip().split("/")[-1]:
                    op = q
                    break
        if op.exists() and op.parent != p.parent:
            cross += 1
    # 案例回流
    case_ref = any(c in t for c in cases)
    # 概念辨析
    diff = bool(re.search(r"与.{2,20}的区别|和.{2,20}不同|区别于|相邻概念|容易混淆", body))

    h = 0
    hgaps = []
    for ok, name in ((ins >= 1, "无入链"), (len(outs) >= 2, "出链少"),
                     (case_ref, "无案例回流"), (diff, "无辨析")):
        if ok:
            h += 1
        else:
            hgaps.append(name)

    depth_ok = depth >= 5
    horiz_ok = h >= 2

    if depth_ok and horiz_ok:
        q = "A"
    elif depth_ok and not horiz_ok:
        q = "B"
    elif not depth_ok and horiz_ok:
        q = "C"
    else:
        q = "D"

    rows.append(dict(path=str(p.relative_to(ROOT)), q=q, n=n, ins=ins,
                     outs=len(outs), cross=cross, depth=depth, h=h,
                     gaps=gaps, hgaps=hgaps))

rows.sort(key=lambda r: ({"C": 0, "B": 1, "D": 2, "A": 3}[r["q"]], -r["ins"], r["depth"]))

from collections import Counter
c = Counter(r["q"] for r in rows)
print("象限分布:", dict(c), "总计", len(rows))
print()
for q in ("C", "B", "D", "A"):
    sub = [r for r in rows if r["q"] == q]
    print(f"===== {q} 类 ({len(sub)}) =====")
    for r in sub:
        print(f"  ins={r['ins']:<2} d={r['depth']} h={r['h']} n={r['n']:<5} "
              f"[{','.join(r['gaps']) or '-'}][{','.join(r['hgaps']) or '-'}] {r['path']}")
    print()

json.dump(rows, open("/tmp/quadrant_scan.json", "w"), ensure_ascii=False, indent=1)
print("JSON -> /tmp/quadrant_scan.json")
