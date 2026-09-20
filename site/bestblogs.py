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
# 单次请求超时。**这个值要够大。**
#
# 实测这台机器到这个域名的 TLS 握手经常要 15-25 秒才完成，偶尔直接超时。
# 原来写 12 秒，于是大部分请求在握手中途就被自己掐掉，表现为
# `unreachable:TimeoutError` —— 看起来像对方挂了，其实是本地等得不够久。
# 同样的 URL 用 curl 打（默认无超时）能通，这一点是判断依据。
TIMEOUT = 30.0

# 失败重试次数。TLS 抖动是间歇性的，实测连续重试 3 次里通常有 1-2 次能过。
# 抓取跑在后台，多等几秒没成本；抓不到则整块内容消失。
ATTEMPTS = 5

USER_AGENT = (
    "technical-knowledge/1.0 (personal reading digest; "
    "+https://github.com/hub138/technical-knowledge)"
)

KEY_FILE = pathlib.Path(
    os.environ.get("BESTBLOGS_KEY_FILE")
    or pathlib.Path.home() / ".config" / "technical-knowledge" / "bestblogs.key"
)

# 缓存。API 有每日配额，**一天只打一次**。
_CACHE: dict[str, object] = {"at": 0.0, "items": [], "status": "unknown", "ttl": 0.0}
# 每账号每天 500 次调用，翻 N 页就是 N 次。
# 2 小时刷新 = 12 次/天 × 4 页 = 48 次，看着安全，但再加上手动刷新和服务重启
# 就顶到上限了 —— 超了以后整个源静默变空（429 → quota），页面什么都不显示。
#
# 一天一次：4 页 × 1 次 = 4 次/天，怎么用都用不完。这批内容本来就是按天更新的
# 精选，一天取一次对它没有损失。
_CACHE_TTL = 86400

# 请求**失败**后的重试间隔，和成功时不同。
#
# 失败的两种原因要分开看：
#   · 那天确实没有内容 —— 结果稳定，锁一天没问题。
#   · 配额耗尽 / 网络不通 —— 这是暂时的，可能几小时后就恢复。
#
# 第一版两种都锁 24 小时。于是配额在中午恢复、页面却要空到第二天才重新抓 ——
# 缓存把"抓失败"当成了"确认没有"，而它俩完全不是一回事。
_RETRY_TTL = 3600

# 落盘。
#
# 原来只放内存 —— 服务一重启缓存就没了，重启一次就要重新抓一次。
# 而重启在这台机器上是常事（改完代码 kickstart）。落盘之后重启直接读文件，
# 一次请求都不发。
_CACHE_FILE = pathlib.Path(
    os.environ.get("BESTBLOGS_CACHE_FILE")
    or pathlib.Path(__file__).resolve().parent.parent / "data" / "bestblogs-cache.json"
)

# 早报缓存。同样落盘：早报一天一版，一天只该抓一次。
_BRIEF_TTL = 86400
_BRIEF_CACHE_FILE = pathlib.Path(
    pathlib.Path(__file__).resolve().parent.parent / "data" / "bestblogs-brief.json"
)
_brief_cache: dict[str, object] = {"at": 0.0, "payload": {}, "ttl": 0.0}


def _load_brief_cache() -> None:
    try:
        raw = json.loads(_BRIEF_CACHE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("payload"), dict):
            _brief_cache["at"] = float(raw.get("at") or 0.0)
            _brief_cache["payload"] = raw["payload"]
            _brief_cache["ttl"] = float(raw.get("ttl") or 0.0)
    except (OSError, ValueError):
        pass


