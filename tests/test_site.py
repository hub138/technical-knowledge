from __future__ import annotations

"""精简后的站点测试。

原则:只留"改代码才会红"的测试,删掉"改文案也会红"的测试。

保留:
  - 服务器行为(鉴权/压缩/缓存头/安全头/路由可达)
  - vault 数据完整性(元数据/链接可达/红线扫描)
  - 收藏夹管线(往返/上限/校验/追踪状态)
  - feed 抓取管线(清洗/编码/解析/失败隔离/快照白名单)
  - BestBlogs 请求参数契约(枚举值/路径/缓存档位)

删除(2026-09-21,用户要求精简):
  - NavigationContractTests 整类 —— 盯 UI 文本和 class 名,每次改页面
    都要人肉同步断言,是负资产
  - 内容审计(QUALITY/INVENTORY/REVIEW_MODULE 相关) —— 文案措辞审计,
    同样随内容编辑而红;脚本仍在 scripts/ 可手动跑
  - PaperNotes 大部分 —— 解析器已有 --check 兜底,只留入库索引可读一条
  - 文件中段的死代码(两个 interleave 测试在 if __name__ 块之后,
    从来不会被收集执行)

运行: python3 -m unittest tests/test_site
"""

import http.client
import importlib.util
import json
import subprocess
import tempfile
import threading
import time
import unittest
import re
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knowledge_site_server", ROOT / "site" / "server.py")
SERVER_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SERVER_MODULE)


