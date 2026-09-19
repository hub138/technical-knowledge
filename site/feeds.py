"""取回外部源的最新几条，供 /sources 页面就地显示。

## 为什么是这个形态

用户的原话：「不是抓进来 是直接给个入口 一个页面框 把他们的东西 直接显示进来
不就行吗 直接 curl那种？」所以要做的是**服务端取回 + 本站样式重排**，
不是 iframe 嵌原站（实测 bestblogs 的 CSP 是 `frame-ancestors 'none'`、
ruanyifeng 是 `X-Frame-Options: SAMEORIGIN`，用户最看重的两个站恰好禁止嵌入），
也不是整页镜像。

三条硬边界，后面每个决策都从这儿推：
  1. 只显示标题 + 摘要 + 时间，**不显示正文**。搬运正文就从「入口」滑向「镜像」了，
     而用户明确说了「不是抓进来」。摘要只用源自己给的 description/summary。
  2. 永远不白屏。外部站挂了，卡片照常渲染，只是那一条窗口说读不到。
  3. 不能拖垮本站。server 是 ThreadingHTTPServer，现抓会让慢源占住请求线程。

## 所以是「缓存 + 过期重抓 + 后台预热」

`/api/feeds` 只读内存/磁盘快照，**零网络请求**，毫秒级返回。过期时不阻塞本次请求，
起一个后台线程去刷。这不只是性能选择 —— 如果请求时现抓，那就是**每个访客触发一轮对外抓取**，
等于把本站变成打向外部站的反射放大器；PaperNotes 的 `Crawl-delay: 1` 还会让 6 源串行
最坏跑到 8-10 秒，把请求线程占满。

## 抓取礼貌

各站 robots.txt 实测（2026-09-18）：
  readhub.cn      Content-Signal: ai-train=no, search=yes, ai-input=no；/rss 允许
  papernotes.org  Allow: / 且 **Crawl-delay: 1** —— 必须限速
  arxivdaily.com  Disallow: /*? 但 Allow: /topics$ /topics/ 等
  zeli.app        Allow: /，Disallow /api/ /debug/
  ruanyifeng.com  robots.txt 为空

注意 `ai-input=no`/`ai-train=no` 是针对训练和 AI 输入的。我们做的是「给人看」，
落在 `search=yes` 一侧。**将来若想把抓来的内容喂给模型，就触碰了这条 —— 不要那么做。**
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

# 反馈与访问日志也落在这里；内容性质相同 —— 运行时数据，不该进版本库。
DATA_HOME = Path(os.environ.get("KNOWLEDGE_DATA_HOME") or REPOSITORY_ROOT / "data")
CACHE_FILE = DATA_HOME / "feeds-cache.json"

# 带可识别的身份和联系方式是礼貌抓取的标准做法，照 scripts/fetch-paper-text.py 的写法。
USER_AGENT = (
    "technical-knowledge/1.0 (source preview; "
    "+https://github.com/hub138/technical-knowledge)"
)
TIMEOUT = 8.0
# 单源下载上限。2MB 对绝大多数页面都够，但 PaperNotes 的 sitemap 实测 5.7MB ——
# 所以按源可覆盖（见 FEEDS 里的 max_bytes）。上限的意义是防止误抓到大文件，
# 不是省流量，所以给足余量比卡得刚好更合适。
MAX_BYTES = 2 * 1024 * 1024

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


# ── 源定义 ────────────────────────────────────────────────────────────────────
#
# 声明式。加源只改这里，解析器按 kind 分发。
#
# ttl 按内容性质定，不是拍脑袋：ReadHub/zeli 是当天热点，15 分钟；
# 阮一峰是周刊，1 小时；论文站的增补是批量导入，30-60 分钟。
FEEDS: list[dict] = [
    {
        "key": "readhub",
        "group": "news",
        "kind": "rss",
        "url": "https://readhub.cn/rss",
        "link": "https://readhub.cn/hot",
        "ttl": 900,
        "limit": 12,
        "delay": 0.0,
    },
    {
        "key": "ruanyifeng",
        "group": "reading",
        "kind": "atom",
        "url": "https://www.ruanyifeng.com/blog/atom.xml",
        "link": "https://www.ruanyifeng.com/blog/index.html",
        "ttl": 3600,
        "limit": 5,
        "delay": 0.0,
    },
    {
        "key": "papernotes",
        "group": "papers",
        "kind": "html",
        # 首页没有论文列表，取 sitemap（robots: Allow: / 且 Crawl-delay: 1）。
        "url": "https://papernotes.org/sitemap.xml",
        "link": "https://papernotes.org/",
        "ttl": 3600,
        "limit": 12,
        # sitemap 实测 5.7MB，默认 2MB 上限会把它挡掉（第一版就报 too_large）。
        "max_bytes": 12 * 1024 * 1024,
        # 而且实测下载要 15.4s，默认 8s 超时会报 unreachable（第二版踩到）。
        # 它的 ttl 是一小时，抓得慢一点无所谓 —— 反正在后台线程里。
        "timeout": 45.0,
        # robots.txt 明确写了 Crawl-delay: 1。只在后台线程里 sleep，不影响访客。
        # 这个源还要逐页补标题，所以每条之间也会 sleep 同样的间隔。
        "delay": 1.0,
    },
    {
        "key": "arxivdaily",
        "group": "papers",
        "kind": "html",
        # robots: Allow: /$ —— 用首页，论文列表在那儿。
        # 实测 /topics 只是子领域目录（列的是分类说明不是论文），所以不抓它。
        "url": "https://www.arxivdaily.com/",
        "link": "https://www.arxivdaily.com/",
        "ttl": 1800,
        "limit": 12,
        "max_bytes": 4 * 1024 * 1024,
        "delay": 0.0,
    },
    {
        "key": "zeli",
        "group": "news",
        "kind": "html",
        "url": "https://zeli.app/zh",
        "link": "https://zeli.app/zh",
        "ttl": 900,
        "limit": 12,
        "delay": 0.0,
    },
    {
        # BestBlogs 保留条目但 kind=none。删掉的话前端就不知道有这么个源需要解释，
        # 而用户要的正是「说清为什么做不到」。
        #
        # 实测为什么抓不到：156KB 的 HTML 只有 55 个字符可见文本，
        # `_next/static` 出现 259 次但没有 `__NEXT_DATA__` —— 纯客户端渲染；
        # 而且这个页面叫「我的关注」，本身要登录。不做 headless 抓取：
        # 那是滥用，抓回来也还是登录墙。
        # 走它的 OpenAPI（见 _fetch_bestblogs），不抓页面。
        #
        # 页面确实抓不到 —— 156KB 的 HTML 只有 55 个字符可见文本，
        # 而且是「我的关注」，本身要登录。但 API 给的东西比页面更全：
        # 人工精审过的精选、公众号头像、字数、阅读时长、评分。
        # key 放在 ~/.config/technical-knowledge/bestblogs.key，不入库。
        "key": "bestblogs",
        "group": "reading",
        "kind": "api",
        "url": "https://api.bestblogs.dev/openapi/v2/resources",
        # 链接指向早报页 —— 那才是"今天该读什么"。
        #
        # 说明一处 API 的限制：`/openapi/v2/resources` 返回的是一个**旧快照**
        # （实测最新一篇是 2025-12，而当天是 2026-09），而且排序、时间窗、
        # category 这些参数**全部被忽略** —— 试过 sortBy / orderBy / order /
        # recent / days / from / time=24h|3d|1w|1m，返回的总数完全一样。
        # brief 端点存在但 `metaData` 恒为 null。网页版早报要登录才看得到内容。
        #
        # 所以这里的定位是"BestBlogs 的人工精审精选（带年份标注）"，
        # 不是"今天的早报"。要今天的内容点 link 去原站登录看。
        "link": "https://www.bestblogs.dev/reading/brief",
        "ttl": 1800,
        "limit": 12,
        "delay": 0.0,
    },
]

BY_KEY = {source["key"]: source for source in FEEDS}


# ── 清洗：外部 HTML 绝不进 innerHTML ──────────────────────────────────────────
#
# 这是整个模块的安全核心。做法是让**响应里根本不存在 HTML 字段** ——
# 从源头消灭 XSS 面，而不是靠前端「记得转义」。前端还会再 esc 一次，那是纵深防御。


class _TextOnly(HTMLParser):
    """只收可见文本。

    关键是 script/style **连内容一起丢**。单纯用正则 `<[^>]+>` 剥标签的话，
    `<script>alert(1)</script>` 会留下 `alert(1)` 这段文本 —— 虽然已经不是可执行代码，
    但脏数据会混进摘要，看起来像正文的一部分。

    也不用 `re.sub(r"<[^>]*>", "", ...)`：属性里出现 `>` 就能骗过它。
    HTMLParser 是有状态的，遇到畸形标签不会误判。
    """

    SKIP = {"script", "style", "noscript", "template"}
    BLOCK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self) -> None:
        # convert_charrefs=True 让 &amp; 变成 &，拿到的才是真文本。
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag in self.BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def clean_text(raw_html: str, limit: int = 300) -> str:
    """把一段 HTML 变成纯文本。畸形输入返回空串，不抛。"""
    if not raw_html:
        return ""
    parser = _TextOnly()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception:  # 畸形 HTML 不该让整个源失败
        return ""
    text = parser.text()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def absolute_url(href: str, base: str) -> str:
    """把相对链接按源的地址补成绝对链接，并挡掉非 http(s) 协议。

    不补的话，他们页面里的 `/foo` 会变成打向**本站**的请求 ——
    点了跳到本站 404，看起来像本站坏了。

    协议白名单是必需的而不是可选：`urljoin` 不拦 `javascript:`（它不是相对地址，
    会原样返回），原样进 `href` 就是在本站执行脚本。
    """
    href = (href or "").strip()
    if not href:
        return ""
    try:
        absolute = urljoin(base, href)
    except ValueError:
        return ""
    if urlsplit(absolute).scheme.lower() not in {"http", "https"}:
        return ""
    return absolute


def decode_body(raw: bytes, content_type: str) -> str:
    """按声明的 charset → utf-8 → gb18030 → utf-8/replace 依次尝试。

    顺序有讲究：utf-8 排在 gb18030 前面，因为它对无效字节会抛错，正好当探测器用。
    gb18030 几乎能解码任何字节序列（不会抛），所以只能垫底 ——
    放前面会把合法的 UTF-8 中文解成乱码而且不报错。
    """
    declared = ""
    match = re.search(r"charset=[\"']?([\w-]+)", content_type or "", re.I)
    if match:
        declared = match.group(1)
    for encoding in (declared, "utf-8", "gb18030"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


# ── 解析 ──────────────────────────────────────────────────────────────────────


def _parse_date(value: str) -> str:
    """把 RFC 2822 或 ISO 8601 的日期统一成 ISO 字符串。解析不了就返回空。

    解析失败**不能丢条目** —— 时间只是显示用的，为了它丢掉内容不划算。
    """
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return ""


def _first_text(node, paths: list[str]) -> str:
    for path in paths:
        found = node.find(path, ATOM_NS)
        if found is not None and (found.text or "").strip():
            return (found.text or "").strip()
    return ""


def parse_xml_feed(text: str, base: str) -> tuple[list[dict], str]:
    """RSS 2.0 和 Atom 共用一个入口，靠根标签区分。"""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [], "parse_error"

    tag = root.tag.split("}")[-1].lower()
    if tag == "rss":
        nodes = root.findall("./channel/item")
    elif tag == "feed":
        nodes = root.findall("a:entry", ATOM_NS)
    else:
        return [], "unsupported_feed"

    items: list[dict] = []
    for node in nodes:
        if tag == "rss":
            title = _first_text(node, ["title"])
            link = _first_text(node, ["link"])
            summary_raw = _first_text(node, ["description"])
            published = _parse_date(_first_text(node, ["pubDate", "date"]))
        else:
            title = _first_text(node, ["a:title"])
            link = ""
            for candidate in node.findall("a:link", ATOM_NS):
                if candidate.get("rel") in (None, "alternate"):
                    link = candidate.get("href", "")
                    break
            summary_raw = _first_text(node, ["a:summary", "a:content"])
            # 优先 `published` 而不是 `updated`。实测阮一峰的 Atom 里
            # `updated` 是「这份 feed 什么时候重新生成的」—— 它的 413 期和 411 期
            # 都是今天被 touch 的，于是按 updated 排会出现 413、411、412 这种乱序。
            # `published` 才是文章自己的日期（411 是 09-03、412 是 09-11、413 是 09-18）。
            published = _parse_date(_first_text(node, ["a:published", "a:updated"]))

        title = clean_text(title, 200)
        url = absolute_url(link, base)
        if not title or not url:
            continue
        items.append({
            "title": title,
            "url": url,
            "summary": clean_text(summary_raw, 300),
            "published": published,
        })
    return items, ""


class _LinkCollector(HTMLParser):
    """收集 <a> 的 href 和可见文本。

    HTML 源用这个而不是正则：正则要同时处理属性顺序、单双引号、嵌套标签，
    很快就变成一个没人敢改的东西。HTMLParser 把这些都处理掉了。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._depth = 0
        self._buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _TextOnly.SKIP:
            self._skip += 1
            return
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._depth = 1
            self._buf = []
        elif self._href is not None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _TextOnly.SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._href is None:
            return
        self._depth -= 1
        if self._depth <= 0:
            text = " ".join("".join(self._buf).split())
            if self._href and text:
                self.links.append((self._href, text))
            self._href = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._href is not None and not self._skip:
            self._buf.append(data)


