"""论文的收藏与推荐。

这一层只管数据和算法，不管路由也不管页面：
    · 路由在 server.py（/api/paper/favorites、/api/paper/recommend）
    · 页面在 papers/index.html（收藏按钮、推荐位）和 index.html（主页推荐块）

为什么收藏单独一份 data/paper-favorites.json，不塞进已有的 favorites.json：
那份是 BestBlogs 文章的收藏，上限 100、字段按文章定制；论文的字段（会议、
子领域、标签、模型评的分）完全不一样，还共用 100 的额度会让"收藏 30 篇
论文"就顶满整个收藏夹。两个东西是两件事。

推荐依据（没有现成的，只能自己算）：

    推荐分 = 模型评分 × 0.7 + 兴趣契合度 × 0.3 + 新鲜度加成

    · 模型评分由 scripts/score_papers.py 定时批量产出，是"值不值得读"；
    · 兴趣契合度 = 与（收藏 + 站内已精读）论文的 Category/Tag 重合权重，
      回答"跟我读过的东西是不是一路的"；
    · 新鲜度只给很小的加成，因为论文的价值不随时间衰减 —— 但追新论文的人
      点进"追踪"页，就是想看新的，加一点点。

评分没覆盖到的论文不参与推荐：没有分的推荐是瞎推。页面上会明说"已评 N 篇"，
读者知道这个推荐的边界在哪。
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import Counter
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
FAVORITES_PATH = REPOSITORY / "data" / "paper-favorites.json"
SCORES_PATH = REPOSITORY / "data" / "paper-scores.json"
INDEX_PATH = (
    REPOSITORY / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目" / "papernotes-index.json"
)
# 站内已经写过解析的论文 —— 它们是最可靠的"这个库关心什么"的样本。
PAPER_NOTES_PATH = (
    REPOSITORY / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目" / "paper-notes.json"
)

# 论文收藏的上限比文章高：文章收藏是一次看一批里挑几条，论文是慢慢攒。
FAVORITES_CAP = 300
_FAV_LOCK = threading.Lock()

_YEAR_RE = re.compile(r"(19|20)\d{2}")

# 权重。改这里就等于改了推荐口味，注释里说清意图，免得后人当数字乱调。
W_SCORE = 0.7          # 模型评的"值不值得读"
W_AFFINITY = 0.3       # 跟我已经读的东西像不像
FRESH_BONUS = 4.0      # 最新一年论文最多加几分（小加成：价值不随时间衰减）


# --------------------------------------------------------------------------
# 收藏
# --------------------------------------------------------------------------


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, payload) -> bool:
    """原子写。收藏和评分都要能直接进 git 看 diff，写一半的 JSON 不该出现。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def load_favorites() -> list[dict]:
    raw = _read_json(FAVORITES_PATH, [])
    return raw if isinstance(raw, list) else []


def _save_favorites(entries: list[dict]) -> bool:
    return _write_json(FAVORITES_PATH, entries)


def favorite_urls() -> set[str]:
    urls = set()
    for entry in load_favorites():
        item = entry.get("item") or {}
        if isinstance(item, dict) and item.get("url"):
            urls.add(str(item["url"]))
    return urls


def favorite_add(paper: dict) -> tuple[bool, str]:
    """收藏一篇论文。判重用 url —— 论文没有"同一篇换个 id"的情况。"""
    if not str(paper.get("url") or "").strip():
        return False, "invalid"
    with _FAV_LOCK:
        entries = load_favorites()
        if any(str((e.get("item") or {}).get("url") or "") == str(paper["url"]) for e in entries):
            return False, "already_favorited"
        if len(entries) >= FAVORITES_CAP:
            return False, "favorites_full"
        snapshot = {k: paper.get(k) for k in
                    ("url", "title", "title_cn", "conference", "subfield", "category", "tags", "summary")}
        snapshot["url"] = str(paper["url"])
        entries.append({"favorited_at": time.time(), "item": snapshot})
        return (_save_favorites(entries), "")


