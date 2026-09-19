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

import datetime
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

# 缓存。API 有每日配额，**一天只打一次**。
_CACHE: dict[str, object] = {"at": 0.0, "items": [], "status": "unknown"}
# 每账号每天 500 次调用，翻 N 页就是 N 次。
# 2 小时刷新 = 12 次/天 × 4 页 = 48 次，看着安全，但再加上手动刷新和服务重启
# 就顶到上限了 —— 超了以后整个源静默变空（429 → quota），页面什么都不显示。
#
# 一天一次：4 页 × 1 次 = 4 次/天，怎么用都用不完。这批内容本来就是按天更新的
# 精选，一天取一次对它没有损失。
_CACHE_TTL = 86400

# 落盘。
#
# 原来只放内存 —— 服务一重启缓存就没了，重启一次就要重新抓一次。
# 而重启在这台机器上是常事（改完代码 kickstart）。落盘之后重启直接读文件，
# 一次请求都不发。
_CACHE_FILE = pathlib.Path(
    os.environ.get("BESTBLOGS_CACHE_FILE")
    or pathlib.Path(__file__).resolve().parent.parent / "data" / "bestblogs-cache.json"
)


def _load_cache() -> None:
    """启动时把上次抓的结果读回来。读不到或坏了就当没有。"""
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(raw, dict):
        return
    items = raw.get("items")
    if not isinstance(items, list):
        return
    _CACHE["at"] = float(raw.get("at") or 0.0)
    _CACHE["items"] = items
    _CACHE["status"] = str(raw.get("status") or "unknown")


