"""BestBlogs 的精选文章 —— 走它的 OpenAPI，不爬页面。

## 为什么用 API 而不是爬

先说结论：这个站**爬不动**。它的列表页是客户端渲染的，HTML 里只有壳；
文章详情页能拿到（JSON-LD 里有标题、摘要、封面、时间），但文章 ID 是
`9f8b29d390` 这种随机哈希，没有列表页就无从枚举 —— 首页只链一篇头条，
文章页也不给"相关推荐"的链接。想靠爬取攒出一个列表，只能写一堆猜不到的
ID，那不是工程是碰运气。

它自己提供了正式途径。文档在 bestblogs.dev/docs/api/endpoints：

    GET /openapi/v2/resources   精选内容列表（AI 初评 + 专家精审）
    GET /openapi/v2/sources     公共订阅源目录
    GET /openapi/v2/brief       某日的早报

参数正好是需要的那些：`type=article`、`language=zh`、
`time=24h|3d|1w`、**`qualified=true` 只返回 Featured 精选**、`score=80+`。
比爬 HTML 稳，也拿到了它真正值钱的那层 —— 人工精审过的排序。

## API Key

需要 `X-API-KEY`。登录 bestblogs.dev → 设置 → API Key 自助申请，免费。
本机放在：

    ~/.config/technical-knowledge/bestblogs.key      （一行，就是 key）

或环境变量 `BESTBLOGS_API_KEY`。两条都没有时这个模块**不报错**，
返回空列表 + 一个 `unconfigured` 状态，页面照常显示别的源。

抓取遵守它 robots.txt 的 `Allow: /`，且 `/openapi/` 不在 Disallow 列表里
（被禁的是 `/api/`，那是给浏览器会话用的另一套）。
"""

from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

# 端点在 api. 子域，**不是** www。
#
# 文档里的 curl 示例写的是 bestblogs.dev，而那个域名把 /openapi/* 301 到
# www，www 上返回 404 —— 三个域名里只有 api. 是真的服务端点。
# 这是实测出来的：同样一个 key，www 上 /me 也 404，api 上返回账号信息。
API_BASE = "https://api.bestblogs.dev/openapi/v2"
TIMEOUT = 12.0

USER_AGENT = (
    "technical-knowledge/1.0 (personal reading digest; "
    "+https://github.com/hub138/technical-knowledge)"
)

KEY_FILE = pathlib.Path(
    os.environ.get("BESTBLOGS_KEY_FILE")
    or pathlib.Path.home() / ".config" / "technical-knowledge" / "bestblogs.key"
)

# 缓存。API 有每日配额，不该每次开页面都打一次。
_CACHE: dict[str, object] = {"at": 0.0, "items": [], "status": "unknown"}
_CACHE_TTL = 1800  # 30 分钟；早报和精选本来就是按天的节奏


def api_key() -> str:
    """Key 从环境变量或本地文件读。都没有返回空串。

    Key 的格式是 `bb_` + 32 位十六进制（文档明确说的）。这里不强校验格式 ——
    将来它改格式不该让这个模块静默失效；只做一次 trim。
    """
    value = (os.environ.get("BESTBLOGS_API_KEY") or "").strip()
    if value:
        return value
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def configured() -> bool:
    return bool(api_key())