def favorite_remove(url: str) -> int:
    with _FAV_LOCK:
        entries = load_favorites()
        kept = [e for e in entries if str((e.get("item") or {}).get("url") or "") != url]
        if len(kept) == len(entries):
            return 0
        return 1 if _save_favorites(kept) else -1


# --------------------------------------------------------------------------
# 评分
# --------------------------------------------------------------------------


def load_scores() -> dict:
    """url → {overall, dims, reason, model, at, v}。由 score_papers.py 产出。"""
    data = _read_json(SCORES_PATH, {})
    scores = data.get("scores") if isinstance(data, dict) else None
    return scores if isinstance(scores, dict) else {}


def load_index() -> list[dict]:
    data = _read_json(INDEX_PATH, {})
    papers = data.get("papers") or []
    return papers if isinstance(papers, list) else []


def attach_scores(papers: list[dict], favs: set[str] | None = None) -> list[dict]:
    """给论文列表补上 score / fav 两个字段。

    /api/papernotes 每页返回 60 条，在这里就地补，前端不用再发一次请求。
    没评过分的就是缺省值（overall 0 + scored=false），卡片上不显示分数，
    免得 0 分被看成"评了 0 分"。
    """
    scores = load_scores()
    favs = favs if favs is not None else favorite_urls()
    for paper in papers:
        record = scores.get(str(paper.get("url") or ""))
        paper["scored"] = bool(record)
        paper["overall"] = int((record or {}).get("overall") or 0)
        paper["reason"] = str((record or {}).get("reason") or "")
        paper["dims"] = (record or {}).get("dims") or {}
        paper["fav"] = str(paper.get("url") or "") in favs
    return papers


# --------------------------------------------------------------------------
# 兴趣画像与推荐
# --------------------------------------------------------------------------


def _fold(text: str) -> str:
    """标签归一化：PaperNotes 里同一概念有「物理/科学计算」和「物理 科学计算」
    两种写法，不归一化的话两个标签永远对不上，兴趣画像也会算重。"""
    return re.sub(r"[\s/·、_]+", "", text or "").casefold()


def interest_profile() -> Counter:
    """从「收藏 + 站内已精读」的论文里抽出方向词频。

    站内已精读的论文（人写过解析的）比收藏更"硬"—— 收藏可能只是随手存的，
    解析写过了说明真读过。权重按 2 倍记。
    """
    counts: Counter = Counter()
    sources: list[dict] = []
    for entry in load_favorites():
        item = entry.get("item") or {}
        if isinstance(item, dict) and item.get("url"):
            # 收藏条目本身就是快照，不用再回查索引
            sources.append(item)
    for paper in sources:
        for tag in paper.get("tags") or []:
            counts[_fold(tag)] += 1
        if paper.get("category"):
            counts[_fold(paper["category"])] += 1

    notes = _read_json(PAPER_NOTES_PATH, {})
    for key, note in (notes or {}).items():
        if not isinstance(note, dict):
            continue
        for tag in note.get("tags") or []:
            counts[_fold(tag)] += 2
        if note.get("category"):
            counts[_fold(note["category"])] += 2
        # 标题里的关键术语也算（已精读的论文往往没打全标签）
        counts[_fold(str(note.get("title") or ""))] += 1
    return counts


def _year_of(paper: dict) -> int:
    match = _YEAR_RE.search(str(paper.get("conference") or ""))
    return int(match.group(0)) if match else 0


def affinity_of(paper: dict, profile: Counter) -> float:
    """与「我读过的东西」的契合度，0-1。"""
    if not profile:
        return 0.0
    hits = 0
    for tag in paper.get("tags") or []:
        hits += profile.get(_fold(tag), 0)
    if paper.get("category"):
        hits += profile.get(_fold(paper["category"]), 0) * 2
    if paper.get("subfield"):
        hits += profile.get(_fold(paper["subfield"]), 0)
    return min(1.0, hits / 8.0)