def _collect_links(html_text: str) -> list[tuple[str, str]]:
    collector = _LinkCollector()
    try:
        collector.feed(html_text)
        collector.close()
    except Exception:
        return []
    return collector.links


# 论文详情页的形状：/ICLR2026/llm_reasoning/some-paper-title/
_PAPER_PATH = re.compile(r"^/[A-Za-z]+\d{4}/[a-z_]+/[a-z0-9_-]+/?$")


def parse_papernotes(text: str, base: str) -> tuple[list[dict], str]:
    """PaperNotes 的 sitemap → 它最近收录的论文 URL 列表。

    首页只有会议和子领域的目录，**没有论文列表也没有时间戳**，所以不能从首页取。
    改用 sitemap 的 `lastmod`。

    这里有个必须说清的语义：`lastmod` 是**它导入这批论文的日期**，不是论文发表的时间。
    它一次批量导入几千篇（实测有一天 6574 条同一天），所以这个列表的含义是
    「PaperNotes 最近新增了什么」，不是「最近发表了什么」。页面措辞按前者写。

    本函数只取 URL 和时间。**标题和摘要要靠 fetch_one 里额外抓的详情页补上** ——
    sitemap 里没有标题，凭空造一个（比如从 URL 反推）会得到人看不懂的 slug。
    """
    if not base.endswith(".xml"):
        return [], "selector_missing"
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [], "parse_error"

    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    found: list[tuple[str, str]] = []
    for url_node in root.findall(f"{ns}url"):
        loc = url_node.findtext(f"{ns}loc", "") or ""
        lastmod = url_node.findtext(f"{ns}lastmod", "") or ""
        if loc and lastmod and _PAPER_PATH.match(urlsplit(loc).path):
            found.append((lastmod, loc))
    if not found:
        return [], "selector_missing"
    found.sort(reverse=True)
    return [
        {"title": "", "url": url, "summary": "", "published": _parse_date(day)}
        for day, url in found
    ], ""


