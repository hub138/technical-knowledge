#!/usr/bin/env python3
"""把论文的「一句话总结」批量抓进摘要库。

为什么要有这个脚本
------------------
summary_ttl 那套（site/server.py 的 _fetch_paper_summary）是**按需**的：读者
翻到某篇才去抓那一篇。索引里两万六千多篇，靠读者翻要翻到什么时候？摘要库
686 条对 26441 篇，评分脚本（只评有中文摘要的）因此长期空转喊"没有待评"。

这个脚本把"抓"这件事从读者身后搬到台前：增量抓、抓完落盘、下游评分才有活干。

抓取不花模型额度
----------------
PaperNotes 每篇正文开头自带一句"一句话总结"，中文译名也在详情页的
title-cn 标签里。所以这是 HTTP GET + 正则，不是让模型翻译 —— 可以安心地
跑满量，不用心疼 token。

用法
----
  python3 scripts/fetch-paper-summaries.py --limit 500          # 抓 500 篇
  python3 scripts/fetch-paper-summaries.py --limit 2000 --concurrency 8
  python3 scripts/fetch-paper-summaries.py --stale-hours 24     # 连过期的一起重抓
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
INDEX_PATH = (
    REPOSITORY / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
    / "papernotes-index.json"
)
SUMMARY_PATH = REPOSITORY / "data" / "papernotes-summaries.json"

# 详情页里"一句话总结"的出处（与 site/server.py 的 _fetch_paper_summary 同源）
SUMMARY_RE = None  # 由 server 侧导出，避免两处正则各写一份
USER_AGENT = "technical-knowledge/1.0 (personal notes)"
TIMEOUT = 15


def _load_index() -> list[dict]:
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    papers = data.get("papers") or []
    return papers if isinstance(papers, list) else []


def _load_cache() -> dict:
    try:
        raw = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_cache(cache: dict) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUMMARY_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8"
    )
    tmp.replace(SUMMARY_PATH)  # 先写临时文件再替换，免得写一半被读到一个空库


def _parse_one_page(page: str) -> tuple[str, str]:
    """从详情页里抠一句话总结和中文译名。抓不到给空串，不猜。"""
    import html
    import re

    summary = ""
    # 一句话总结
    m = re.search(r'<p[^>]*class="[^"]*(?:summary|abstract-lead)[^"]*"[^>]*>([\s\S]{0,4000}?)</p>', page)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        summary = html.unescape(text).strip()
    summary = re.sub(r"\s+", " ", summary)
    if len(summary) > 600:
        cut = summary[:600]
        # 摘要里有 \(M\) 这类 LaTeX，按字符硬切会把右括号切掉 —— 落在
        # 没闭合的 \( 之前再切，否则前端公式匹配找不到结尾，读者看到个反斜杠。
        open_at = cut.rfind(r"\(")
        if open_at > 0 and r"\)" not in cut[open_at:]:
            cut = cut[:open_at]
        summary = cut
    # 中文译名：宁可只显示英文原题，也不自己翻译一个假译名
    title_cn = ""
    cn = re.search(r'<p[^>]*class="[^"]*title-cn[^"]*"[^>]*>([\s\S]{0,200}?)</p>', page)
    if cn:
        title_cn = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cn.group(1)))).strip()
    return summary, title_cn


def _fetch(url: str) -> tuple[str, str] | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            page = response.read(3 * 1024 * 1024).decode("utf-8", errors="replace")
    except Exception:
        return None
    return _parse_one_page(page)


def main() -> int:
    parser = argparse.ArgumentParser(description="批量把论文的一句话总结抓进摘要库")
    parser.add_argument("--limit", type=int, default=500, help="本次最多抓多少篇")
    parser.add_argument("--concurrency", type=int, default=6, help="并发数（别太猛，人家是个人站）")
    parser.add_argument("--stale-hours", type=float, default=0,
                        help="连摘要过期的也重抓（默认只补没抓过的）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    index = _load_index()
    if not index:
        print(f"索引没读到（{INDEX_PATH}），先跑 fetch-papernotes.py")
        return 2

    cache = _load_cache()
    stale_at = time.time() - args.stale_hours * 3600

    todo = []
    for paper in index:
        url = str(paper.get("url") or "")
        if not url:
            continue
        hit = cache.get(url)
        if hit and not (args.stale_hours and float(hit.get("at") or 0) < stale_at):
            if not args.stale_hours:
                continue  # 有了就跳过，增量跑
        todo.append(url)
        if len(todo) >= args.limit:
            break

    if not todo:
        total = sum(1 for p in index if str(p.get("url") or ""))
        print(f"没有要抓的：摘要库已覆盖本批候选（索引 {total} 篇 / 摘要库 {len(cache)} 条）")
        return 0

    print(f"待抓 {len(todo)} 篇（索引 {len(index)} 篇 / 摘要库现有 {len(cache)} 条）")
    started = time.time()
    done = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(_fetch, url): url for url in todo}
        for future in as_completed(futures):
            url = futures[future]
            try:
                parsed = future.result()
            except Exception:
                parsed = None
            if parsed is None:
                failed += 1
                # 抓不到也记一笔（summary 空），免得下次还重试同一批
                cache[url] = {"at": time.time(), "summary": "", "title_cn": ""}
            else:
                summary, title_cn = parsed
                if summary or title_cn:
                    cache[url] = {"at": time.time(), "summary": summary, "title_cn": title_cn}
                    done += 1
                else:
                    cache[url] = {"at": time.time(), "summary": "", "title_cn": ""}
                    failed += 1
            if len(cache) % 200 < args.concurrency:  # 每 200 条落一次盘
                _save_cache(cache)

    _save_cache(cache)
    elapsed = time.time() - started
    print(f"抓完：新增有内容 {done} 条 · 失败/空 {failed} 条 · 摘要库共 {len(cache)} 条 · "
          f"用时 {elapsed:.0f} 秒（约 {len(todo) / max(elapsed, 1):.1f} 篇/秒）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
