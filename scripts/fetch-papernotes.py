"""Build a local index of PaperNotes' paper list.

Why this exists: the papers page called itself "追踪新论文" while showing 44
papers whose newest was 2024. Someone opening a page about tracking new work
saw 2017 papers at the top and nothing recent at all — the data source was
wrong, not the layout.

PaperNotes publishes 23,892 conference paper write-ups and keeps up with
venues (ICLR 2026, CVPR 2026, NeurIPS 2025). Its MkDocs search index carries
title, path and tags for every one of them, and it is a single static file:
7.8MB that downloads in under three seconds. That is small enough to keep, so
lookups become local and do not depend on PaperNotes staying up.

The site points at PaperNotes rather than copying it. Titles, tags and a link
out; the write-ups stay where they are. This page is an entry point.

Two rules carried over from fetch-papers.py, both learned the hard way:

  - Never invent metadata. A paper whose venue cannot be parsed from its path
    keeps an empty venue. A plausible-looking wrong conference is worse than
    an absent one, because nothing downstream can detect it.
  - The index is written from a real request only. Titles come from
    PaperNotes; nothing comes from this script but the normalising.

Usage:
    python3 scripts/fetch-papernotes.py            # refresh and write
    python3 scripts/fetch-papernotes.py --check    # verify, exit 1 if unreadable
    python3 scripts/fetch-papernotes.py --dry      # report without writing
    python3 scripts/fetch-papernotes.py --if-stale 24   # only fetch when >24h old

The last form is what a daily timer calls: it is a no-op when the index is
already fresh, so firing it more often than once a day costs nothing.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import unicodedata
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = (
    ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
    / "papernotes-index.json"
)

SEARCH_INDEX = "https://papernotes.org/search/search_index.json"

# robots.txt is `Allow: /` with `Crawl-delay: 1`. One request per run, so the
# delay is irrelevant, but the identity should still say who is asking.
USER_AGENT = "technical-knowledge/1.0 (paper index; +https://github.com/hub138/technical-knowledge)"
TIMEOUT = 120.0

# /ICLR2026/llm_agent/some-title/ → ("ICLR", "2026", "llm_agent")
#
# 子领域那一段允许数字开头（`3d_vision`、`3d_reconstruction`），
# 第一版写的 [a-z_]+ 漏掉了它们，2101 条被判成"没有会议"。
#
# 标题那一段要先做 URL 解码：49 条带重音符号或希腊字母的
# （`g%C3%B6del_agent`、`vggt-%CF%89`）在编码形态下匹配不上。
PAPER_PATH = re.compile(r"^/([A-Za-z]+)(\d{4})/([a-z0-9_]+)/([^/]+)/?$")


def subfield_of(location: str) -> tuple[str, str, str]:
    """Return (slug, 中文标签, 大类) for a paper path. Empty strings if unknown."""
    match = PAPER_PATH.match("/" + (location or "").lstrip("/"))
    if not match:
        return "", "", ""
    slug = match.group(3)
    label, category = SUBFIELDS.get(slug, ("", ""))
    return slug, label, category

# Venue names as they are usually written. Anything not listed keeps its raw
# uppercase form rather than being guessed at.
VENUE_LABEL = {
    "ICLR": "ICLR",
    "ICML": "ICML",
    "NEURIPS": "NeurIPS",
    "CVPR": "CVPR",
    "ICCV": "ICCV",
    "ECCV": "ECCV",
    "ACL": "ACL",
    "AAAI": "AAAI",
    "EMNLP": "EMNLP",
    "NAACL": "NAACL",
    "MM": "ACM MM",
    "SIGIR": "SIGIR",
    "KDD": "KDD",
    "WWW": "WWW",
    "ICRA": "ICRA",
    "IROS": "IROS",
}

# 子领域 → 中文标签，以及它属于哪个大类。
#
# 这不是猜的：PaperNotes 自己的导航就是这个两层结构，顺序也是它的顺序 ——
# LLM 排第一，尽管图像生成的篇数最多。照搬它的分法是因为读者找论文时
# 先想的是「LLM 相关的」而不是「五百篇以上的」；按篇数平铺会让
# LLM Agent（504 篇）淹在图像生成（2066 篇）旁边。
#
# 左边是 URL 里的 slug，右边是 (中文标签, 大类)。
SUBFIELDS: dict[str, tuple[str, str]] = {
    # LLM
    "llm_reasoning": ("LLM Reasoning", "LLM"),
    "llm_agent": ("LLM Agent", "LLM"),
    "multi_agent": ("Multi-Agent", "LLM"),
    "llm_alignment": ("对齐 / RLHF", "LLM"),
    "llm_safety": ("LLM 安全", "LLM"),
    "hallucination": ("幻觉检测", "LLM"),
    "llm_evaluation": ("LLM 评测", "LLM"),
    "llm_efficiency": ("LLM 效率", "LLM"),
    "llm_pretraining": ("预训练", "LLM"),
    "knowledge_editing": ("知识编辑", "LLM"),
    "llm_nlp": ("LLM 其他", "LLM"),
    # LLM 应用
    "nlp_understanding": ("NLP 理解", "LLM 应用"),
    "nlp_generation": ("文本生成", "LLM 应用"),
    "dialogue": ("对话系统", "LLM 应用"),
    "multilingual_mt": ("多语言 / 翻译", "LLM 应用"),
    "information_retrieval": ("信息检索 / RAG", "LLM 应用"),
    "code_intelligence": ("代码智能", "LLM 应用"),
    # 生成与多模态
    "image_generation": ("图像生成", "生成与多模态"),
    "video_generation": ("视频生成", "生成与多模态"),
    "multimodal_vlm": ("多模态 VLM", "生成与多模态"),
    "vlm_reasoning": ("VLM Reasoning", "生成与多模态"),
    "vlm_efficiency": ("VLM Efficiency", "生成与多模态"),
    "audio_speech": ("音频 / 语音", "生成与多模态"),
    "aigc_detection": ("AIGC 检测", "生成与多模态"),
    # 视觉感知
    "3d_vision": ("3D 视觉", "视觉感知"),
    "object_detection": ("目标检测", "视觉感知"),
    "segmentation": ("语义分割", "视觉感知"),
    "image_restoration": ("图像恢复", "视觉感知"),
    "remote_sensing": ("遥感", "视觉感知"),
    "anomaly_detection": ("异常检测", "视觉感知"),
    "human_understanding": ("人体理解", "视觉感知"),
    "video_understanding": ("视频理解", "视觉感知"),
    # 决策与具身
    "autonomous_driving": ("自动驾驶", "决策与具身"),
    "robotics": ("机器人 / 具身智能", "决策与具身"),
    "reinforcement_learning": ("强化学习", "决策与具身"),
    # 基础与理论
    "self_supervised": ("自监督 / 表示学习", "基础与理论"),
    "optimization": ("优化 / 理论", "基础与理论"),
    "causal_inference": ("因果推理", "基础与理论"),
    "interpretability": ("可解释性", "基础与理论"),
    "model_compression": ("模型压缩", "基础与理论"),
    "graph_learning": ("图学习", "基础与理论"),
    "federated_learning": ("联邦学习", "基础与理论"),
    "recommender": ("推荐系统", "基础与理论"),
    "time_series": ("时间序列", "基础与理论"),
    "learning_theory": ("学习理论", "基础与理论"),
    # 科学与跨学科
    "medical_imaging": ("医学图像", "科学与跨学科"),
    "medical_nlp": ("医疗 LLM", "科学与跨学科"),
    "computational_biology": ("计算生物", "科学与跨学科"),
    "physics": ("物理 / 科学计算", "科学与跨学科"),
    "scientific_computing": ("科学计算", "科学与跨学科"),
    "earth_science": ("地球科学", "科学与跨学科"),
    "signal_comm": ("信号 / 通信", "科学与跨学科"),
    "social_computing": ("社会计算", "科学与跨学科"),
    "ai_safety": ("AI 安全", "科学与跨学科"),
    # 其他
    "others": ("其他", "其他"),
}

# 大类顺序。LLM 打头，和 PaperNotes 自己的导航一致。
CATEGORY_ORDER = [
    "LLM", "LLM 应用", "生成与多模态", "视觉感知",
    "决策与具身", "基础与理论", "科学与跨学科", "其他",
]

# 方向标签的展示顺序。这些是实测篇数最多、且和这个知识库的主题最贴近的。
# 只是一个排序用的白名单，不影响收录 —— 没在名单里的标签照常保留。
FEATURED_TAGS = [
    "LLM Agent", "多智能体", "RAG", "记忆化", "长上下文", "长上下文推理",
    "LLM推理", "多跳推理", "GUI Agent", "Web Agent", "LLM安全", "对齐",
    "强化学习", "信息检索/RAG", "LLM评测", "模型压缩", "多模态VLM",
]


def normalise_title(title: str) -> str:
    """Key for deduplication.

    The same paper appears under more than one venue or subfield (83 such
    groups in the current index — a workshop version and a main-conference
    version, or a cross-listed paper). Keyed on the title with case, accents
    and punctuation stripped, so the two entries collapse into one.
    """
    text = unicodedata.normalize("NFKD", title or "").casefold()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)


def parse_location(location: str) -> tuple[str, str]:
    """Return (venue, conference) for a site path, or empty strings.

    Never guesses: a path that does not match the known shape gets nothing.
    """
    match = PAPER_PATH.match("/" + (location or "").lstrip("/"))
    if not match:
        return "", ""
    raw, year, _subfield, _slug = match.groups()
    # 标题段放宽到任意字符之后，年份就是唯一能挡住"这不是论文路径"的东西。
    # 会议年份落在 2010-2035 之外说明匹配到的不是论文路径，宁可不给会议。
    if not (2010 <= int(year) <= 2035):
        return "", ""
    label = VENUE_LABEL.get(raw.upper(), raw.upper())
    return label, f"{label} {year}"


def fetch() -> list[dict]:
    request = urllib.request.Request(SEARCH_INDEX, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = response.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"PaperNotes index is not JSON: {error}") from error
    docs = payload.get("docs")
    if not isinstance(docs, list) or not docs:
        raise SystemExit("PaperNotes index has no docs — its layout probably changed")
    return docs


def build(docs: list[dict]) -> dict:
    seen: dict[str, dict] = {}
    dropped = 0
    for doc in docs:
        title = " ".join((doc.get("title") or "").split())
        location = (doc.get("location") or "").strip("/")
        if not title or not location:
            dropped += 1
            continue
        key = normalise_title(title)
        if not key:
            dropped += 1
            continue
        if key in seen:
            # Keep the first. Entries arrive in conference order, so the first
            # is the one under the more prominent venue listing.
            dropped += 1
            continue
        venue, conference = parse_location(location)
        slug, subfield, category = subfield_of(location)
        tags = [t for t in (doc.get("tags") or []) if isinstance(t, str) and t.strip()]
        seen[key] = {
            "title": title,
            "url": f"https://papernotes.org/{location}/",
            "venue": venue,
            "conference": conference,
            "subfield": subfield,
            "category": category,
            "tags": tags,
        }
    return {
        "source": "papernotes.org",
        "fetched_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "total": len(seen),
        "papers": list(seen.values()),
        "dropped": dropped,
    }


def summarise(index: dict) -> str:
    papers = index["papers"]
    conferences: dict[str, int] = {}
    tags: dict[str, int] = {}
    for paper in papers:
        if paper["conference"]:
            conferences[paper["conference"]] = conferences.get(paper["conference"], 0) + 1
        for tag in paper["tags"]:
            tags[tag] = tags.get(tag, 0) + 1
    top = sorted(conferences.items(), key=lambda kv: -kv[1])[:5]
    lines = [
        f"  papers:      {len(papers):,}",
        f"  dropped:     {index.get('dropped', 0):,} (duplicate titles or missing fields)",
        f"  conferences: {', '.join(f'{c} {n:,}' for c, n in top)}",
        f"  tags:        {len(tags):,} distinct",
    ]
    missing = sum(1 for p in papers if not p["conference"])
    lines.append(f"  no venue:    {missing:,}")
    return "\n".join(lines)


def index_age_hours() -> float | None:
    """How old the checked-in index is, in hours. None if it cannot be told.

    Age comes from the index's own `fetched_at` rather than the file's mtime:
    mtime changes when the file is copied or checked out, which says nothing
    about when the data was actually fetched. A fresh clone would look
    seconds old and never refresh.
    """
    try:
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    raw = payload.get("fetched_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        stamp = datetime.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        # 没带时区的按 UTC 读，与写入端一致（build() 写的是 UTC）。
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - stamp).total_seconds() / 3600.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in index is readable and sane")
    parser.add_argument("--dry", action="store_true", help="report without writing")
    # 2026-09-26 新增：定时抓取的入口。PaperNotes 的会议论文是按批次放出来的，
    # 一天抓一次足够；但定时器可能被重复触发（服务重启、cron 与站内调度并存、
    # 手工补跑），每次都真抓会白白打一次对方站。这个开关让「只在够旧时才抓」
    # 成为脚本自己的能力 —— 调用方不必各自判断新鲜度，重复调用天然幂等。
    parser.add_argument("--if-stale", type=float, metavar="HOURS", default=0.0,
                        help="only fetch when the index is older than HOURS")
    args = parser.parse_args()

    if args.if_stale > 0:
        age = index_age_hours()
        # 下限取 0，不是「小于就算新鲜」：fetched_at 若被写成未来时间（时钟
        # 前跳、时区写错、手工改文件），年龄是负数，任何 if-stale 阈值都能
        # 满足「< 阈值」，于是每次都判定新鲜、永远不再抓 —— 一个越用越错的
        # 静默故障。负年龄按「不知道」处理，走抓取这一支。
        if age is not None and 0 <= age < args.if_stale:
            print(f"papernotes index is {age:.1f}h old "
                  f"(< {args.if_stale:g}h) — nothing to do")
            return
        if age is None or (age is not None and age < 0):
            print("papernotes index has no usable fetched_at — fetching")

    if args.check:
        # The check never touches the network: it verifies the file that is
        # checked in, so a PaperNotes outage cannot fail this repository's CI.
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"missing {INDEX.relative_to(ROOT)} — run: python3 scripts/fetch-papernotes.py")
            sys.exit(1)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            print(f"cannot read {INDEX.relative_to(ROOT)}: {error}")
            sys.exit(1)
        papers = index.get("papers")
        if not isinstance(papers, list) or not papers:
            print("index has no papers")
            sys.exit(1)
        problems = []
        for paper in papers:
            if not paper.get("title") or not paper.get("url"):
                problems.append(f"entry missing title or url: {paper!r}")
                break
            if not str(paper["url"]).startswith("https://papernotes.org/"):
                problems.append(f"url not on papernotes.org: {paper['url']}")
                break
        if problems:
            print(f"index is malformed ({len(problems)} problem(s)):")
            for problem in problems:
                print(f"  {problem}")
            sys.exit(1)
        print(f"papernotes index is readable ({len(papers):,} papers)")
        return

    try:
        docs = fetch()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as error:
        print(f"cannot reach PaperNotes: {error}")
        sys.exit(1)

    index = build(docs)
    print(f"PaperNotes search index: {len(docs):,} docs")
    print(summarise(index))

    if args.dry:
        print(f"would write {len(index['papers']):,} paper(s) to {INDEX.name}")
        return

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    # indent=1 keeps the file diffable when a venue is added. 5MB is fine.
    #
    # 原子写（2026-09-26）：这个索引 5MB，落盘要好几百毫秒，而站点每次请求
    # 都可能读它。直接 write_text 会让读到一半的请求拿到截断的 JSON —— 页面
    # 上表现为「论文列表空了」，而文件其实完好。先写同目录的临时文件再 rename，
    # 读者要么看到旧版要么看到新版，不会看到中间态。临时文件放同目录，是因为
    # rename 跨文件系统会退化成拷贝，原子性就没了。
    payload = json.dumps(index, ensure_ascii=False, indent=1) + "\n"
    tmp = INDEX.with_name(INDEX.name + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(INDEX)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    print(f"wrote {INDEX.relative_to(ROOT)} "
          f"({INDEX.stat().st_size / 1048576:.1f}MB)")


if __name__ == "__main__":
    main()
