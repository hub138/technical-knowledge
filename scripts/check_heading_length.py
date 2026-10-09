#!/usr/bin/env python3
"""检查文章小节标题的字数。

为什么需要它：文章里的 h2/h3/h4 会被抽成目录条目（右侧「本文目录」与顶栏
「本文目录」弹层都读它们）。标题一旦写成长句，目录里就会出现一整段话当条目——
实测最严重的一条 351 字，目录整块被撑变形。

成因通常是「小标题 + 正文」粘在同一行：`## 统计与停手线复现不是"出现一次就算"…`
标题后面少一个换行，整段就被吃进标题里。

阈值（中文按字符计）：
  --warn 35  超过就看一眼，多数是正常长标题，少数是「标题+首句」粘连
  --error 60 超过基本可以确定是格式错误，必须拆

阈值依据实测分布（452 篇 / 3801 个标题）：中位 6 字、90 分位 16 字、最长 38 字是
正常标题（如「要解决的问题：repartition 后并行度在特定分区数下坍缩」）。warn 定 25
会把这批正常长标题全报成可疑（实测 32 条全是误报），定 35 才只捞真正的异常。

用法：
    python3 scripts/check_heading_length.py                  # 扫默认文章目录
    python3 scripts/check_heading_length.py --repo <目录> --error 40
    python3 scripts/check_heading_length.py --json
"""
import argparse
import json
import pathlib
import re
import sys

HEADING = re.compile(r'^(#{2,4})\s+(.+)$', re.M)


def scan(repo: pathlib.Path, warn: int, error: int):
    rows = []
    for p in sorted(repo.rglob('*.md')):
        if any(part.startswith('.') for part in p.relative_to(repo).parts):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        body = re.sub(r'^---.*?---', '', text, flags=re.S)
        for m in HEADING.finditer(body):
            title = m.group(2).strip()
            n = len(title)
            if n > warn:
                rows.append({'file': str(p), 'level': len(m.group(1)),
                             'chars': n, 'title': title[:60],
                             'level_name': 'error' if n > error else 'warn'})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='vault/工程知识')
    ap.add_argument('--warn', type=int, default=35)
    ap.add_argument('--error', type=int, default=60)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    repo = pathlib.Path(args.repo)
    if not repo.exists():
        print('找不到目录：%s' % repo, file=sys.stderr)
        return 2

    rows = scan(repo, args.warn, args.error)
    errors = [r for r in rows if r['level_name'] == 'error']

    if args.json:
        print(json.dumps({'warn': args.warn, 'error': args.error,
                          'total': len(rows), 'errors': errors},
                         ensure_ascii=False, indent=1))
    else:
        print('超 %d 字的标题 %d 条，其中超 %d 字（格式错误）%d 条'
              % (args.warn, len(rows), args.error, len(errors)))
        for r in sorted(errors, key=lambda x: -x['chars'])[:15]:
            print('  [%d字] %s' % (r['chars'], r['title']))
            print('         %s' % r['file'])
        if len(errors) > 15:
            print('  ... 其余 %d 条' % (len(errors) - 15))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