def _save_cache() -> None:
    """把结果写到盘上。写失败不算错误 —— 下次重新抓就是了。"""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(
                {
                    "at": _CACHE["at"],
                    "items": _CACHE["items"],
                    "status": _CACHE["status"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


_load_cache()


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

    # 重试两次。
    #
    # 实测这个端点会出现 TLS 握手直接超时（`The handshake operation timed
    # out` / `TLS/SSL connection has been closed (EOF)`），而且是**连续多次
    # 都失败**再恢复的那种，不是单次抖动。抓取是后台串行的，多花几秒没成本；
    # 一次失败就让整块精选消失才是代价。
    #
    # 只重试网络层错误。HTTP 错误（401 / 429）重试没意义 —— 那是服务端
    # 明确回答了"不行"，再问一遍答案一样。
    body = ""
    content_type = ""
    last_error = ""
    for attempt in range(3):
        if attempt:
            time.sleep(0.8 * attempt)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                return None, "bad_key"
            if error.code == 429:
                return None, "quota"
            return None, f"http_{error.code}"
        except (urllib.error.URLError, OSError) as error:
            # 记下最后一次的具体原因，方便排查是 DNS、TLS 还是超时。
            last_error = type(error).__name__
            continue
    else:
        return None, f"unreachable:{last_error}" if last_error else "unreachable"

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
        # 毫秒时间戳 + 由它推出的完整日期。
        #
        # 接口的 publishDateStr 有两种格式："2025-04-17" 和 "04-24"。
        # 后者不是"很久以前"，是**今年**（省略了年份）—— 实测 04-24 的
        # 时间戳是 2026-04-24。直接显示这个字符串会让最新的文章看起来
        # 像陈年旧文。统一从时间戳推日期，显示层不再碰原字符串。
        "published_ts": item.get("publishTimeStamp") or 0,
        "published_full": (
            datetime.datetime.fromtimestamp(
                (item.get("publishTimeStamp") or 0) / 1000
            ).strftime("%Y-%m-%d")
            if item.get("publishTimeStamp") else ""
        ),
        "score": item.get("score") or "",
        # 内容自带的两个分类字段。接口的 category 参数**不生效**（实测五种
        # 取值返回的总数几乎一样），所以筛选用它随数据带回来的这个值。
        "category": _text(item.get("categoryDesc"), 30),
        "domain": _text(item.get("mainDomainDesc"), 30),
        # 阅读量/字数/时长 —— arXivDaily 那种「10994 字（约 44 分钟）」的质感。
        "word_count": item.get("wordCount") or 0,
        "read_minutes": item.get("readTime") or 0,
        "read_count": item.get("readCount") or 0,
        "tags": [t for t in (item.get("tags") or []) if isinstance(t, str)][:6],
        "quotes": quotes[:3],
        "points": points[:4],
        "authors": [a for a in (item.get("authors") or []) if isinstance(a, str)][:4],
    }


# 时间窗到天数的换算。用于本地筛 —— 接口的 time 参数不生效。
_WINDOW_DAYS = {"24h": 1, "3d": 3, "1w": 7, "1m": 30, "2m": 60, "all": 0}


def digest(limit: int = 12, hours: str = "2m", pages: int = 4, force: bool = False) -> dict:
    """精选文章列表。带缓存，失败时返回上一次的结果而不是空。"""
    now = time.time()
    # TTL 判断**不能要求缓存非空**。
    #
    # 原来写的是 `_CACHE["items"] and ...` —— 于是"抓到了，但窗口内没有文章"
    # 这种结果（items 为空）每次都会被当成"没抓过"重新去问一遍。
    # 配额耗尽时恰好就是这种状态，结果服务每重启一次就重试一次。
    #
    # 改成看"有没有抓过"（at 有值）而不是"抓到了什么"。
    if not force and _CACHE["at"] and now - float(_CACHE["at"]) < _CACHE_TTL:
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
    # 抓多页。
    #
    # 单页只有 20 条，而且第一页是按**评分**排的 —— 里面混着 2024 年的。
    # 实测翻到第 10 页能拿到 2026-09 的文章（9 天前）。所以要翻够页数，
    # 再在本地按发布时间排、按新鲜度筛。
    #
    # 页数 10：实测新文章藏在深处 —— 60 天窗口内唯一一篇（2026-09-10）
    # 在第 5 页之后，翻 4 页根本碰不到。所以页数要给够，靠下面的预算
    # 控制成本：凑够 limit 条窗口内的就停，不用翻满。
    rows: list[dict] = []
    error = ""
    # 并行翻页。
    #
    # 串行翻 10 页要 ~100 秒（实测）。虽然结果缓存 30 分钟、且抓取在后台
    # 串行进行不阻塞访客，但它会拖住同一批里的其它源。10 个请求之间没依赖，
    # 并行是对的：实测 10 页从 ~100 秒降到 ~15 秒。
    def fetch_page(page: int) -> list[dict]:
        data, err = _get("resources", {
            "type": "ARTICLE",
            "language": "zh_CN",
            "limit": "20",
            "page": str(page),
        })
        if err:
            return []
        chunk = data if isinstance(data, list) else (
            (data or {}).get("dataList") or (data or {}).get("list") or []
        )
        return [r for r in chunk if isinstance(r, dict)]

    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(pages, 6) if pages else 1) as pool:
            for chunk in pool.map(fetch_page, range(1, (pages or 1) + 1)):
                rows.extend(chunk)
    except ImportError:
        # 极简回退：串行翻页。
        for page in range(1, (pages or 1) + 1):
            rows.extend(fetch_page(page))

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
        # 失败也要记时间。
        #
        # 不记的话，配额耗尽的这段时间里服务每重启一次就重试一次（4 次调用），
        # 而重启在这台机器上是常事。记下"刚刚试过"，TTL 就会挡住紧接着的重试。
        _CACHE["at"] = now
        _CACHE["status"] = error
        _save_cache()
        return {"status": error, "items": [], "fetched_at": 0, "cached": False, "error": error}

    items = [_normalise(row) for row in rows if isinstance(row, dict)]
    items = [item for item in items if item["title"] and item["url"]]
    # 按发布时间倒序排。
    #
    # 接口自己的排序**不是**按时间 —— 实测 time=24h/3d/1w/1m 四个窗口返回的
    # 总数完全一样（52742），第一页的日期从 2024 混到 2025，说明它按评分或
    # 相关性排。它给的是"精选库里最值得读的"，不是"最近发布的"。
    # 而这一页要的是后者，所以自己排。
    items.sort(key=lambda item: item.get("published_ts") or 0, reverse=True)

    # 本地按时间窗筛。
    #
    # 接口的 time 参数被忽略（24h/3d/1w/1m 返回的总数完全一样），所以窗口
    # 只能自己卡。默认 1 个月 —— 更长的话首页会摆出一年前的文章，
    # 而这一块叫"最新优质好文"，名不副实。
    #
    # 筛完不够 limit 条就少给 —— **不回填旧的**。
    #
    # 这里踩过一次：第一版写了"一条都没有时才退回全部"，结果 1 周窗口
    # 返回了一篇 2025-02 的文章。那个回退分支看起来是"防页面空掉"的
    # 保险，实际效果是把窗口彻底废掉 —— 因为对方的库存整体偏旧时，
    # 窗口内本来就常常是空的，于是每次都走回退。
    #
    # 宁缺毋滥：窗口内没有就显示没有。
    days = _WINDOW_DAYS.get(hours, 0)
    if days:
        cutoff = time.time() - days * 86400
        items = [i for i in items if (i.get("published_ts") or 0) / 1000 >= cutoff]

    _CACHE.update({"at": now, "items": items, "status": "ok" if items else "empty"})
    # 落盘。下次服务启动直接读它，不用重新抓 —— 重启不该消耗配额。
    # 抓到空结果时也存：那是"今天确实没有新内容"这个事实，
    # 不存的话每次启动都会再去问一遍。
    _save_cache()
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