# 论文详情页里的标题和「一句话总结」。用 og:title 而不是 h1 ——
# 实测这个站（MkDocs）的正文标题是 h2，页面级标题只在 og:title/title 标签里。
_OG_TITLE = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)', re.I)
_SUMMARY = re.compile(r"一句话总结[\s\S]{0,800}?<p>([\s\S]{0,600}?)</p>", re.I)


def enrich_papernotes(items: list[dict], delay: float, timeout: float = TIMEOUT) -> list[dict]:
    """给 PaperNotes 的条目补标题和摘要，逐页抓。

    **只抓 limit 条**，不是两万条。逐页扫全站是滥用，也违背「只做入口」的定位。
    """
    enriched: list[dict] = []
    for index, item in enumerate(items):
        if index:
            time.sleep(delay)
        request = urllib.request.Request(
            item["url"], headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                page = decode_body(response.read(MAX_BYTES), response.headers.get("Content-Type", ""))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            continue
        title_match = _OG_TITLE.search(page)
        title = html.unescape(title_match.group(1)).strip() if title_match else ""
        # og:title 带「[论文解读] 」前缀，是站点自己的标记，不是标题的一部分。
        title = re.sub(r"^\[[^\]]{0,12}\]\s*", "", title).strip()
        if not title:
            continue
        summary_match = _SUMMARY.search(page)
        summary = clean_text(summary_match.group(1)) if summary_match else ""

        # PaperNotes 的「一句话总结」和 arXivDaily 的「AI总结」是同一类东西：
        # 都是模型读完论文写的一句话。所以打同一个标签，前端就用同一个
        # 蓝底框渲染 —— 两处的读者看到的是同一种可信度标记。
        #
        # 它的原话（实测 JarvisEvo 那篇）：
        #   "JarvisEvo 把"会修图的设计师"做成一个单模型 Agent：它一边调用
        #    Lightroom 工具迭代修图、一边对中间结果做视觉自评…在 ArtEdit-Bench
        #    上像素保真度比 Nano-Banana 高 44.96%。"
        tags = ["AI总结"] if summary else []

        # 论文编号从 URL 反推不了（PaperNotes 的 slug 是标题），所以从页面里找
        # arXiv 链接。有就显示，没有就不显示 —— 不编。
        arxiv_id = ""
        arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", page)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)

        enriched.append({
            **item,
            "title": clean_text(title, 200),
            "summary": summary,
            "tags": tags,
            "arxiv_id": arxiv_id,
        })
    return enriched


# arXivDaily 首页上一条论文的形状。实测（2026-09-18）长这样：
#   <h2>Coding Agents with an Obstacle-Aware Harness…</h2>
#   <p class="title-cn">面向安全机器人操作、具有障碍物感知约束框架的编码智能体</p>
#   <p class="summary"><span class="summary-label">AI总结</span>本研究提出…</p>
#   <a class="icon-button url-button" href="https://arxiv.org/abs/2609.20822">URL</a>
#
# 抓 `/` 而不是 `/topics`：robots 两条都放行（`Allow: /$` 和 `Allow: /topics$`），
# 但实测 `/topics` 只是子领域目录，列的是「3D 视觉 / 三维重建、NeRF…」这种分类说明，
# 不是论文。第一版抓 /topics 拿到一条「3D 视觉 三维重建、NeRF、Gaussian Splatting…」，
# 看着像标题其实是分类描述 —— 这正是 sanity check 要抓的东西。
# arXivDaily 的条目块。一条论文一个 <article class="paper-card">。
#
# 这一版把整块一起抓，因为块内含好几个字段，分开抓会在条目边界上串味：
#
#   data-paper-updated  论文日期（不是抓取日期）
#   paper-meta 里的 span  编号 2609.20822 + 日期 + 分类芯片 + 「新提交」标
#   h2                  英文原标题
#   title-cn            中文译名
#   authors             作者
#   affiliations        机构（带中文译名，标注是 AI 分析生成的、可能有误）
#   summary             摘要
#
# `[\s\S]{0,n}?` 的非贪婪配上明确的分隔标签，条目之间不会互相吃。
_AD_BLOCK = re.compile(
    r'<article[^>]+class=["\'][^"\']*paper-card[^"\']*["\']'
    r'(?P<attrs>[^>]*)>'
    r'(?P<body>[\s\S]{0,6000}?)'
    r'</article>',
    re.I,
)
_AD_ID = re.compile(r'<span>\s*(\d{4}\.\d{4,5})\s*</span>')
_AD_DATE = re.compile(r'data-paper-updated=["\'](\d{4}-\d{2}-\d{2})["\']')
_AD_TITLE_EN = re.compile(r'<h2[^>]*>([\s\S]{0,300}?)</h2>', re.I)
_AD_TITLE_CN = re.compile(r'<p[^>]+class=["\'][^"\']*title-cn[^"\']*["\'][^>]*>([\s\S]{0,300}?)</p>', re.I)
_AD_AUTHORS = re.compile(r'<p[^>]+class=["\'][^"\']*authors[^"\']*["\'][^>]*>([\s\S]{0,400}?)</p>', re.I)
_AD_SUMMARY = re.compile(r'<p[^>]+class=["\'][^"\']*summary[^"\']*["\'][^>]*>([\s\S]{0,1200}?)</p>', re.I)
_AD_ARXIV = re.compile(r'href=["\'](https://arxiv\.org/abs/[^"\']+)["\']', re.I)
# 分类芯片：cs.AI / cs.CL 这种。标题属性里是英文全称，标签内容是短码。
_AD_CATEGORY = re.compile(
    r'<span[^>]+class=["\'][^"\']*category-pill[^"\']*["\'][^>]*>\s*([A-Za-z0-9.\-]{2,12})\s*</span>',
    re.I,
)
# 「新提交」/「版本更新」这类标记。
_AD_SUBMISSION = re.compile(
    r'<span[^>]+class=["\'][^"\']*submission-pill[^"\']*["\'][^>]*>\s*([^<]{2,12})\s*</span>',
    re.I,
)
# 机构名（含中文译名）。
_AD_AFFILIATION = re.compile(
    r'<span[^>]+class=["\'][^"\']*affiliation-item[^"\']*["\'][^>]*>\s*([^<]{2,60}?)\s*</span>',
    re.I,
)


def parse_arxivdaily(text: str, base: str) -> tuple[list[dict], str]:
    """arXivDaily 首页的论文列表。

    每条论文一个 <article class="paper-card">，块内有编号、日期、分类芯片、
    英文标题、中文译名、作者、机构、摘要 —— 这些都取，因为页面上有。
    以前只取标题和摘要，是因为按 `<h2>` 逐个抓，块边界都没碰到。

    日期取 `data-paper-updated`，那是**论文的日期**，不是抓取时间。

    「AI总结」是页面上的小标题（说明这段摘要是模型写的），提成 tag，
    不混进正文 —— 否则每条都读成 "AI总结 本文研究…"。
    """
    items: list[dict] = []
    seen: set[str] = set()
    for match in _AD_BLOCK.finditer(text):
        attrs = match.group("attrs") or ""
        body = match.group("body") or ""

        title_match = _AD_TITLE_EN.search(body)
        if not title_match:
            continue
        title_en = clean_text(title_match.group(1), 200)
        if not title_en:
            continue

        link = _AD_ARXIV.search(body)
        url = link.group(1) if link else ""
        if not url or url in seen:
            continue
        seen.add(url)

        cn_match = _AD_TITLE_CN.search(body)
        title_cn = clean_text(cn_match.group(1), 200) if cn_match else ""

        date_match = _AD_DATE.search(attrs) or _AD_DATE.search(body)
        published = date_match.group(1) if date_match else ""

        summary_match = _AD_SUMMARY.search(body)
        summary = clean_text(summary_match.group(1), 320) if summary_match else ""
        tags: list[str] = []
        if summary.startswith("AI总结"):
            tags.append("AI总结")
            summary = summary[len("AI总结"):].lstrip(" ：:")

        # 分类芯片和「新提交」标。它们是页面上最显眼的元数据，
        # 拿过来当标签比我自己编一个"论文"强。
        for code in _AD_CATEGORY.findall(body):
            if code not in tags:
                tags.append(code)
        for note in _AD_SUBMISSION.findall(body):
            note = clean_text(note, 12)
            if note and note not in tags:
                tags.append(note)

        author_match = _AD_AUTHORS.search(body)
        authors = clean_text(author_match.group(1), 200) if author_match else ""
        affiliations = [clean_text(a, 60) for a in _AD_AFFILIATION.findall(body)][:4]

        arxiv_id = ""
        id_match = _AD_ID.search(body)
        if id_match:
            arxiv_id = id_match.group(1)

        items.append({
            # 中英并列，和 arXivDaily 一致：英文是论文原名（读者在 arXiv
            # 和别的文章里看到的就是这一行），中文是译名。
            "title": title_en,
            "title_cn": title_cn,
            "url": url,
            "summary": summary,
            "published": published,
            "tags": tags[:6],
            "authors": authors,
            "affiliations": affiliations,
            "arxiv_id": arxiv_id,
        })
        if len(items) >= 40:
            break
    if not items:
        return [], "selector_missing"
    return items, ""



def parse_zeli(text: str, base: str) -> tuple[list[dict], str]:
    """zeli 首页的故事列表。

    数据不在 HTML 元素里，而在 Next.js 的 RSC payload 里 —— 一条条的
    `self.__next_f.push([1,"..."])`。直接抓 DOM 只能拿到标题和链接，
    而 payload 里有钱日期、作者、热度和**摘要**。

    解析有三个坑，都踩过：

      1. **payload 被拆在多个 <script> 标签里。** 单看一个标签的 json
         只到一半，怎么补都是错的（表现为"Expecting ',' delimiter"）。
         必须先把所有 push 的参数拼起来再解析。

      2. **两层转义混在一起。** 结构键是 `\"`（一层），字符串内部真正的
         引号是 `\\"`（两层）。要先保护两层、再收一层，否则摘要里带引号
         的那几条会把 JSON 撕开。

      3. **不能用括号配平找数组结尾。** 摘要里可能出现 `]` 或 `"])`，
         配平会被带偏。合并成完整 payload 之后就没这个问题了 ——
         配平只在完整文本上才可靠。
    """
    import datetime as _dt

    parts: list[str] = []
    for chunk in re.finditer(r'self\.__next_f\.push\(\[\d+,\s*("(?:[^"\\]|\\.)*")\s*\]\)', text):
        try:
            parts.append(json.loads(chunk.group(1)))
        except (ValueError, TypeError):
            continue
    payload = "".join(parts)
    marker = payload.find('"initialPosts"')
    if marker < 0:
        return [], "selector_missing"

    start = payload.index("[", marker)
    depth = 0
    in_string = False
    escaped = False
    end = None
    for i in range(start, len(payload)):
        ch = payload[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return [], "selector_missing"

    try:
        posts = json.loads(payload[start:end + 1])
    except (ValueError, TypeError):
        return [], "selector_missing"

    items: list[dict] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        title = clean_text(post.get("title"), 200)
        url = str(post.get("url") or "")
        if not title or not url.startswith("http"):
            continue
        stamp = post.get("time")
        published = ""
        if isinstance(stamp, (int, float)) and stamp > 0:
            published = _dt.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
        score = post.get("score")
        items.append({
            "title": title,
            "url": url,
            # zeli 自己写的摘要，比标题多得多 —— 原来这一格是空的。
            "summary": clean_text(post.get("abstract"), 300),
            "published": published,
            # 热度和作者做标签。Hacker News 的分数是有意义的信号：
            # 170 分和 3 分不是同一件事。
            "tags": ([f"▲ {score}"] if isinstance(score, int) and score > 0 else [])
                    + ([str(post.get("by"))] if post.get("by") else []),
        })
        if len(items) >= 40:
            break
    return items, ""



def parse_html_source(key: str, text: str, base: str) -> tuple[list[dict], str]:
    if key == "papernotes":
        return parse_papernotes(text, base)
    if key == "arxivdaily":
        return parse_arxivdaily(text, base)
    if key == "zeli":
        return parse_zeli(text, base)
    return [], "unsupported_source"


def parse_feed(kind: str, key: str, text: str, base: str) -> tuple[list[dict], str]:
    """返回 (items, error)。items 为空且 error 为空 = 确实没有内容。"""
    if kind in {"rss", "atom"}:
        return parse_xml_feed(text, base)
    if kind == "html":
        return parse_html_source(key, text, base)
    return [], "unsupported_kind"


# ── 抓取 ──────────────────────────────────────────────────────────────────────


def _fetch_bestblogs(source: dict) -> tuple[list[dict], str]:
    """BestBlogs 走它自己的 OpenAPI，不走 HTTP 抓页面。

    这个源原来标成 kind:"none"（不抓），理由是页面纯客户端渲染 + 要登录。
    那个判断在当时是对的 —— 但它的 OpenAPI 能拿到同样的内容，而且更好：
    带公众号名和头像、字数、阅读时长、评分，都是人工精审过的。

    延迟 import 是为了避免循环依赖：bestblogs 不依赖 feeds，
    而 feeds 只在真正要抓这一源时才需要它。
    """
    try:
        import bestblogs
    except ImportError:
        return [], "module_missing"
    result = bestblogs.digest(limit=int(source.get("limit") or 12))
    status = result.get("status") or ""
    if status == "unconfigured":
        return [], "no_key"
    if status != "ok":
        return [], result.get("error") or status or "unreachable"
    items = []
    for row in result.get("items") or []:
        items.append({
            "title": row.get("title", ""),
            "url": row.get("url", ""),
            "summary": row.get("summary", ""),
            "published": row.get("published_full") or row.get("published", ""),
            # 下面几个只有 BestBlogs 有。feedEntry 认到就用，不认就忽略 ——
            # 别的源照旧渲染成纯文字列表。
            "source": row.get("source", ""),
            "source_icon": row.get("source_icon", ""),
            "cover": row.get("cover", ""),
            "word_count": row.get("word_count") or 0,
            "read_minutes": row.get("read_minutes") or 0,
            "tags": row.get("tags") or [],
            # 内容自带的分类（人工智能 / 商业科技 / 软件编程）。
            # 前端拿它做本地筛选 —— 接口的 category 参数不生效。
            "category": row.get("category") or "",
        })
    return items, ""


def fetch_one(source: dict) -> tuple[list[dict], str]:
    """抓一个源。**绝不抛异常** —— 一个源失败不能影响其余。"""
    if source.get("key") == "bestblogs":
        return _fetch_bestblogs(source)
    if source.get("kind") == "none":
        return [], ""
    if source.get("delay"):
        # 只在后台刷新线程里 sleep。刷新是串行的，所以这里睡不会拖住任何访客。
        time.sleep(float(source["delay"]))

    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/xml, "
                "text/html;q=0.9, */*;q=0.8"
            ),
        },
    )
    try:
        timeout = float(source.get("timeout", TIMEOUT))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            cap = int(source.get("max_bytes", MAX_BYTES))
            raw = response.read(cap + 1)
            if len(raw) > cap:
                return [], "too_large"
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return [], f"http_{error.code}"
    except (urllib.error.URLError, OSError, ValueError):
        return [], "unreachable"

    text = decode_body(raw, content_type)
    items, error = parse_feed(source["kind"], source["key"], text, source["url"])
    if error:
        return [], error
    if not items and source["kind"] == "html":
        # 抓到 200 但一条都没解出来，最可能是选择器失效（站方改版）。
        # 这和「今天没有新内容」是两回事，必须分开报，否则改版会静默变成空列表。
        return [], "selector_missing"

    limit = source.get("limit", 5)
    # PaperNotes 的 sitemap 只有 URL 和时间，标题要逐页去补。
    # 先截断到 limit 再补，避免为了显示 5 条去抓 40 个页面。
    if source["key"] == "papernotes":
        items = enrich_papernotes(
            items[:limit],
            float(source.get("delay", 0)),
            float(source.get("timeout", TIMEOUT)),
        )
        return items[:limit], ""
    # 其余源按同一条规矩：宁可按发布时间/新增顺序排，但只有能解析出时间的才排。
    if all(item.get("published") for item in items):
        items.sort(key=lambda item: item["published"], reverse=True)
    return items[:limit], ""


