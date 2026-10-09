#!/usr/bin/env python3
"""给站内镜像图补「图源」标注。

背景：站点把 Commons 的图镜像进 /static/figures/ 之后，文章里只剩一个站内
路径，来源与许可信息随外链一起消失了——164 处引用里有 93 处没有任何图源
说明。CC 授权要求署名，缺了就是合规缺口。

难点是"这张本地文件对应 Commons 上的哪个文件"：
  - 本轮镜像有 URL 映射（.work/figure-map.json），能直接反查；
  - 更早那轮镜像用的是 thumb 文件名（1280px-xxx.png），原 URL 已经丢了，
    只能按名字去 Commons 搜，并且要求搜索结果规范化后与本地名对得上，
    对不上就不写——宁可不标，也不标错。

用法：先 dry-run 看匹配质量，确认后再 --apply。
"""
import argparse
import json
import pathlib
import re
import subprocess
import time
import urllib.parse

REPO = pathlib.Path(__file__).resolve().parent.parent
V = REPO / 'vault' / '工程知识'
FIG = REPO / 'site' / 'figures'
MAP = REPO / '.work' / 'figure-map.json'
UA = 'knowledge-governor/1.0 (caption backfill; local)'


def api(params):
    q = urllib.parse.urlencode(params)
    for attempt in range(3):
        proc = subprocess.run(['curl', '-s', '-A', UA,
                               'https://commons.wikimedia.org/w/api.php?' + q],
                              text=True, capture_output=True, timeout=45)
        try:
            return json.loads(proc.stdout)
        except Exception:
            time.sleep(5 + attempt * 5)
    return {}


def norm(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def commons_name_from_map(local):
    if not MAP.exists():
        return None
    m = json.loads(MAP.read_text(encoding='utf-8'))
    for url, loc in m.items():
        if loc.split('/')[-1] == local:
            segs = [s for s in url.split('?')[0].split('/') if s]
            return segs[-2] if '/thumb/' in url else segs[-1]
    return None


def commons_name_by_search(local):
    stem = re.sub(r'^\d+px-', '', re.sub(r'\.(png|jpg|jpeg|gif|svg)$', '', local))
    stem = re.sub(r'-+$', '', stem)
    if len(stem) < 8:
        return None
    data = api({'action': 'query', 'format': 'json', 'list': 'search',
                'srnamespace': '6', 'srlimit': '5',
                'srsearch': stem.replace('-', ' ')})
    hits = (data.get('query') or {}).get('search') or []
    for h in hits:
        title = h['title'][5:]  # 去掉 File:
        if norm(title).startswith(norm(stem)[:20]) or norm(stem).startswith(norm(title)[:20]):
            return title
    return None


def license_of(titles):
    """一次查多个文件的许可与作者（Commons 支持批量 titles）。"""
    out = {}
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        data = api({'action': 'query', 'format': 'json', 'prop': 'imageinfo',
                    'iiprop': 'extmetadata',
                    'titles': '|'.join('File:' + t for t in chunk)})
        pages = (data.get('query') or {}).get('pages') or {}
        for p in pages.values():
            title = (p.get('title') or '')[5:]
            info = (p.get('imageinfo') or [{}])[0].get('extmetadata') or {}
            get = lambda k: re.sub('<[^>]+>', '', info.get(k, {}).get('value', '')).strip()
            out[title] = (get('LicenseShortName') or '见 Commons 页面',
                          get('Artist') or '见 Commons 页面')
    return out


def collect_missing():
    """返回 [(文章路径, 本地文件名)]：站内图后面 3 行内没有「图源」。"""
    out = []
    for p in V.rglob('*.md'):
        lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
        for i, ln in enumerate(lines):
            m = re.match(r'!\[[^\]]*\]\((/static/figures/([^)]+))\)', ln.strip())
            if not m:
                continue
            if '图源' in '\n'.join(lines[i + 1:i + 4]):
                continue
            out.append((p, m.group(2)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    missing = collect_missing()
    print('缺图源标注的引用', len(missing))
    uniq = sorted({m[1] for m in missing})
    print('涉及唯一图片', len(uniq))

    resolved = {}
    unresolved = []
    for local in uniq:
        name = commons_name_from_map(local) or commons_name_by_search(local)
        if name:
            resolved[local] = name
        else:
            unresolved.append(local)
    print('可确定来源', len(resolved), '| 无法确定', len(unresolved))
    for u in unresolved[:8]:
        print('   未确定:', u)

    lic = license_of(sorted(set(resolved.values())))
    rows = []
    for local, name in resolved.items():
        l, a = lic.get(name, ('见 Commons 页面', '见 Commons 页面'))
        url = 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(name.replace(' ', '_'))
        rows.append((local, name, l, a, url))
    if not args.apply:
        for r in rows[:12]:
            print('样例: %-42s → %s | %s | %s' % (r[0][:42], r[1][:34], r[2][:22], r[3][:22]))
        print('（dry-run，未写入；确认无误后加 --apply）')
        return

    by_local = {r[0]: r for r in rows}
    changed = 0
    for p, local in missing:
        r = by_local.get(local)
        if not r:
            continue
        _, name, l, a, url = r
        cap = ('*图源：Wikimedia Commons《%s》，作者 %s，%s，%s。*'
               % (name.replace('_', ' '), a, l, url))
        s = p.read_text(encoding='utf-8')
        lines = s.splitlines()
        for i, ln in enumerate(lines):
            if re.match(r'!\[[^\]]*\]\(/static/figures/' + re.escape(local) + r'\)', ln.strip()):
                if i + 1 < len(lines) and lines[i + 1].strip() == '':
                    lines.insert(i + 2, cap)
                else:
                    lines.insert(i + 1, cap)
                break
        p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        changed += 1
    print('已补图源标注的引用', changed)


if __name__ == '__main__':
    main()