class QuietHandler(SERVER_MODULE.Handler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


class AuthenticationTests(unittest.TestCase):
    """服务器行为:鉴权、压缩、缓存、安全头、路由。

    起一个真实的服务实例(随机端口),全部走 HTTP 层。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.original_local_check = SERVER_MODULE.is_local_client
        SERVER_MODULE.is_local_client = lambda _address: False
        vault = SERVER_MODULE.Vault(ROOT / "vault")
        cls.server = SERVER_MODULE.KnowledgeHTTPServer(
            ("127.0.0.1", 0), QuietHandler, vault, "test-password-only"
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        SERVER_MODULE.is_local_client = cls.original_local_check

    def request(
        self,
        method: str,
        path: str,
        body: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def _login(self) -> str:
        login = self.request(
            "POST",
            "/auth/login",
            json.dumps({"password": "test-password-only"}),
            {"Content-Type": "application/json"},
        )
        assert login[0] == 204, login
        return login[1]["Set-Cookie"].split(";", 1)[0]

    def test_large_json_is_gzipped_when_accepted(self) -> None:
        """大 JSON 必须压缩,且解压后与未压缩完全一致。

        守两件事:压缩没被误删(/api/notes 1.7MB→485KB 的唯一来源,丢了
        不报错只是慢),以及压缩没损坏内容(半截 gzip 流只会表现为
        "数据加载失败",排查方向会被带偏)。"""
        import gzip as _gzip

        status, headers, plain = self.request("GET", "/api/notes")
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers)

        status, headers, packed = self.request(
            "GET", "/api/notes", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertLess(len(packed), len(plain))
        self.assertEqual(_gzip.decompress(packed), plain)

    def test_cache_headers_differ_by_kind(self) -> None:
        """js/css 重新验证,真静态资源可缓存,API/HTML 不缓存。

        曾因 1 小时缓存让浏览器拿旧 shell.js 撞新页面(收藏弹窗不可见)。
        """
        css = self.request("GET", "/site/base.css")
        if css[0] != 200:
            css = self.request("GET", "/static/base.css")
        if css[0] == 200:
            self.assertIn("no-cache", css[1].get("Cache-Control", ""))

        svg = self.request("GET", "/favicon.svg")
        if svg[0] == 200:
            self.assertIn("max-age", svg[1].get("Cache-Control", ""))

        api = self.request("GET", "/api/notes")
        self.assertEqual(api[0], 200)
        self.assertIn("no-store", api[1].get("Cache-Control", ""))

        page = self.request("GET", "/")
        self.assertEqual(page[0], 200)
        self.assertIn("no-cache", page[1].get("Cache-Control", ""))

    def test_external_clients_cannot_reach_openmaic_without_the_site_password(self) -> None:
        """模型凭据只属于本机。非本机地址的请求必须弹回登录页,不能拿到
        工具会话,邻居不该花掉机主的配额。"""
        original = SERVER_MODULE.is_local_client
        SERVER_MODULE.is_local_client = lambda _address: False
        try:
            launch = self.request("GET", "/launch/openmaic?next=%2F")
            self.assertEqual(launch[0], 302)
            self.assertTrue(launch[1]["Location"].startswith("/auth/login?next="))
            self.assertNotIn("openmaic_access=", launch[1].get("Set-Cookie", ""))
        finally:
            SERVER_MODULE.is_local_client = original

    def test_valid_login_creates_protected_cookie(self) -> None:
        bad = self.request(
            "POST", "/auth/login",
            json.dumps({"password": "wrong"}), {"Content-Type": "application/json"},
        )
        good = self.request(
            "POST", "/auth/login",
            json.dumps({"password": "test-password-only"}), {"Content-Type": "application/json"},
        )
        self.assertEqual(bad[0], 401)
        self.assertEqual(good[0], 204)
        set_cookie = good[1]["Set-Cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)

        cookie = set_cookie.split(";", 1)[0]
        api = self.request("GET", "/api/notes", headers={"Cookie": cookie})
        self.assertEqual(api[0], 200)
        self.assertGreater(len(json.loads(api[2])["notes"]), 100)

    def test_cross_origin_preflight_is_rejected(self) -> None:
        self.assertEqual(self.request("OPTIONS", "/api/notes")[0], 403)

    def test_public_pages_send_browser_security_headers(self) -> None:
        response = self.request("GET", "/learn/history")
        self.assertEqual(response[0], 200)
        self.assertEqual(response[1]["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("Permissions-Policy", response[1])
        policy = response[1]["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("form-action 'self'", policy)
        self.assertIn("frame-ancestors 'self'", policy)

    def test_authenticated_navigation_routes_are_live(self) -> None:
        """核心路由必须活着且返回内容。这是"站点没挂"的底线检查。"""
        cookie = self._login()
        note_path = "工程知识/AI 系统工程：从模型能力到生产能力/知识与检索/RAG的核心是选择可引用证据.md"
        routes = [
            "/", "/learn", "/learn/openmaic", "/learn/intuition", "/learn/transfer",
            "/learn/history", "/projects", "/apps/agent-evaluation",
            "/apps/agent-evaluation/", "/apps/agent-evaluation/index.html",
            "/health", "/api/notes", "/api/access",
            "/api/note?path=" + quote(note_path),
            "/projects/archify/README.md", "/projects/OpenMAIC/README-zh",
            "/static/base.css", "/static/shell.js",
        ]
        for route in routes:
            with self.subTest(route=route):
                response = self.request("GET", route, headers={"Cookie": cookie})
                self.assertEqual(response[0], 200)
                self.assertGreater(len(response[2]), 0)

        health = self.request("GET", "/health", headers={"Cookie": cookie})
        self.assertGreater(json.loads(health[2])["notes"], 100)
        note = self.request("GET", "/api/note?path=" + quote(note_path), headers={"Cookie": cookie})
        self.assertIn("RAG", json.loads(note[2])["title"])

    def test_tool_redirects_do_not_trust_request_host(self) -> None:
        """重定向目标必须用服务端自己的 public_host(),不能信请求 Host 头
        —— 否则攻击者域名会把用户带去钓鱼站。"""
        original = SERVER_MODULE.public_host
        original_secret = SERVER_MODULE.read_keychain_secret
        SERVER_MODULE.public_host = lambda: "192.168.1.4"
        SERVER_MODULE.read_keychain_secret = lambda service: (
            "test-openmaic-access"
            if service == SERVER_MODULE.OPENMAIC_ACCESS_SERVICE
            else original_secret(service)
        )
        try:
            cookie = self._login()
            response = self.request(
                "GET", "/launch/openmaic?next=%2F",
                headers={"Cookie": cookie, "Host": "attacker.example"},
            )
            self.assertEqual(response[0], 303)
            self.assertTrue(response[1]["Location"].startswith("http://192.168.1.4:3100/"))
        finally:
            SERVER_MODULE.public_host = original
            SERVER_MODULE.read_keychain_secret = original_secret

    def test_local_tool_access_does_not_need_a_site_cookie(self) -> None:
        original = SERVER_MODULE.is_local_client
        original_secret = SERVER_MODULE.read_keychain_secret
        SERVER_MODULE.is_local_client = lambda _address: True
        SERVER_MODULE.read_keychain_secret = lambda service: (
            "test-openmaic-access"
            if service == SERVER_MODULE.OPENMAIC_ACCESS_SERVICE
            else original_secret(service)
        )
        try:
            response = self.request("GET", "/launch/openmaic?next=%2F")
            self.assertEqual(response[0], 303)
            self.assertTrue(response[1]["Location"].startswith("http://"))
            self.assertIn("openmaic_access=", response[1]["Set-Cookie"])
        finally:
            SERVER_MODULE.is_local_client = original
            SERVER_MODULE.read_keychain_secret = original_secret

    def test_tool_redirect_encodes_unicode_return_path(self) -> None:
        original_local = SERVER_MODULE.is_local_client
        original_secret = SERVER_MODULE.read_keychain_secret
        SERVER_MODULE.is_local_client = lambda _address: True
        SERVER_MODULE.read_keychain_secret = lambda service: (
            "test-openmaic-access"
            if service == SERVER_MODULE.OPENMAIC_ACCESS_SERVICE
            else original_secret(service)
        )
        try:
            response = self.request(
                "GET",
                "/launch/openmaic?next=" + quote("/?topic=RAG 从向量检索到重排的演进", safe=""),
            )
            self.assertEqual(response[0], 303)
            location = response[1]["Location"]
            self.assertTrue(location.startswith("http://"))
            self.assertIn("topic=RAG%20", location)
            self.assertNotRegex(location, r"[^\x00-\x7f]")
        finally:
            SERVER_MODULE.is_local_client = original_local
            SERVER_MODULE.read_keychain_secret = original_secret

    def test_legacy_home_aliases_canonicalize(self) -> None:
        for path in (
            "/index.html",
            "/?domain=%E6%80%BB%E8%A7%88&topic=%E9%A6%96%E9%A1%B5",
            "/?path=%E7%9F%A5%E8%AF%86%E5%BA%93%E9%A6%96%E9%A1%B5.md",
        ):
            with self.subTest(path=path):
                response = self.request("GET", path)
                self.assertEqual(response[0], 308)
                self.assertEqual(response[1]["Location"], "/")


class OriginLocalTests(unittest.TestCase):
    """本机判定必须认得「隧道送进来的回环流量」。

    SSH 反向隧道把公网访客送到回环别名上，源地址恒为 127.0.0.1——只看
    来源会把公网访客全放成本机（实测公网可开 /insights、免密启动工具）。
    判定要同时看连接目的地址（内核级事实，伪造不了）。
    """

    def test_true_loopback_pair_is_local(self) -> None:
        self.assertTrue(SERVER_MODULE.origin_is_local("127.0.0.1", "127.0.0.1"))
        self.assertTrue(SERVER_MODULE.origin_is_local("::1", "::1"))

    def test_tunnel_alias_destination_is_not_local(self) -> None:
        self.assertFalse(SERVER_MODULE.origin_is_local("127.0.0.1", "127.10.0.1"))

    def test_ipv4_mapped_tunnel_alias_is_not_local(self) -> None:
        self.assertFalse(SERVER_MODULE.origin_is_local("::ffff:127.0.0.1", "::ffff:127.10.0.1"))

    def test_lan_visitor_is_not_local(self) -> None:
        self.assertFalse(SERVER_MODULE.origin_is_local("10.1.2.3", "10.95.30.97"))

    def test_own_interface_pair_is_local(self) -> None:
        # 本机进程走自身网卡地址访问自己（如 curl http://10.95.30.97:8787），
        # 源与目的都是本机地址 → 本机。
        self.assertTrue(SERVER_MODULE.origin_is_local("127.0.0.1", "10.95.30.97"))


class UiCopyTests(unittest.TestCase):
    """UI 文案规范：标题下的描述类文案不以句号结尾。

    成熟产品的惯例（GitHub 仓库描述、Stripe/Linear 的 hero 副标题）：
    短语式单句描述无尾标点；多句段落与报错句不受此约束。nav.js 的
    description 是侧栏 tooltip 与子页面页头（shell.js PAGE_META 派生）
    的唯一真源，在这里守住即可覆盖两处。
    """

    def test_nav_descriptions_have_no_trailing_period(self) -> None:
        nav = (ROOT / "site" / "nav.js").read_text(encoding="utf-8")
        for m in re.finditer(r'description: "([^"]+)"', nav):
            self.assertFalse(
                m.group(1).endswith("。"),
                f"导航描述以句号结尾（描述类短语不带尾标点）: {m.group(1)}",
            )


class VaultIntegrityTests(unittest.TestCase):
    """vault 数据完整性:元数据、链接可达、发布红线。

    这些测的是数据不是代码,不会因为改页面而红。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.vault = SERVER_MODULE.Vault(ROOT / "vault")

    def test_core_notes_have_required_metadata(self) -> None:
        required = {"title", "updated", "review_after", "change_rate", "confidence", "sources"}
        failures: list[str] = []
        for note in self.vault.notes.values():
            if not str(note["path"]).startswith("工程知识/"):
                continue
            missing = [key for key in required if not note.get(key)]
            if missing:
                failures.append(f"{note['path']}: {', '.join(missing)}")
        self.assertEqual(failures, [])

    def test_wikilinks_resolve(self) -> None:
        """读者能点到的 wikilink 必须可达。围栏代码块排除在外——里面是模板
        和示例,不是导航。"""
        fence_re = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
        unresolved: list[str] = []
        for relative, note in self.vault.notes.items():
            prose = fence_re.sub("", str(note["body"]))
            for target, _label in SERVER_MODULE.WIKILINK_RE.findall(prose):
                if not self.vault.resolve_note(target, relative):
                    unresolved.append(f"{relative} -> {target}")
        self.assertEqual(unresolved, [])

    def test_vault_never_contains_internal_product_names(self) -> None:
        """内部产品名绝不能出现在 vault 的任何文件里——正文、标题、文件名、
        链接都算。发布红线:名字进了仓库等于宣告内部产品存在这些缺陷。"""
        banned = re.compile(r"tbase|tchouse|csig", re.IGNORECASE)
        version = re.compile(r"v\d+\.\d+\.\d+\.\d+")
        hits = []
        for path in (ROOT / "vault").rglob("*.md"):
            rel = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8", errors="replace")
            if banned.search(text) or version.search(text):
                hits.append(rel)
        self.assertEqual(hits, [], "vault 内出现内部产品名或内部版本号")

    def test_every_core_note_has_an_incoming_link(self) -> None:
        linked = {edge["target"] for edge in self.vault.edges()}
        orphans = [
            str(note["path"])
            for note in self.vault.notes.values()
            if str(note["path"]).startswith("工程知识/") and note["path"] not in linked
        ]
        self.assertEqual(orphans, [])


class FavoritesTests(unittest.TestCase):
    """收藏夹管线:往返、上限、校验、追踪状态。DATA_HOME 换临时目录。"""

    def test_favorites_round_trip_and_limits(self) -> None:
        server = SERVER_MODULE
        item = {
            "title": "测试文章",
            "url": "https://example.com/a",
            "summary": "摘要" * 1500,
            "source": "测试源",
            "score": 90,
        }
        with tempfile.TemporaryDirectory() as tmp:
            original = server.DATA_HOME
            server.DATA_HOME = Path(tmp)
            try:
                self.assertEqual(server._load_favorites(), [])
                ok, err = server.favorites_add("t:1", item)
                self.assertTrue(ok, err)
                entries = server._load_favorites()
                self.assertEqual(len(entries), 1)
                stored = entries[0]
                self.assertEqual(stored["id"], "t:1")
                self.assertLessEqual(len(str(stored["item"]["summary"])), 2000)
                self.assertEqual(stored["item"]["score"], 90)
                # 2026-09-22：POST 语义改为 upsert 后，同 id 再收藏 =
                # 更新成功而非 already_favorited（favorites_update 路径）。
                ok, err = server.favorites_add("t:1", item)
                self.assertFalse(ok)
                self.assertEqual(err, "already_favorited")
                self.assertEqual(server.favorites_remove("t:1"), 1)
                self.assertEqual(server._load_favorites(), [])
                self.assertEqual(server.favorites_remove("t:missing"), 0)
            finally:
                server.DATA_HOME = original

    def test_favorites_update_refreshes_snapshot(self) -> None:
        """2026-09-22 新增：favorites_update 守门——收藏快照可被刷新。

        链路：前端 favRefreshItem 在早报刷新后 POST 最新字段 → POST 接口
        对同 id 走 favorites_update。要守的行为：
        - 同 id 更新成功，评分等字段换成新值，favorited_at 不变；
        - URL 变了 → url_mismatch 拒绝（URL 是判重锚点不能漂移）；
        - id 不存在 → not_found（由接口层决定是否转 add）；
        - 无标题/无 URL → invalid。"""
        server = SERVER_MODULE
        item = {"title": "旧标题", "url": "https://example.com/a", "score": 90}
        with tempfile.TemporaryDirectory() as tmp:
            original = server.DATA_HOME
            server.DATA_HOME = Path(tmp)
            try:
                self.assertTrue(server.favorites_add("t:1", item)[0])
                first = server._load_favorites()[0]
                stamped = first["favorited_at"]
                fresh = {"title": "新标题", "url": "https://example.com/a", "score": 95}
                ok, err = server.favorites_update("t:1", fresh)
                self.assertTrue(ok, err)
                entry = server._load_favorites()[0]
                self.assertEqual(entry["item"]["title"], "新标题")
                self.assertEqual(entry["item"]["score"], 95)
                self.assertEqual(entry["favorited_at"], stamped)
                moved = {"title": "另一篇", "url": "https://example.com/b", "score": 88}
                ok, err = server.favorites_update("t:1", moved)
                self.assertFalse(ok)
                self.assertEqual(err, "url_mismatch")
                ok, err = server.favorites_update("t:missing", fresh)
                self.assertFalse(ok)
                self.assertEqual(err, "not_found")
                ok, err = server.favorites_update("t:1", {"summary": "缺标题"})
                self.assertFalse(ok)
                self.assertEqual(err, "invalid")
            finally:
                server.DATA_HOME = original

    def test_favorites_cap_is_enforced(self) -> None:
        server = SERVER_MODULE
        with tempfile.TemporaryDirectory() as tmp:
            original = server.DATA_HOME
            server.DATA_HOME = Path(tmp)
            try:
                for n in range(server.FAVORITES_CAP):
                    ok, err = server.favorites_add(f"t:{n}", {"title": f"文{n}", "url": f"https://example.com/{n}"})
                    self.assertTrue(ok, (n, err))
                ok, err = server.favorites_add("t:over", {"title": "第 101 篇", "url": "https://example.com/over"})
                self.assertFalse(ok)
                self.assertEqual(err, "favorites_full")
                self.assertEqual(len(server._load_favorites()), server.FAVORITES_CAP)
            finally:
                server.DATA_HOME = original

    def test_favorites_reject_unshaped_items(self) -> None:
        server = SERVER_MODULE
        with tempfile.TemporaryDirectory() as tmp:
            original = server.DATA_HOME
            server.DATA_HOME = Path(tmp)
            try:
                ok, err = server.favorites_add("t:bad", {"summary": "只有摘要"})
                self.assertFalse(ok)
                self.assertEqual(err, "invalid")
            finally:
                server.DATA_HOME = original

    def test_favorites_and_feedback_privacy(self) -> None:
        """收藏是读者亲手挑的内容,必须进版本库(换机器不空);反馈与访问
        记录含访客隐私,必须忽略。"""
        tracked = subprocess.run(
            ["git", "check-ignore", "-q", "data/favorites.json"],
            cwd=ROOT, capture_output=True,
        )
        self.assertNotEqual(tracked.returncode, 0, "收藏数据应进版本库")
        for private in ("data/feedback.jsonl", "data/visits.jsonl"):
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", private],
                cwd=ROOT, capture_output=True,
            )
            self.assertEqual(ignored.returncode, 0, f"{private} 必须忽略")

    def test_wecom_key_never_lives_in_tracked_files(self) -> None:
        """群机器人 key 是凭据,只能住 Keychain;会被提交的文件里不能有。"""
        for relative in ("site/server.py", "index.html", "site/shell.js", "site/insights.html"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotRegex(
                text, r"webhook/send\?key=[0-9a-f]{8}-",
                f"{relative} 不应内嵌 webhook key",
            )


class FeedTests(unittest.TestCase):
    """外部源抓取:清洗、链接、编码、解析、失败隔离。

    完全不碰网络——外部站抖一下就红的测试没人信。只测纯函数。
    """

    RSS_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel><title>Readhub</title>
      <item>
        <title>某公司发布某产品</title>
        <link>https://readhub.cn/topic/abc</link>
        <description>&lt;p&gt;摘要里的&lt;b&gt;正文&lt;/b&gt;内容&lt;/p&gt;</description>
        <pubDate>Fri, 18 Sep 2026 04:31:23 GMT</pubDate>
      </item>
      <item>
        <title>第二条</title>
        <link>/topic/relative</link>
        <description>纯文本摘要</description>
        <pubDate>Thu, 17 Sep 2026 10:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>周刊第 412 期</title>
        <link rel="alternate" href="http://example.com/blog/412.html"/>
        <summary>这里记录每周值得分享的内容。</summary>
        <published>2026-09-11T00:11:50Z</published>
        <updated>2026-09-18T10:18:41Z</updated>
      </entry>
    </feed>"""

    def test_clean_text_drops_script_content(self) -> None:
        result = FEEDS_MODULE.clean_text(
            "<script>alert('xss')</script><style>.a{color:red}</style><p>真正的正文</p>"
        )
        self.assertIn("真正的正文", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("color:red", result)

    def test_clean_text_survives_malformed_html(self) -> None:
        for bad in ("<p>未闭合", "</unopened>", "<a href='>'>", ""):
            self.assertIsInstance(FEEDS_MODULE.clean_text(bad), str)

    def test_absolute_url_rejects_dangerous_schemes(self) -> None:
        """协议白名单是必需的:urljoin 不拦 javascript:,原样进 href 就在本站执行。"""
        for bad in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:x",
            "file:///etc/passwd",
        ):
            self.assertEqual(FEEDS_MODULE.absolute_url(bad, "https://x.com/"), "", bad)

    def test_decode_body_never_raises_on_broken_bytes(self) -> None:
        self.assertIsInstance(FEEDS_MODULE.decode_body(b"\xff\xfe\x00bad", ""), str)

    def test_parse_rss(self) -> None:
        items, error = FEEDS_MODULE.parse_xml_feed(self.RSS_SAMPLE, "https://readhub.cn/rss")
        self.assertEqual(error, "")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "某公司发布某产品")
        self.assertEqual(items[0]["url"], "https://readhub.cn/topic/abc")
        self.assertNotIn("<b>", items[0]["summary"])
        self.assertEqual(items[1]["url"], "https://readhub.cn/topic/relative")

    def test_parse_atom_prefers_published_over_updated(self) -> None:
        """updated 是 feed 重新生成的时间,不是文章日期。按 updated 排会乱序。"""
        items, error = FEEDS_MODULE.parse_xml_feed(self.ATOM_SAMPLE, "http://example.com/blog/atom.xml")
        self.assertEqual(error, "")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["published"].startswith("2026-09-11"), items[0]["published"])

    def test_source_failure_does_not_break_others(self) -> None:
        """一个源抛异常,其余源照常返回。_save_to_disk 必须换掉——否则桩数据
        会覆盖真实缓存,这个坑犯过一次。"""
        original_fetch = FEEDS_MODULE.fetch_one
        original_save = FEEDS_MODULE._save_to_disk
        calls: list[str] = []

        def fake(source: dict) -> tuple[list[dict], str]:
            calls.append(source["key"])
            if source["key"] == "readhub":
                return [], "unreachable"
            return ([{"title": "t", "url": "https://x.com/a", "summary": "", "published": ""}], "")

        FEEDS_MODULE.fetch_one = fake
        FEEDS_MODULE._save_to_disk = lambda: None
        try:
            FEEDS_MODULE._refresh_all()
        finally:
            FEEDS_MODULE.fetch_one = original_fetch
            FEEDS_MODULE._save_to_disk = original_save
            FEEDS_MODULE._CACHE.clear()

        self.assertIn("readhub", calls)
        self.assertGreaterEqual(len(calls), 5)

    def test_snapshot_exposes_no_html_field(self) -> None:
        """快照里不能有承载 HTML 的字段——让它根本不存在,XSS 面从源头没了。"""
        payload = FEEDS_MODULE.snapshot()
        allowed = {
            "title", "url", "summary", "published",
            "cover", "source", "source_icon", "word_count", "read_minutes",
            "tags", "title_cn", "authors", "affiliations", "arxiv_id", "category",
            "score",
            # 2026-09-22 放行 author：zeli 源的作者署名标量字段（短字符串
            # 限长 60，不承载 HTML），与 snapshot() 白名单同步。
            "author",
        }
        forbidden = {"html", "content", "body", "rendered", "innerHTML"}
        for source in payload["sources"]:
            for item in source["items"]:
                self.assertTrue(
                    set(item) <= allowed,
                    f"{source['key']} 的条目出现了越界字段: {set(item) - allowed}",
                )
                self.assertFalse(
                    set(item) & forbidden,
                    f"{source['key']} 的条目带了 HTML 承载字段: {set(item) & forbidden}",
                )

    def test_snapshot_covers_every_declared_source(self) -> None:
        payload = FEEDS_MODULE.snapshot()
        self.assertEqual(
            {s["key"] for s in payload["sources"]},
            {s["key"] for s in FEEDS_MODULE.FEEDS},
        )

    def test_feeds_declare_a_known_kind(self) -> None:
        for source in FEEDS_MODULE.FEEDS:
            self.assertIn(source["kind"], {"rss", "atom", "html", "api", "none", "podcast"}, source["key"])
            self.assertTrue(source["url"].startswith("https://"), source["key"])
            self.assertIn("ttl", source)


FEEDS_SPEC = importlib.util.spec_from_file_location(
    "knowledge_site_feeds", ROOT / "site" / "feeds.py"
)
FEEDS_MODULE = importlib.util.module_from_spec(FEEDS_SPEC)
assert FEEDS_SPEC.loader is not None
FEEDS_SPEC.loader.exec_module(FEEDS_MODULE)

PAPERNOTES_SPEC = importlib.util.spec_from_file_location(
    "fetch_papernotes", ROOT / "scripts" / "fetch-papernotes.py"
)
PAPERNOTES_MODULE = importlib.util.module_from_spec(PAPERNOTES_SPEC)
assert PAPERNOTES_SPEC.loader is not None
PAPERNOTES_SPEC.loader.exec_module(PAPERNOTES_MODULE)


class PaperNotesTests(unittest.TestCase):
    """PaperNotes 只留入库索引可读一条——解析器回归由 fetch-papernotes.py
    --check 兜底(在 check_all.py 里仍然跑)。"""

    def test_committed_index_is_readable(self) -> None:
        index = json.loads(PAPERNOTES_MODULE.INDEX.read_text(encoding="utf-8"))
        papers = index["papers"]
        self.assertGreater(len(papers), 20000)
        for paper in papers[:200]:
            self.assertTrue(paper["title"])
            self.assertTrue(paper["url"].startswith("https://papernotes.org/"))
            self.assertIsInstance(paper["tags"], list)


BESTBLOGS_SPEC = importlib.util.spec_from_file_location(
    "knowledge_site_bestblogs", ROOT / "site" / "bestblogs.py"
)
BESTBLOGS_MODULE = importlib.util.module_from_spec(BESTBLOGS_SPEC)
assert BESTBLOGS_SPEC.loader is not None
BESTBLOGS_SPEC.loader.exec_module(BESTBLOGS_MODULE)


class BestBlogsRequestTests(unittest.TestCase):
    """BestBlogs 请求参数契约。

    这类 bug 是静默的:服务端对无效取值不报错直接忽略,返回默认排序的旧
    内容,看起来"接口通了"实际拿的是错数据。用假请求函数截下实际发出的
    参数做断言,不打网络。
    """

    def setUp(self) -> None:
        if not BESTBLOGS_MODULE.api_key():
            self.skipTest("未配置 bestblogs.key")
        self.calls: list[tuple[str, dict]] = []
        self._orig_get = BESTBLOGS_MODULE._get
        self._orig_save = BESTBLOGS_MODULE._save_cache
        self._orig_save_brief = BESTBLOGS_MODULE._save_brief_cache
        BESTBLOGS_MODULE._save_cache = lambda: None
        BESTBLOGS_MODULE._save_brief_cache = lambda: None
        self.respond_with([], "")

    def respond_with(self, data: object, error: str) -> None:
        def fake_get(path: str, params: dict) -> tuple[object, str]:
            self.calls.append((path, dict(params)))
            return data, error
        BESTBLOGS_MODULE._get = fake_get

    def tearDown(self) -> None:
        BESTBLOGS_MODULE._get = self._orig_get
        BESTBLOGS_MODULE._save_cache = self._orig_save
        BESTBLOGS_MODULE._save_brief_cache = self._orig_save_brief

    def test_resources_uses_documented_enum_values(self) -> None:
        BESTBLOGS_MODULE.digest(limit=3, force=True)
        calls = [c for c in self.calls if c[0] == "resources"]
        self.assertTrue(calls, "应当请求过 /openapi/v2/resources")
        for _, params in calls:
            self.assertEqual(params.get("type"), "article",
                             "type 必须是小写 article;大写 ARTICLE 会被静默忽略")
            self.assertEqual(params.get("language"), "zh",
                             "language 必须是 zh/en/all;zh_CN 会被静默忽略")

    def test_brief_uses_the_briefs_public_path(self) -> None:
        """早报走 /openapi/v2/briefs/public/<date>,文档里的 /brief 是 404。"""
        self.respond_with({"contentItems": []}, "")
        BESTBLOGS_MODULE.brief(force=True)
        paths = [c[0] for c in self.calls]
        self.assertTrue(paths, "应当请求过早报端点")
        for path in paths:
            self.assertTrue(path.startswith("briefs/public/"),
                            f"{path} 不在 briefs/public/ 下")
            tail = path.split("/")[-1]
            self.assertTrue(
                tail == "today" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", tail),
                f"{path} 的最后一段既不是 today 也不是 ISO 日期",
            )

    def test_a_failed_fetch_is_not_cached_for_a_whole_day(self) -> None:
        """抓失败只能锁一小段:配额中午恢复,页面却要空到第二天,是把
        "这次没抓到"当成"确认没有"。digest 和 brief 都要守。"""
        retry = float(BESTBLOGS_MODULE._RETRY_TTL)
        day = float(BESTBLOGS_MODULE._CACHE_TTL)
        self.assertLess(retry, day)

        self.respond_with(None, "quota")

        digest_cache_backup = dict(BESTBLOGS_MODULE._CACHE)
        BESTBLOGS_MODULE._CACHE.clear()
        BESTBLOGS_MODULE._CACHE.update({"at": 0.0, "items": [], "status": "unknown", "ttl": 0.0})
        result = BESTBLOGS_MODULE.digest(limit=3, force=True)
        self.assertEqual(result.get("status"), "quota")
        self.assertLessEqual(
            float(BESTBLOGS_MODULE._CACHE.get("ttl") or 0), retry,
            "配额耗尽后写入的 ttl 必须是短档",
        )
        BESTBLOGS_MODULE._CACHE.clear()
        BESTBLOGS_MODULE._CACHE.update(digest_cache_backup)

        brief_cache_backup = dict(BESTBLOGS_MODULE._brief_cache)
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update({"at": 0.0, "payload": {}, "ttl": 0.0})
        with tempfile.TemporaryDirectory() as tmp:
            original_lg = BESTBLOGS_MODULE._LAST_GOOD_FILE
            original_arch = BESTBLOGS_MODULE._ARCHIVE_FILE
            BESTBLOGS_MODULE._LAST_GOOD_FILE = Path(tmp) / "last-good.json"
            BESTBLOGS_MODULE._ARCHIVE_FILE = Path(tmp) / "archive.json"
            try:
                result = BESTBLOGS_MODULE.brief(force=True)
                self.assertEqual(result.get("status"), "quota")
                self.assertLessEqual(
                    float(BESTBLOGS_MODULE._brief_cache.get("ttl") or 0), retry,
                    "早报抓失败后写入的 ttl 也必须是短档",
                )
                BESTBLOGS_MODULE._save_last_good(
                    [{"title": "存量", "url": "https://example.com/x", "score": 90}],
                    "2026-09-13", 1.0,
                )
                result = BESTBLOGS_MODULE.brief(force=True)
                self.assertEqual(result.get("status"), "stale")
                self.assertEqual(len(result.get("items") or []), 1)
                self.assertGreater(result.get("stale_age_days", 0), 0)
            finally:
                BESTBLOGS_MODULE._LAST_GOOD_FILE = original_lg
                BESTBLOGS_MODULE._ARCHIVE_FILE = original_arch
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update(brief_cache_backup)


if __name__ == "__main__":
    unittest.main()