# ── 缓存与后台刷新 ────────────────────────────────────────────────────────────

_CACHE: dict[str, dict] = {}
_CACHE_LOCK = threading.Lock()
# 保证同一时刻只有一个刷新在跑。没有它的话，6 个源各自过期 + 多个访客同时命中，
# 会启动多个并发刷新线程，把外部站打穿。
_REFRESH_LOCK = threading.Lock()
_LOADED = False


def _load_from_disk() -> None:
    """启动后第一次访问时把上次的快照读进内存，这样重启后的首个访客不用等。"""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    try:
        payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        return
    with _CACHE_LOCK:
        for key, entry in sources.items():
            if isinstance(entry, dict) and isinstance(entry.get("items"), list):
                _CACHE[key] = entry


def _save_to_disk() -> None:
    try:
        DATA_HOME.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    with _CACHE_LOCK:
        payload = {"saved_at": int(time.time()), "sources": dict(_CACHE)}
    tmp = CACHE_FILE.with_name(CACHE_FILE.name + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def _refresh_all() -> None:
    """串行抓所有源。只在后台线程里跑。"""
    for source in FEEDS:
        key = source["key"]
        if source.get("kind") == "none":
            with _CACHE_LOCK:
                _CACHE[key] = {
                    "items": [],
                    "fetched_at": 0,
                    "error": "",
                    "status": "unavailable",
                    "reason": source.get("reason", ""),
                }
            continue
        items, error = fetch_one(source)
        with _CACHE_LOCK:
            _CACHE[key] = {
                "items": items,
                "fetched_at": int(time.time()) if not error else
                              _CACHE.get(key, {}).get("fetched_at", 0),
                "error": error,
                "status": "error" if error else ("ok" if items else "empty"),
            }
    _save_to_disk()


def _kick_refresh() -> None:
    """起一个后台线程刷新。拿不到锁就直接返回 —— 已经有人在刷了。"""
    if not _REFRESH_LOCK.acquire(blocking=False):
        print("[feeds] refresh already running, skipped", flush=True)
        return

    def run() -> None:
        try:
            _refresh_all()
        finally:
            _REFRESH_LOCK.release()

    threading.Thread(target=run, daemon=True, name="feeds-refresh").start()


def _is_stale(now: float) -> bool:
    for source in FEEDS:
        if source.get("kind") == "none":
            continue
        entry = _CACHE.get(source["key"])
        if not entry:
            return True
        if now - entry.get("fetched_at", 0) > source.get("ttl", 1800):
            return True
    return False


def snapshot(force: bool = False) -> dict:
    """给 /api/feeds 用的快照。**不发起任何网络请求**，所以返回时间恒定在毫秒级。"""
    _load_from_disk()
    now = time.time()
    with _CACHE_LOCK:
        cached = {k: dict(v) for k, v in _CACHE.items()}

    stale = _is_stale(now)
    # 冷启动（完全没有缓存）时**短暂**等一下，但不等满。
    #
    # 抓取是串行的，全量实测约 41s（papernotes 的 sitemap 一个就 30s）。
    # 让访客等 41 秒去换一个完整的首屏是不划算的：页面本身（卡片、外链、
    # 说明）才是主体，内容窗格是附带的。所以只等 4 秒 —— 够快到的那几个源
    # 到位（ReadHub 0.5s、阮一峰 0.7s、arXivDaily 2.5s、zeli 3.2s），
    # 慢的留空，前端会在 2.5s 后自己重试一次把剩下的补上。
    #
    # 有旧数据时**完全不等**，立刻返回旧数据 + 后台刷新：陈旧但完整，
    # 好过新鲜但空。
    if not cached:
        _kick_refresh()
        deadline = time.time() + 4.0
        while time.time() < deadline:
            with _CACHE_LOCK:
                if len(_CACHE) >= 4:
                    break
            time.sleep(0.2)
        with _CACHE_LOCK:
            cached = {k: dict(v) for k, v in _CACHE.items()}
    elif stale or force:
        _kick_refresh()

    sources = []
    for source in FEEDS:
        entry = cached.get(source["key"], {})
        item_list = entry.get("items", [])
        if not entry:
            # 还没有它的任何记录 —— 后台刷新还没走到这个源。
            # 这必须和「抓过了，确实没有内容」区分开：前者是"正在读取"，
            # 后者是"今天没更新"。混在一起的话，冷启动的几个空框会
            # 显示成「暂时没有新内容」，等于对外部站做了个错误的断言。
            status = "pending"
        else:
            status = entry.get("status") or ("ok" if item_list else "empty")
        if source.get("kind") == "none":
            status = "unavailable"
        sources.append({
            "key": source["key"],
            "group": source["group"],
            "status": status,
            "reason": source.get("reason", ""),
            "error": entry.get("error", ""),
            "fetched_at": entry.get("fetched_at", 0),
            "link": source["link"],
            # 白名单，不是"返回全部"。**不含任何 HTML 字段** —— 这是安全设计，
            # 不是在省带宽。tests 里有一条专门守着它：加字段必须先改那条测试，
            # 这样就没人能顺手把一个承载 HTML 的字段塞进来。
            #
            # 这里列出的是几个**标量**：图片 URL、公众号名、字数、时长。
            # 它们都是数字或短字符串，前端用的时候仍然走 esc()。
            "items": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("summary", ""),
                    "published": item.get("published", ""),
                    # 下面几个只有 BestBlogs 提供；别的源没有就是空值，
                    # 前端按"有没有 cover"决定走富卡片还是纯文字列表。
                    "cover": item.get("cover", ""),
                    "source": item.get("source", ""),
                    "source_icon": item.get("source_icon", ""),
                    "word_count": item.get("word_count", 0),
                    "read_minutes": item.get("read_minutes", 0),
                    # 标签是字符串数组（「AI总结」这类标记）。仍是标量集合，
                    # 不承载 HTML。
                    "tags": [
                        str(tag)[:20]
                        for tag in (item.get("tags") or [])
                        if isinstance(tag, str) and tag.strip()
                    ][:6],
                    # 下面几个只有 arXivDaily 提供：中文译名、作者、机构。
                    # 都是标量或字符串数组，仍不承载 HTML。
                    "title_cn": item.get("title_cn", ""),
                    "authors": str(item.get("authors") or "")[:200],
                    "affiliations": [
                        str(a)[:60] for a in (item.get("affiliations") or [])
                        if isinstance(a, str)
                    ][:4],
                    "arxiv_id": str(item.get("arxiv_id") or "")[:20],
                    "category": str(item.get("category") or "")[:30],
                }
                for item in item_list
            ],
        })

    return {
        "stale": not any(s["items"] for s in sources),
        "fetched_at": int(now),
        "sources": sources,
    }


def refresh_now() -> dict:
    """同步刷新一次。只给离线校验脚本用，不接在请求路径上。"""
    global _LOADED
    _LOADED = True
    _refresh_all()
    return snapshot()