def _get(path: str, params: dict[str, str]) -> tuple[object, str]:
    """打一个端点。返回 (data, error)。**不抛异常。**"""
    key = api_key()
    if not key:
        return None, "unconfigured"
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{API_BASE}/{path}" + (f"?{query}" if query else "")
    request = urllib.request.Request(
        url,
        headers={
            "X-API-KEY": key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return None, "bad_key"
        return None, f"http_{error.code}"
    except (urllib.error.URLError, OSError):
        return None, "unreachable"

    # 端点不存在或 key 无效时它返回的是一个 HTML 页面（前端路由接住了请求），
    # 不是 JSON。直接 json.loads 会抛，把它误报成"网络不可达"会让排查方向跑偏。
    if "json" not in content_type.lower() and body.lstrip()[:1] == "<":
        # 404 时的 HTML 说明路由没匹配上 —— 实测用格式不合法的 key
        # （不是 bb_ 开头）就是 404，无法区分"key 无效"和"路径写错"。
        # 报 bad_key 是更可能的那一种，且指向的行动是对的（去拿一个真 key）。
        return None, "bad_key" if api_key() else "unconfigured"
    try:
        payload = json.loads(body)
    except ValueError:
        return None, "bad_payload"

    if not isinstance(payload, dict):
        return None, "bad_payload"
    if not payload.get("success"):
        message = str(payload.get("message") or "")
        if "额度" in message or "quota" in message.lower():
            return None, "quota"
        return None, "api_error"
    return payload.get("data"), ""


def _text(value: object, limit: int = 300) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _normalise(item: dict) -> dict:
    """把一条 API 结果整理成页面要的形状。

    字段名照真实响应，不照文档 —— 文档只列了几个，实际有四十多个，
    其中好几个正是页面需要的（公众号头像、金句、字数/时长）。

    正文不入库：这一页是入口，全文在原站。
    """
    rid = item.get("id") or ""
    # 优先用 BestBlogs 的站内页（排版统一、不跳微信），
    # 没有才退回原文 url —— 微信链接会过期，站内页不会。
    url = item.get("readUrl") or item.get("url") or ""
    quotes = [q for q in (item.get("keyQuotes") or []) if isinstance(q, str) and q.strip()]
    points = []
    for point in item.get("mainPoints") or []:
        if isinstance(point, dict) and point.get("point"):
            points.append({
                "point": _text(point.get("point"), 160),
                "explain": _text(point.get("explanation"), 240),
            })
    return {
        "id": rid,
        "title": _text(item.get("title") or item.get("originalTitle"), 200),
        # 一句话总结比长摘要更适合卡片；长摘要留给详情。
        "summary": _text(item.get("oneSentenceSummary") or item.get("summary"), 220),
        "long_summary": _text(item.get("summary"), 400),
        # 公众号名 + 头像。sourceImage 就是它 —— 不需要去微信后台拿。
        "source": _text(item.get("sourceName"), 40),
        "source_icon": str(item.get("sourceImage") or ""),
        "cover": str(item.get("cover") or item.get("enclosureUrl") or ""),
        "url": url,
        "published": str(item.get("publishDateStr") or ""),
        "published_full": str(item.get("publishDateTimeStr") or ""),
        "score": item.get("score") or "",
        "category": _text(item.get("categoryDesc") or item.get("mainDomainDesc"), 30),
        # 阅读量/字数/时长 —— arXivDaily 那种「10994 字（约 44 分钟）」的质感。
        "word_count": item.get("wordCount") or 0,
        "read_minutes": item.get("readTime") or 0,
        "read_count": item.get("readCount") or 0,
        "tags": [t for t in (item.get("tags") or []) if isinstance(t, str)][:6],
        "quotes": quotes[:3],
        "points": points[:4],
        "authors": [a for a in (item.get("authors") or []) if isinstance(a, str)][:4],
    }


def digest(limit: int = 12, hours: str = "3d", force: bool = False) -> dict:
    """精选文章列表。带缓存，失败时返回上一次的结果而不是空。"""
    now = time.time()
    if not force and _CACHE["items"] and now - float(_CACHE["at"]) < _CACHE_TTL:
        return {
            "status": _CACHE["status"],
            "items": _CACHE["items"],
            "fetched_at": int(_CACHE["at"]),
            "cached": True,
        }

    # 参数取值是实测出来的，文档写的不准：
    #   type      要大写 ARTICLE。小写 article 返回 0 条（totalCount=0），
    #             而不是报错 —— 静默失败，只能靠总数看出来。
    #   language  是 zh_CN / en_US，不是 zh / en。
    data, error = _get("resources", {
        "type": "ARTICLE",
        "language": "zh_CN",
        "time": hours,
        "qualified": "true",   # 只要 Featured，这是它人工精审的那一层
        "limit": str(min(50, max(1, limit))),
        "page": "1",
    })

    if error:
        # 已经有缓存就继续用它 —— 配额用完或网络抖动不该让首页空掉。
        if _CACHE["items"]:
            return {
                "status": _CACHE["status"],
                "items": _CACHE["items"],
                "fetched_at": int(_CACHE["at"]),
                "cached": True,
                "error": error,
            }
        return {"status": error, "items": [], "fetched_at": 0, "cached": False, "error": error}

    # 分页响应形如 {"currentPage","pageSize","totalCount","pageCount","dataList":[...]}。
    # 文档没写这个形状，是照真实响应试出来的 —— 之前猜 data / data.list
    # 都是 0 条，而接口其实返回了 14 万条。
    rows = data if isinstance(data, list) else (
        (data or {}).get("dataList") or (data or {}).get("list") or []
    )
    items = [_normalise(row) for row in rows if isinstance(row, dict)]
    items = [item for item in items if item["title"] and item["url"]]

    _CACHE.update({"at": now, "items": items, "status": "ok" if items else "empty"})
    return {"status": "ok" if items else "empty", "items": items, "fetched_at": int(now), "cached": False}


def sources(limit: int = 60) -> dict:
    """公共订阅源目录 —— 就是公众号列表。"""
    data, error = _get("sources", {"language": "zh_CN", "limit": str(limit), "page": "1"})
    if error:
        return {"status": error, "items": []}
    rows = data if isinstance(data, list) else (
        (data or {}).get("dataList") or (data or {}).get("list") or []
    )
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _text(row.get("name") or row.get("title"), 60)
        if not name:
            continue
        items.append({
            "name": name,
            "url": str(row.get("url") or row.get("homepage") or ""),
            "icon": str(row.get("icon") or row.get("logo") or row.get("avatar") or ""),
            "category": _text(row.get("categoryName") or row.get("category"), 30),
            "description": _text(row.get("description"), 120),
        })
    return {"status": "ok" if items else "empty", "items": items}