def recommend(limit: int = 6) -> dict:
    """推荐一批论文。返回 {items, scored_total, profile_note}。

    只推**评过分**的：没有评分的推荐是瞎推，宁可页面少几条，也不摆一排
    标着"推荐"却不知道凭什么的东西。profile 空（还没收藏任何论文）时
    退化为纯评分排序，并在 note 里说明「你还没收藏，现在是按高分推的」。
    """
    scores = load_scores()
    profile = interest_profile()
    favs = favorite_urls()
    index = load_index()
    by_url = {str(p.get("url") or ""): p for p in index}

    candidates: list[dict] = []
    for url, record in scores.items():
        if url in favs:
            continue
        paper = by_url.get(url) or {"url": url, "title": url.rsplit("/", 2)[-2]}
        candidates.append((paper, record))

    # 评分都还没批出来的情况：返回空 + 提示，让页面给出一个"去评分"的入口，
    # 而不是假装没有内容。
    if not candidates:
        return {
            "items": [],
            "scored_total": 0,
            "note": "还没有论文评分。跑 scripts/score_papers.py --loop 就会慢慢攒起来。",
        }

    items = []
    newest_year = max((_year_of(p) for p, _ in candidates), default=0)
    for paper, record in candidates:
        overall = float(record.get("overall") or 0)
        affinity = affinity_of(paper, profile)
        fresh = 0.0
        year = _year_of(paper)
        if year and newest_year:
            fresh = FRESH_BONUS * max(0.0, (year - (newest_year - 3)) / 3.0)
        value = overall * W_SCORE + affinity * 10 * W_AFFINITY + fresh
        items.append(
            {
                "url": str(paper.get("url") or ""),
                "title": paper.get("title") or "",
                "title_cn": paper.get("title_cn") or "",
                "conference": paper.get("conference") or "",
                "subfield": paper.get("subfield") or "",
                "category": paper.get("category") or "",
                "tags": list(paper.get("tags") or [])[:4],
                "summary": paper.get("summary") or "",
                "overall": int(overall),
                "dims": record.get("dims") or {},
                "reason": record.get("reason") or "",
                "affinity": round(affinity, 2),
                "why": _why(record, affinity, profile),
            }
        )

    items.sort(
        key=lambda it: (it["overall"], it["affinity"]),
        reverse=True,
    )
    return {
        "items": items[:limit],
        "scored_total": len(scores),
        "note": ""
        if profile
        else f"你还没收藏或精读过论文，这一批是按模型评分排的（已评 {len(scores)} 篇）。",
    }


def _why(record: dict, affinity: float, profile: Counter) -> str:
    """给推荐位一句话理由。理由要能说清"凭什么推这条"——
    页面上只摆分数不摆理由，读者没法判断这个推荐是不是可信的。

    注意别拿模板前缀去"补"理由。试过拼成「高分 · 贴主题 · <模型理由>」，
    结果每条开头都一模一样，五条摆在一起就是模板腔；而且真有信息的那句
    被前缀挤到后半截，再截断就剩一堆碎片。分数徽章已经在卡片右上角说清
    「多少分」，理由这一行只负责说「凭什么推」。
    """
    reason = str(record.get("reason") or "").strip()
    if reason:
        return reason[:120]
    # 模型没给理由时，退回维度描述，别硬编一句。
    overall = int(record.get("overall") or 0)
    dims = record.get("dims") or {}
    if not dims:
        return f"{overall} 分"
    top = max(dims, key=lambda k: dims.get(k) or 0)
    names = {"relevance": "贴主题", "novelty": "有新意", "evidence": "证据扎实", "practicality": "能落地"}
    return f"{overall} 分，{names.get(top, '')}这块突出" if (dims.get(top) or 0) >= 8 else f"{overall} 分"
