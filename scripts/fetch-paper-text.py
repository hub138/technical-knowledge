"""把论文 PDF 拉到本地，转成纯文本，给 L2 深度解读当依据。

为什么要有这一步: L2 的第 3、4 节要求公式、关键超参、消融表和数据集指标,
这些摘要里一个字都没有。凭摘要写出来的"深度解读"每一句都可能是错的,
而读者分辨不出来 —— 所以要么读到正文,要么明确留空。

用法:
    python3 scripts/fetch-paper-text.py 1706.03762 2309.06180
    python3 scripts/fetch-paper-text.py --list          # 看缓存里有什么
    python3 scripts/fetch-paper-text.py --all-missing   # 抓还没抓过的

抓下来的文本放在 论文与项目/全文/ 下, 文件名是 arXiv 编号。这个目录不进知识库,
只是写作时的中间产物 —— 正文受版权保护, 不随站点分发。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
REGISTRY = PAPER_DIR / "arxiv-registry.json"
TEXT_DIR = PAPER_DIR / "全文"

# arXiv 的 API 条款要求请求之间留间隔, 且要能识别出请求方。
USER_AGENT = "technical-knowledge/1.0 (local L2 analysis; contact: local user)"
THROTTLE_SECONDS = 3.0
PDF_URL = "https://arxiv.org/pdf/{pid}"
ABS_URL = "https://arxiv.org/abs/{pid}"

# arXiv 编号: 新旧两种格式都要认, 否则会把 "1706.03762v5" 这类带版本号的拒掉。
ARXIV_ID = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$|^[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$")


def registry_ids() -> list[str]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return sorted(data["papers"])


def fetch(pid: str) -> bytes:
    """下载一篇的 PDF。失败时抛异常, 由调用方决定是否继续。"""
    request = urllib.request.Request(
        PDF_URL.format(pid=pid),
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        payload = response.read()
    # PDF 必须以 %PDF- 开头。拿到 HTML 说明撞上了拦截页或跳转页,
    # 这种字节流喂给 pypdf 只会报一句看不懂的错, 不如在这里就说清楚。
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"返回的不是 PDF（前 8 字节: {payload[:8]!r}）")
    return payload


def to_text(payload: bytes) -> str:
    reader = PdfReader(io.BytesIO(payload))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取论文全文供 L2 解读使用")
    parser.add_argument("ids", nargs="*", help="arXiv 编号")
    parser.add_argument("--list", action="store_true", help="列出已缓存的全文")
    parser.add_argument("--all-missing", action="store_true", help="抓取所有还没抓过的")
    parser.add_argument("--force", action="store_true", help="已有缓存也重新抓")
    args = parser.parse_args()

    if args.list:
        if not TEXT_DIR.exists():
            print("还没有缓存任何全文")
            return 0
        for path in sorted(TEXT_DIR.glob("*.txt")):
            print(f"  {path.stem}  {path.stat().st_size:>9,} 字符")
        return 0

    targets = list(args.ids)
    if args.all_missing:
        have = {p.stem for p in TEXT_DIR.glob("*.txt")} if TEXT_DIR.exists() else set()
        targets += [pid for pid in registry_ids() if pid not in have]
    if not targets:
        parser.error("没有指定编号。用 --all-missing 或显式给出编号。")

    bad = [pid for pid in targets if not ARXIV_ID.match(pid)]
    if bad:
        print(f"编号格式不对: {', '.join(bad)}", file=sys.stderr)
        return 2

    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[tuple[str, str]] = []
    for index, pid in enumerate(targets):
        target = TEXT_DIR / f"{pid}.txt"
        if target.exists() and not args.force:
            print(f"  跳过 {pid}（已有缓存）")
            continue
        if index:
            time.sleep(THROTTLE_SECONDS)
        try:
            payload = fetch(pid)
            text = to_text(payload)
        except (urllib.error.URLError, RuntimeError, OSError, ValueError) as error:
            # 单篇失败不影响其余的。抓不到就记下来, 报告时如实说哪几篇没有正文,
            # 而不是拿摘要冒充正文去写 L2。
            print(f"  失败 {pid}: {error}", file=sys.stderr)
            failures.append((pid, str(error)))
            continue
        if len(text) < 3000:
            # 提取出来的字符太少, 多半是扫描版或提取器吃不下。这种"正文"没法用。
            print(f"  失败 {pid}: 只提取到 {len(text)} 字符, 可能是扫描版", file=sys.stderr)
            failures.append((pid, f"只提取到 {len(text)} 字符"))
            continue
        target.write_text(text, encoding="utf-8")
        print(f"  抓到 {pid}: {len(text):,} 字符 → {target.name}")

    if failures:
        print(f"\n{len(failures)} 篇没抓到:", file=sys.stderr)
        for pid, reason in failures:
            print(f"  {pid}: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