def _save_brief_cache() -> None:
    try:
        _BRIEF_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BRIEF_CACHE_FILE.write_text(
            json.dumps(_brief_cache, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


_load_brief_cache()


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
    _CACHE["ttl"] = float(raw.get("ttl") or 0.0)


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
                    # ttl 必须落盘。它是"这次结果该锁多久"，重启后要能读出
                    # 来 —— 不存的话失败态重启后又变回默认的长 TTL（一天），
                    # 配额恢复后还是要等一天。
                    "ttl": _CACHE.get("ttl") or 0.0,
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
    for attempt in range(ATTEMPTS):
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
        # published 优先给"真实日期"，不要相对词。
        #
        # 早报接口的 publishDateStr 返回的是「今天」「昨天」这种相对描述 ——
        # 直接显示的话，卡片上的日期会写着"昨天"，而这一页是要归档给人看的，
        # 过几天再看就不成立了。有时间戳就从它推日期；没有才退回原字符串。
        "published": (
            datetime.datetime.fromtimestamp(
                (item.get("publishTimeStamp") or 0) / 1000
            ).strftime("%Y-%m-%d")
            if item.get("publishTimeStamp")
            else str(item.get("publishDateTimeStr") or item.get("publishDateStr") or "")[:10]
        ),
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
    # TTL 按上次结果取：失败用短的那档，成功后用长的那档。
    ttl = float(_CACHE.get("ttl") or _CACHE_TTL)
    if not force and _CACHE["at"] and now - float(_CACHE["at"]) < ttl:
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
    # 每页的请求错误要收集起来。
    #
    # 第一版 fetch_page 遇到错误直接 return []，外层于是永远看不到失败 ——
    # 配额耗尽被当成"抓到了 0 条"，返回 empty 而不是 quota。后果有两层：
    # 前端显示"没有内容"而不是"取数失败"，而缓存又会用短 TTL 之外的分支
    # 处理，重试节奏也就跟着错了。错误必须往上传，不能就地咽掉。
    page_errors: list[str] = []

    def fetch_page(page: int) -> list[dict]:
        # 参数取值必须以文档为准（bestblogs.dev/docs/api/endpoints）：
        #
        #   type      article / podcast / video / tweet / newsletter   ← 小写
        #   language  zh / en / all                                   ← 不是 zh_CN
        #   time      24h / 3d / 1w / 1m / all
        #   limit     默认 20，最大 100
        #
        # 第一版写的是 type=ARTICLE 和 language=zh_CN —— 两个都是无效值。
        # 服务端不报错，直接忽略，于是返回的是**默认排序**的内容：那批数据
        # 整体偏旧（多数 2024-2025），看起来就像"这个 API 捞不到新文章"。
        # 参数写错却看不出来，是因为无效值被静默忽略而不是报错。
        data, err = _get("resources", {
            "type": "article",
            "language": "zh",
            "time": hours if hours in ("24h", "3d", "1w", "1m") else "1m",
            "qualified": "true",
            "limit": "50",
            "page": str(page),
        })
        if err:
            page_errors.append(err)
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

    # 一条都没抓到、而且有请求失败 —— 这才是真失败（配额 / 网络）。
    # 抓到过内容时不算失败，个别页翻不到不影响整体。
    if not rows and page_errors:
        error = page_errors[0]

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
        _CACHE["ttl"] = _RETRY_TTL   # 配额/网络问题，一小时后可以再试
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

    _CACHE.update({"at": now, "items": items, "status": "ok" if items else "empty",
                   "ttl": _CACHE_TTL})
    # 落盘。下次服务启动直接读它，不用重新抓 —— 重启不该消耗配额。
    # 抓到空结果时也存：那是"今天确实没有新内容"这个事实，
    # 不存的话每次启动都会再去问一遍。
    _save_cache()
    return {"status": "ok" if items else "empty", "items": items, "fetched_at": int(now), "cached": False}


def brief(force: bool = False) -> dict:
    """今日早报 —— 站上「我的早报 / 今日精选」那块内容。

    两个端点，两次调用拿全部：

        GET  /openapi/v2/briefs/public/today        今天的候选（id + 评分 + 推荐理由）
        POST /openapi/v2/resources/batch-meta       按 id 批量取完整字段

    这才是这个源的正常用法，比翻 `resources` 精选流靠谱得多：
    两次调用 vs 翻四页，内容却是今天/昨天的。

    ## 路径是试出来的，文档写得不完整

    文档的 Endpoints 页把早报写成 `GET /openapi/v2/brief`，参数 `date`。
    照那个路径打过去是 404 —— 真实路径多了一层 `briefs/public/`，而且
    日期是路径的一部分（`/today`），不是查询参数：

        /openapi/v2/briefs/public/today       ✅ 200
        /openapi/v2/briefs/public?date=...    ❌ 404
        /openapi/v2/brief?date=...&language=zh ❌ 404
        /openapi/v2/brief/public/today        ❌ 404

    怎么找到真的：装了官方 CLI（`npm i -g @bestblogs/cli`），跑
    `bestblogs discover today --json`，它的错误信息里带着实际请求的 URL。
    以后这类"文档描述和真实路径对不上"的情况，用官方 CLI 反查比猜快得多。

    ## 为什么日期不用自己算

    早报端点只有 `/today` 一个入口，不像文档说的能按 date 取历史。
    周日没有早报这件事由服务端处理：它自己会给最近一版。
    """
    now = time.time()
    ttl = float(_brief_cache.get("ttl") or _BRIEF_TTL)
    if not force and _brief_cache.get("at") and \
            now - float(_brief_cache["at"]) < ttl and _brief_cache.get("payload"):
        return {**_brief_cache["payload"], "cached": True}

    if not api_key():
        return {"status": "unconfigured", "items": [], "date": ""}

    data, error = _get("briefs/public/today", {})
    if error:
        _remember_brief_failure(now, error)
        return {"status": error, "items": [], "date": "", "error": error}

    # 字段名是 `contentItems`，不是 `candidates`。
    #
    # `candidates` 是官方 CLI 的输出格式 —— 它把这份响应用自己的一套类型
    # 重新包了一层。我照着 CLI 的 --json 输出写解析，于是拿到的永远是空：
    # 请求成功、err 也是空，只是键名对不上，静默变成"今天没有内容"。
    #
    # 教训：CLI 的输出**不是**原始 API 的形状。要写解析就用 curl 打原始
    # 端点，别拿 CLI 的 --json 当契约。
    candidates = data if isinstance(data, list) else (
        (data or {}).get("contentItems") or (data or {}).get("candidates")
        or (data or {}).get("dataList") or []
    )
    ids = [str(c.get("resourceId") or c.get("id") or "")
           for c in candidates if isinstance(c, dict)]
    ids = [i for i in ids if i][:40]
    if not ids:
        _remember_brief_failure(now, "empty")
        return {"status": "empty", "items": [], "date": ""}

    # 批量取详情。候选里没有发布日期（没有 publishDateTimeStr 这类字段），
    # 而页面要按时间排、要显示日期 —— 必须补这一次。
    rows = _batch_meta(ids)
    if not rows:
        _remember_brief_failure(now, "empty")
        return {"status": "empty", "items": [], "date": ""}

    items = [_normalise(row) for row in rows if isinstance(row, dict)]
    items = [i for i in items if i.get("title") and i.get("url")]
    items.sort(key=lambda item: item.get("published_ts") or 0, reverse=True)

    payload = {
        "status": "ok",
        # 早报自己的日期字段（briefDate），比从条目里取第一篇更准。
        "date": (data or {}).get("briefDate") or (items[0].get("published", "") if items else ""),
        "items": items,
        "fetched_at": int(now),
        "cached": False,
    }
    _brief_cache.update({"at": now, "payload": payload, "ttl": _BRIEF_TTL})
    _save_brief_cache()
    return payload


def _batch_meta(ids: list[str]) -> list[dict]:
    """按 id 批量取完整元数据。

    POST 而不是 GET，body 是 `{"ids": [...]}`。一次最多几十个 id ——
    早报一次给 20 个，一个请求就够，省下的配额留给别的。
    """
    key = api_key()
    if not key:
        return []
    body = json.dumps({"ids": ids}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}/resources/batch-meta",
        data=body,
        headers={
            "X-API-KEY": key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(0.8 * attempt)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        data = payload.get("data")
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []
    return []


def _remember_brief_failure(now: float, status: str) -> None:
    """记下失败，但只锁一小时。

    这里和 digest 是同一个教训：把"这次没抓到"当成"确认没有"会把
    暂态问题锁成一整天的空白。配额和网络都是几小时就恢复的。
    """
    payload = {"status": status, "date": "", "items": [], "fetched_at": int(now), "cached": False}
    _brief_cache.update({"at": now, "payload": payload, "ttl": _RETRY_TTL})
    _save_brief_cache()


def sources(limit: int = 60) -> dict:
    """公共订阅源目录 —— 就是公众号列表。"""
    # 同上：language 的有效取值是 zh / en / all。
    data, error = _get("sources", {"language": "zh", "limit": str(limit), "page": "1"})
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
