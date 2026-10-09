"""文章点赞与评论（2026-09-26）。

知乎那套拆成两块，这里各做各的：

  点赞  对**文章**的一次表态。公开计数（"142 人觉得有用"），同时告诉
        来访者他自己点没点——否则第二个人看到数字不知道能不能点。
  评论  公开的对话。列表 + 自己的能删，别人都能读。

这站原本没有真正的评论：左下角浮层里的「这篇有用」写进 localStorage
（自己看得见，别人永远看不到），旁边那个是反馈面板（报障用，不是讨论）。
两个半成品合不成评论。现在统一放到文章底部的一整块：操作条（有用 +
评论数）在上，评论区（发布框 + 列表）在下，正常文档流，不是悬浮。

数据：两条 append-only 的 jsonl，和站点其它日志（feedback.jsonl）同一套路数。
  likes      {path, uid, at}
  comments   {id, path, author, text, at, uid}

隐私：uid 是浏览器自己生成的随机串，**落盘前哈希**，不存原始值、更不存 IP
或 UA——读者为一个知识库留个匿名赞，不该留下任何能反查到他的信息。
计数按 (path, uid_hash) 去重，一个人一次赞。

用法（前端）：
  GET  /api/likes?path=…   → {count, liked}
  POST /api/likes          → {count, liked}
  GET  /api/comments?path=…→ {items, total}
  POST /api/comments        → {item}
  POST /api/comments/remove → {removed}
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time
import uuid

DATA_HOME = pathlib.Path(__file__).resolve().parent.parent / "data"

COMMENTS_PATH = DATA_HOME / "comments.jsonl"
LIKES_PATH = DATA_HOME / "likes.jsonl"

# 单条评论的正文上限。比长微博短、比一条闲言长——写不下观点就分两条。
COMMENT_MAX = 1000
# 昵称上限。空着不填也算数，那时候显示「匿名访客」。
AUTHOR_MAX = 24
# 每篇文章最多回多少条。防的是把一篇笔记塞成论坛。
COMMENTS_PER_PAGE = 200
_COMMENTS_LOCK = threading.Lock()
_LIKES_LOCK = threading.Lock()


def _hash_uid(uid: str) -> str:
    """只留哈希。同一浏览器换 UA/IP 仍是同一个人（赞不重复），
    但hash 推不回原始串。"""
    return hashlib.sha1(str(uid or "").encode("utf-8")).hexdigest()[:16]


def _append(path: pathlib.Path, row: dict) -> None:
    """append 一行。jsonl 的好处是评论是一条一行，写坏了一行不影响别的，
    也不用整文件重写（评论区是热数据，整文件重写会和读者同时读到半个文件）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os_sync = getattr(handle, "flush", None)
        del os_sync  # 只 flush 不 fsync：写盘失败丢的是刚发的一条，比锁死读者更轻


def _read(path: pathlib.Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue  # 坏行跳过，不让它把整个评论区带崩
        if isinstance(row, dict):
            rows.append(row)
    return rows


# ---------------------------------------------------------------- 点赞


def likes_overview(path: str, uid: str) -> dict:
    """一篇的赞数 + 这位来访者点没点。"""
    with _LIKES_LOCK:
        rows = [r for r in _read(LIKES_PATH) if r.get("path") == path]
    me = _hash_uid(uid)
    return {"count": len(rows), "liked": any(r.get("uid") == me for r in rows)}


def toggle_like(path: str, uid: str) -> dict:
    """点/取消一篇的「有用」。再点是取消——知乎也是这个语义，
    一个表态不该只能往上加。"""
    me = _hash_uid(uid)
    with _LIKES_LOCK:
        rows = _read(LIKES_PATH)
        kept = [r for r in rows if not (r.get("path") == path and r.get("uid") == me)]
        had = len(kept) != len(rows)      # 原来点过赞
        if had:
            # 再点一次 = 收回。知乎的语义也是这样：表态能撤回。
            LIKES_PATH.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8"
            )
            count = len(kept)
        else:
            _append(LIKES_PATH, {"path": path, "uid": me, "at": time.time()})
            count = len(kept) + 1
    return {"count": count, "liked": not had}


def like_count(path: str) -> int:
    """只问总数（站点统计页要用，手上没有来访者 uid）。"""
    with _LIKES_LOCK:
        return len([r for r in _read(LIKES_PATH) if r.get("path") == path])


# ---------------------------------------------------------------- 评论


def comments_list(path: str, limit: int = COMMENTS_PER_PAGE) -> dict:
    """一篇的评论。最新在前——读者看评论区是想看"最近有人说什么"。"""
    with _COMMENTS_LOCK:
        rows = [r for r in _read(COMMENTS_PATH) if r.get("path") == path]
    rows.sort(key=lambda r: float(r.get("at") or 0), reverse=True)
    items = [
        {
            "id": str(r.get("id") or ""),
            "author": str(r.get("author") or "匿名访客"),
            "text": str(r.get("text") or ""),
            "at": float(r.get("at") or 0),
            "mine": False,
        }
        for r in rows[:limit]
    ]
    return {"items": items, "total": len(rows)}


def comment_add(path: str, text: str, uid: str, author: str = "") -> dict:
    """发一条评论。返回存好的那条（前端直接插进列表，不必再拉一次）。"""
    body = str(text or "").strip()
    if not body:
        raise ValueError("empty")
    if len(body) > COMMENT_MAX:
        body = body[:COMMENT_MAX]
    name = str(author or "").strip()[:AUTHOR_MAX] or "匿名访客"
    row = {
        "id": uuid.uuid4().hex[:12],
        "path": path,
        "author": name,
        "text": body,
        "uid": _hash_uid(uid),
        "at": time.time(),
    }
    with _COMMENTS_LOCK:
        _append(COMMENTS_PATH, row)
    return {
        "id": row["id"],
        "author": row["author"],
        "text": row["text"],
        "at": row["at"],
        "mine": True,
    }


def comment_remove(cid: str, uid: str) -> bool:
    """删自己那条。只认 uid——不能靠"谁的 id 小"这类规则去删别人的。"""
    me = _hash_uid(uid)
    with _COMMENTS_LOCK:
        rows = _read(COMMENTS_PATH)
        kept = [
            r
            for r in rows
            if not (str(r.get("id") or "") == cid and r.get("uid") == me)
        ]
        if len(kept) == len(rows):
            return False
        COMMENTS_PATH.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8"
        )
    return True


def comment_count(path: str) -> int:
    """一篇多少条评论（操作条上那个数）。"""
    with _COMMENTS_LOCK:
        return len([r for r in _read(COMMENTS_PATH) if r.get("path") == path])
