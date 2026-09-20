from __future__ import annotations

import http.client
import importlib.util
import json
import subprocess
import tempfile
import threading
import time
import unittest
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("knowledge_site_server", ROOT / "site" / "server.py")
SERVER_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SERVER_MODULE)
QUALITY_SPEC = importlib.util.spec_from_file_location(
    "knowledge_quality_audit", ROOT / "scripts" / "audit-knowledge-quality.py"
)
QUALITY_MODULE = importlib.util.module_from_spec(QUALITY_SPEC)
assert QUALITY_SPEC.loader is not None
QUALITY_SPEC.loader.exec_module(QUALITY_MODULE)
INVENTORY_SPEC = importlib.util.spec_from_file_location(
    "editorial_inventory", ROOT / "scripts" / "editorial-inventory.py"
)
INVENTORY_MODULE = importlib.util.module_from_spec(INVENTORY_SPEC)
assert INVENTORY_SPEC.loader is not None
INVENTORY_SPEC.loader.exec_module(INVENTORY_MODULE)
REVIEW_SPEC = importlib.util.spec_from_file_location(
    "knowledge_quality_review", ROOT / "scripts" / "review-knowledge-quality.py"
)
REVIEW_MODULE = importlib.util.module_from_spec(REVIEW_SPEC)
assert REVIEW_SPEC.loader is not None
REVIEW_SPEC.loader.exec_module(REVIEW_MODULE)


def parse_nav_items() -> list[dict[str, object]]:
    """Read the navigation data out of site/nav.js.

    The nav used to be a literal array inside whichever file rendered it, so
    tests pinned the text. It is now one data file with one renderer, so tests
    should read the data and check properties of it — which entries exist, which
    are owner-only — instead of looking for a particular string.
    """
    source = (ROOT / "site" / "nav.js").read_text(encoding="utf-8")
    start = source.index("items: [")
    end = source.index("\n  ],", start)
    block = source[start:end]
    items: list[dict[str, object]] = []
    for entry in re.finditer(r"\{\s*key:\s*\"([^\"]+)\"(.*?)\n    \}", block, re.S):
        key, body = entry.group(1), entry.group(2)
        item: dict[str, object] = {"key": key}
        href = re.search(r'href:\s*"([^"]+)"', body)
        label = re.search(r'label:\s*"([^"]+)"', body)
        if href:
            item["href"] = href.group(1)
        if label:
            item["label"] = label.group(1)
        if re.search(r"localOnly:\s*true", body):
            item["localOnly"] = True
        if re.search(r"parent:\s*\"", body):
            item["parent"] = True
        items.append(item)
    return items


class QuietHandler(SERVER_MODULE.Handler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


class AuthenticationTests(unittest.TestCase):
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

    def test_large_json_is_gzipped_when_accepted(self) -> None:
        """大 JSON 必须压缩，且解压后与未压缩完全一致。

        这条守两件事：
          1. 压缩没被误删 —— 它是 /api/notes 1.7MB → 485KB 的唯一来源，
             丢了不会有任何功能报错，只是慢，属于最难发现的那种退化。
          2. 压缩没有损坏内容。半截的 gzip 流解压会抛异常，而页面只会
             表现为"数据加载失败"，排查方向会被带到别处。
        """
        import gzip as _gzip

        status, headers, plain = self.request("GET", "/api/notes")
        self.assertEqual(status, 200)
        self.assertNotIn("Content-Encoding", headers,
                         "没请求 gzip 时不该压缩")

        status, headers, packed = self.request(
            "GET", "/api/notes", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertLess(len(packed), len(plain),
                        "压缩后应当更小；没更小说明压了也没意义")
        self.assertEqual(_gzip.decompress(packed), plain,
                         "解压后的字节必须和未压缩逐字节相同")

    def test_cache_headers_differ_by_kind(self) -> None:
        """静态资源可缓存，API 不缓存。

        曾经所有响应一律 no-store，包括 base.css 和 mermaid.min.js ——
        那些文件每次访问都重新下载。这类退化没有任何功能症状，
        只有网络面板能看出来，所以用它守住。
        """
        css = self.request("GET", "/site/base.css")
        if css[0] != 200:
            css = self.request("GET", "/static/base.css")
        if css[0] == 200:
            self.assertIn("max-age", css[1].get("Cache-Control", ""),
                          "静态资源应该可缓存")

        api = self.request("GET", "/api/notes")
        self.assertEqual(api[0], 200)
        self.assertIn("no-store", api[1].get("Cache-Control", ""),
                      "API 不该被缓存")

        page = self.request("GET", "/")
        self.assertEqual(page[0], 200)
        self.assertIn("no-cache", page[1].get("Cache-Control", ""),
                      "HTML 要重新验证")

    def test_external_knowledge_is_public_but_tool_launch_requires_authentication(self) -> None:
        page = self.request("GET", "/?domain=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD")
        api = self.request("GET", "/api/notes")
        access = self.request("GET", "/api/access")
        launch = self.request("GET", "/launch/deeptutor?next=%2Fchat")

        self.assertEqual(page[0], 200)
        self.assertGreater(len(page[2]), 1000)
        self.assertEqual(api[0], 200)
        self.assertGreater(len(json.loads(api[2])["notes"]), 100)
        self.assertEqual(access[0], 200)
        self.assertEqual(json.loads(access[2])["knowledge_public"], True)
        self.assertEqual(launch[0], 302)
        self.assertTrue(launch[1]["Location"].startswith("/auth/login?next="))

    def test_external_clients_cannot_reach_openmaic_without_the_site_password(self) -> None:
        """The machine-configured model credential is for this Mac only.

        A request that does not originate from one of this host's own addresses
        must be bounced to the login page instead of being handed a tool
        session, so a LAN neighbour never spends the owner's quota.
        """
        original = SERVER_MODULE.is_local_client
        SERVER_MODULE.is_local_client = lambda _address: False
        try:
            launch = self.request("GET", "/launch/openmaic?next=%2F")
            self.assertEqual(launch[0], 302)
            self.assertTrue(launch[1]["Location"].startswith("/auth/login?next="))
            self.assertNotIn("openmaic_access=", launch[1].get("Set-Cookie", ""))
        finally:
            SERVER_MODULE.is_local_client = original

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

    def test_valid_login_creates_protected_cookie(self) -> None:
        bad = self.request(
            "POST",
            "/auth/login",
            json.dumps({"password": "wrong"}),
            {"Content-Type": "application/json"},
        )
        good = self.request(
            "POST",
            "/auth/login",
            json.dumps({"password": "test-password-only"}),
            {"Content-Type": "application/json"},
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
        response = self.request("OPTIONS", "/api/notes")
        self.assertEqual(response[0], 403)

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

    def test_head_requests_return_headers_without_a_body(self) -> None:
        for path in ("/", "/learn/history", "/health", "/api/notes"):
            with self.subTest(path=path):
                response = self.request("HEAD", path)
                self.assertEqual(response[0], 200)
                self.assertIn("Content-Length", response[1])
                self.assertEqual(response[2], b"")

    def test_authenticated_navigation_routes_are_live(self) -> None:
        login = self.request(
            "POST",
            "/auth/login",
            json.dumps({"password": "test-password-only"}),
            {"Content-Type": "application/json"},
        )
        cookie = login[1]["Set-Cookie"].split(";", 1)[0]
        note_path = "工程知识/AI系统/知识与检索/RAG的核心是选择可引用证据.md"
        routes = [
            "/",
            "/learn",
            "/learn/openmaic",
            "/learn/intuition",
            "/learn/transfer",
            "/learn/history",
            "/projects",
            "/apps/agent-evaluation",
            "/apps/agent-evaluation/",
            "/apps/agent-evaluation/index.html",
            "/health",
            "/api/notes",
            "/api/access",
            "/api/note?path=" + quote(note_path),
            "/projects/archify/README.md",
            "/projects/OpenMAIC/README-zh",
            "/static/base.css",
            "/static/shell.js",
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
        original = SERVER_MODULE.public_host
        original_secret = SERVER_MODULE.read_keychain_secret
        SERVER_MODULE.public_host = lambda: "192.168.1.4"
        SERVER_MODULE.read_keychain_secret = lambda service: (
            "test-openmaic-access"
            if service == SERVER_MODULE.OPENMAIC_ACCESS_SERVICE
            else original_secret(service)
        )
        try:
            login = self.request(
                "POST",
                "/auth/login",
                json.dumps({"password": "test-password-only"}),
                {"Content-Type": "application/json"},
            )
            cookie = login[1]["Set-Cookie"].split(";", 1)[0]
            response = self.request(
                "GET",
                "/launch/openmaic?next=%2F",
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

    def test_openmaic_routes_and_rendered_readme_are_live(self) -> None:
        login = self.request(
            "POST",
            "/auth/login",
            json.dumps({"password": "test-password-only"}),
            {"Content-Type": "application/json"},
        )
        cookie = login[1]["Set-Cookie"].split(";", 1)[0]
        page = self.request("GET", "/learn/openmaic", headers={"Cookie": cookie})
        alias = self.request("GET", "/learn/openmic", headers={"Cookie": cookie})
        readme = self.request("GET", "/projects/OpenMAIC/README-zh", headers={"Cookie": cookie})
        readme_legacy = self.request("GET", "/projects/OpenMAIC/README-zh.md", headers={"Cookie": cookie})
        changelog = self.request("GET", "/projects/OpenMAIC/CHANGELOG.md", headers={"Cookie": cookie})
        self.assertEqual(page[0], 200)
        self.assertIn("text/html", page[1]["Content-Type"])
        self.assertEqual(alias[0], 308)
        self.assertEqual(alias[1]["Location"], "/learn/openmaic")
        self.assertEqual(readme[0], 200)
        self.assertIn("text/html", readme[1]["Content-Type"])
        self.assertIn("OpenMAIC", readme[2].decode("utf-8"))
        self.assertIn("<h2", readme[2].decode("utf-8"))
        self.assertEqual(readme_legacy[0], 200)
        self.assertIn("text/html", readme_legacy[1]["Content-Type"])
        self.assertEqual(changelog[0], 200)
        self.assertIn("text/html", changelog[1]["Content-Type"])
        self.assertIn("返回课堂指南", changelog[2].decode("utf-8"))

    def test_deeptutor_readme_uses_its_own_title_and_nested_images(self) -> None:
        """DeepTutor ships its Chinese README under assets/README with paths
        relative to that directory.  Regression guard for the previously
        hardcoded OpenMAIC header and the unreachable ../../assets images."""
        page = self.request("GET", "/projects/DeepTutor/README-zh")
        self.assertEqual(page[0], 200)
        self.assertIn("text/html", page[1]["Content-Type"])
        body = page[2].decode("utf-8")
        self.assertIn("DeepTutor 中文项目说明", body)
        self.assertNotIn("OpenMAIC · 中文项目说明", body)
        self.assertIn("/projects/DeepTutor/assets/figs/logo/logo.png", body)

    def test_openmaic_job_history_is_redacted_and_live(self) -> None:
        response = self.request("GET", "/api/learning/openmaic-jobs")
        self.assertEqual(response[0], 200)
        payload = json.loads(response[2])
        self.assertIsInstance(payload.get("jobs"), list)
        for job in payload["jobs"]:
            self.assertNotIn("apiKey", job)
            self.assertIn("status", job)

    def test_openmaic_job_titles_come_from_the_classroom_not_a_placeholder(self) -> None:
        """The history page used to label every success "已保存的课堂", so a
        reader could not tell two classrooms apart. Titles are now read from the
        classroom's own stage.name, with a topic fallback for failed jobs."""
        response = self.request("GET", "/api/learning/openmaic-jobs")
        self.assertEqual(response[0], 200)
        jobs = json.loads(response[2])["jobs"]
        for job in jobs:
            self.assertIn("title", job)
            self.assertNotIn(job["title"], {"已保存的课堂", "OpenMAIC 生成任务"})
            # A generated classroom must surface its real course title.
            if job.get("classroomId"):
                self.assertTrue(job["title"].strip())
                self.assertNotIn(job["title"], {"未命名的生成任务"})

    def test_classroom_title_reader_handles_missing_files(self) -> None:
        self.assertEqual(SERVER_MODULE.openmaic_classroom_title(""), "")
        self.assertEqual(SERVER_MODULE.openmaic_classroom_title("no-such-id"), "")

    def test_job_topic_fallback_is_short_and_prefers_the_declared_topic(self) -> None:
        topic = SERVER_MODULE.openmaic_job_topic(
            {"inputSummary": {"requirementPreview": "请生成一堂课堂，主题是“缓存失效的三个原因”。还要别的内容。"}}
        )
        self.assertEqual(topic, "缓存失效的三个原因")
        self.assertLessEqual(len(topic), 60)
        # No declared topic: fall back to a truncated preview rather than "".
        self.assertTrue(SERVER_MODULE.openmaic_job_topic({"inputSummary": {"requirementPreview": "随便写点什么"}}))
        self.assertEqual(SERVER_MODULE.openmaic_job_topic({}), "")

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
                "/launch/openmaic?next="
                + quote("/?topic=RAG 从向量检索到重排的演进", safe=""),
            )
            self.assertEqual(response[0], 303)
            location = response[1]["Location"]
            self.assertTrue(location.startswith("http://"))
            self.assertIn("topic=RAG%20", location)
            self.assertNotRegex(location, r"[^\x00-\x7f]")
        finally:
            SERVER_MODULE.is_local_client = original_local
            SERVER_MODULE.read_keychain_secret = original_secret


class KnowledgeGraphTests(unittest.TestCase):
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
        """Every wikilink a reader can click must resolve.

        Fenced code blocks are excluded on purpose: they hold templates and
        worked examples (`[[相关页面1]]`, a hypothetical `[[KV缓存原理]]`), and
        those are meant to be illustrative rather than navigable. Counting them
        made this test fail for 60 links that were genuinely broken plus 9 that
        were never links at all, which hid the real breakage.
        """
        fence_re = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
        unresolved: list[str] = []
        for relative, note in self.vault.notes.items():
            prose = fence_re.sub("", str(note["body"]))
            for target, _label in SERVER_MODULE.WIKILINK_RE.findall(prose):
                if not self.vault.resolve_note(target, relative):
                    unresolved.append(f"{relative} -> {target}")
        self.assertEqual(unresolved, [])

    def test_knowledge_management_is_flagged_out_of_graph(self) -> None:
        """知识库管理 holds maintenance material, not engineering knowledge.
        It must be marked so the graph and the reader's 入链/延伸 rails skip it.

        This asserts the flag is derived from `category`, not only from the
        frontmatter key, so a new page added under that folder inherits the
        exclusion without its author remembering to add `exclude_from_graph`.
        """
        management = [
            note for note in self.vault.notes.values() if note["category"] == "知识库管理"
        ]
        self.assertTrue(management, "expected 知识库管理 notes to exist")
        unflagged = [str(note["path"]) for note in management if not note["exclude_from_graph"]]
        self.assertEqual(unflagged, [])

    def test_knowledge_management_keeps_one_core_article(self) -> None:
        """知识库管理 is a maintenance log, not a knowledge category. If pages
        pile up in its root, the sidebar count inflates and the directory fills
        with upkeep notes. The 2026-09-17 cleanup moved 28 pages into 归档/;
        this keeps a future page from quietly landing back in the root."""
        root = ROOT / "vault" / "知识库管理"
        stray = sorted(
            path.name
            for path in root.glob("*.md")
            if path.name != "知识库管理.md"
        )
        self.assertEqual(
            stray,
            [],
            "知识库管理 根目录只应有 知识库管理.md，其它内容应放入 归档/",
        )

    def test_knowledge_management_pages_are_still_readable(self) -> None:
        """Excluded from the graph is not the same as hidden. The pages stay
        listed and servable — only their graph participation is dropped."""
        management = [
            note for note in self.vault.notes.values() if note["category"] == "知识库管理"
        ]
        unlisted = [str(note["path"]) for note in management if not note["listed"]]
        self.assertEqual(unlisted, [])
        self.assertIsNotNone(self.vault.note("知识库管理/知识库管理.md"))

    def test_public_notes_payload_has_no_edges_into_knowledge_management(self) -> None:
        """The graph is filtered on the server so every renderer inherits it.
        Before, each renderer filtered separately and the reader's relation
        rails had no check at all, leaking 知识库管理 links into the graph."""
        handler_source = (ROOT / "site" / "server.py").read_text(encoding="utf-8")
        self.assertIn('self.vault.notes.values()', handler_source)
        self.assertIn('"exclude_from_graph"', handler_source)

        notes = [
            note
            for note in self.vault.notes.values()
            if note["listed"] and not note["exclude_from_graph"]
        ]
        graph_paths = {str(note["path"]) for note in notes}
        edges = [
            edge
            for edge in self.vault.edges()
            if edge["source"] in graph_paths and edge["target"] in graph_paths
        ]
        leaked = [
            edge
            for edge in edges
            if str(edge["source"]).startswith("知识库管理")
            or str(edge["target"]).startswith("知识库管理")
        ]
        self.assertEqual(leaked, [])
        self.assertGreater(len(edges), 0, "filtering should not remove every edge")

    def test_knowledge_management_split_keeps_methods_out_of_archive(self) -> None:
        """The category was one grab-bag page mixing structure, update process,
        quality rules and tool costs. It is now an entry page plus a 方法 folder;
        the split has to actually be reachable, not just written on disk."""
        # The point is that method documents live in 方法/ and are reachable,
        # not that the folder holds exactly two of them. Pinning the list meant
        # every new document failed the test, which trains you to edit the
        # assertion instead of reading it — the test stops being a signal.
        methods = sorted((ROOT / "vault" / "知识库管理" / "方法").glob("*.md"))
        self.assertGreaterEqual(len(methods), 2, "the methods folder must not be empty")
        for required in ("知识从哪来怎么更新", "一篇知识怎么写"):
            self.assertIn(
                required,
                [path.stem for path in methods],
                f"{required} must stay in 方法/",
            )
        topics = {
            str(note["topic"])
            for note in self.vault.notes.values()
            if str(note["path"]).startswith("知识库管理/方法/")
        }
        self.assertEqual(topics, {"方法"}, "方法 目录必须成为一个独立 topic")
        # 提出来的两篇同样不入图谱（按 category 判定，应自动继承）
        for note in self.vault.notes.values():
            if str(note["path"]).startswith("知识库管理/方法/"):
                self.assertTrue(note["exclude_from_graph"], f"{note['path']} 应排除出图谱")

    def test_feedback_storage_is_gitignored(self) -> None:
        """Feedback is visitor data, not knowledge. If data/ ever became
        tracked, every reader's IP and comment would be committed."""
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "data/feedback.jsonl"],
            cwd=ROOT,
            capture_output=True,
        )
        self.assertEqual(ignored.returncode, 0, "data/ 必须在 .gitignore 中")

    def test_feedback_record_shape_is_safe(self) -> None:
        """The stored record must not leak the password or contain fields the
        insights page cannot render."""
        server = SERVER_MODULE
        record = {
            "ts": time.time(),
            "kind": "bug",
            "message": "x",
            "path": "知识库管理/知识库管理.md",
            "title": "知识库管理",
            "contact": "",
            "status": "open",
            "ip": "127.0.0.1",
            "host_kind": "local",
            "agent": "Chrome 142",
            "name": "tester",
            "name_source": "manual",
        }
        with tempfile.TemporaryDirectory() as tmp:
            original = server.DATA_HOME
            server.DATA_HOME = Path(tmp)
            try:
                self.assertTrue(server._append_jsonl(Path(tmp) / "f.jsonl", record))
                back = server._read_jsonl(Path(tmp) / "f.jsonl")
                self.assertEqual(len(back), 1)
                self.assertEqual(back[0]["kind"], "bug")
                self.assertNotIn("password", json.dumps(back[0], ensure_ascii=False))
            finally:
                server.DATA_HOME = original

    def test_wecom_key_never_lives_in_tracked_files(self) -> None:
        """The group-bot key is a credential. It belongs in the Keychain, and
        nothing that can be committed may contain it."""
        server_source = (ROOT / "site" / "server.py").read_text(encoding="utf-8")
        self.assertIn("WECOM_SERVICE", server_source)
        self.assertIn("read_keychain_secret(WECOM_SERVICE)", server_source)
        # key=... 不应作为字面量出现在任何会被提交的文件里
        for relative in ("site/server.py", "index.html", "site/shell.js", "site/insights.html"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotRegex(
                text,
                r"webhook/send\?key=[0-9a-f]{8}-",
                f"{relative} 不应内嵌 webhook key",
            )

    def test_describe_agent_reads_common_browsers(self) -> None:
        cases = [
            ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36", "Chrome 142"),
            ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Safari 18"),
        ]
        for ua, expected in cases:
            self.assertIn(expected, SERVER_MODULE.describe_agent(ua))

    def test_parallel_skill_categories_are_integrated_into_domains(self) -> None:
        categories = {str(note["category"]) for note in self.vault.notes.values()}
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Agent技能", categories)
        self.assertNotIn("后端技能", categories)
        self.assertFalse((ROOT / "vault" / "Agent技能").exists())
        self.assertFalse((ROOT / "vault" / "后端技能").exists())
        self.assertIn('id="reader-relations"', home)
        self.assertIn("function renderRelations", home)
        self.assertNotIn("后端技能", home)
        self.assertNotIn("Agent技能", home)
        self.assertNotIn("skillTracks", home)
        self.assertNotIn("能力线", home)

    def test_no_note_repeats_a_heading_or_lead(self) -> None:
        """Editing a page by adding a section has twice left the old section in
        place, producing a page that repeats itself. The shape test only checks
        that the required headings exist, so it passes while the prose is
        duplicated. This catches the duplication directly."""
        for relative, note in self.vault.notes.items():
            body = str(note["body"])
            # Subsections legitimately reuse names under different parents
            # ("三种解法" appears once per failure mode), so only compare
            # headings against siblings at the same level.
            repeated: list[str] = []
            current_parent: tuple[int, str] | None = None
            seen: set[str] = set()
            for level, heading in re.findall(r"^(#{2,3}) (.+)$", body, re.M):
                depth = len(level)
                if depth == 2:
                    current_parent, seen = heading, set()
                elif current_parent is not None:
                    if heading in seen:
                        repeated.append(f"{current_parent} > {heading}")
                    seen.add(heading)
            self.assertEqual(
                repeated, [], f"{relative} repeats headings: {repeated}"
            )
            # The lead paragraph should not also appear under a heading.
            lead = next(
                (p.strip() for p in re.split(r"\n\n", body) if p.strip()), ""
            )
            if len(lead) > 80:
                self.assertEqual(
                    body.count(lead[:80]),
                    1,
                    f"{relative} repeats its opening paragraph",
                )

    def test_sidebar_domains_have_independent_expand_state(self) -> None:
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("expandedDomains:new Set()", home)
        self.assertIn('aria-expanded="${open}"', home)
        self.assertIn("state.expandedDomains.delete(domain)", home)
        self.assertIn("state.expandedDomains.add(domain)", home)
        self.assertIn("#tk-sidebar.collapsed #domains", home)

    def test_every_core_note_has_an_incoming_link(self) -> None:
        linked = {edge["target"] for edge in self.vault.edges()}
        orphans = [
            str(note["path"])
            for note in self.vault.notes.values()
            if str(note["path"]).startswith("工程知识/") and note["path"] not in linked
        ]
        self.assertEqual(orphans, [])

    def test_durable_pages_explain_the_causal_contract(self) -> None:
        failures = QUALITY_MODULE.audit(ROOT)
        self.assertEqual(failures, [])

    def test_editorial_inventory_covers_all_durable_pages(self) -> None:
        rows = INVENTORY_MODULE.inventory(ROOT)
        expected = len(list((ROOT / "vault" / "工程知识").rglob("*.md")))
        self.assertEqual(len(rows), expected)
        durable = [row for row in rows if row["durable"]]
        self.assertGreater(len(durable), 100)
        self.assertTrue(all(row["round1"] == "通过" for row in durable))
        self.assertTrue(all(row["round2"] == "待复核" for row in durable))

    def test_second_pass_has_no_structural_findings(self) -> None:
        result = REVIEW_MODULE.review(ROOT)
        self.assertEqual(result["findings"], [])


class NavigationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.home = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.projects = (ROOT / "projects" / "index.html").read_text(encoding="utf-8")
        cls.evaluation = (ROOT / "apps" / "agent-evaluation" / "index.html").read_text(encoding="utf-8")
        cls.learning = (ROOT / "apps" / "learning" / "index.html").read_text(encoding="utf-8")
        cls.openmaic = (ROOT / "apps" / "learning" / "openmaic.html").read_text(encoding="utf-8")
        cls.intuition = (ROOT / "apps" / "learning" / "intuition.html").read_text(encoding="utf-8")
        cls.transfer = (ROOT / "apps" / "learning" / "transfer.html").read_text(encoding="utf-8")
        cls.history = (ROOT / "apps" / "learning" / "history.html").read_text(encoding="utf-8")

    def test_home_has_one_graph_entry_and_hides_legacy_overview_domain(self) -> None:
        self.assertEqual(self.home.count('id="home-graph"'), 1)
        self.assertIn('id="app-alert"', self.home)
        self.assertIn('id="reader-back"', self.home)
        self.assertIn('id="reader-study"', self.home)
        self.assertIn("/learn?topic=", self.home)
        self.assertIn('data-tooltip="进入学习中心', self.home)
        self.assertIn("function updateReaderStudy()", self.home)
        self.assertIn("alertUser('这篇笔记暂时无法打开", self.home)
        self.assertIn("状态未知", self.home)
        self.assertIn("学习工具状态暂时不可用", self.home)
        self.assertIn("setMobileSidebar(matchMedia('(max-width:760px)').matches)", self.home)
        self.assertIn("filter(d=>d!=='总览'&&d!=='Clippings')", self.home)
        self.assertIn("domain==='总览'||topic==='首页'", self.home)
        self.assertIn("history.replaceState({},'','/')", self.home)

    def test_graph_has_quiet_labels_and_keyboard_contract(self) -> None:
        self.assertIn('.node:hover text,.node:focus text,.node:focus-within text', self.home)
        self.assertIn("tabindex:'0',role:'button','aria-label':n.title", self.home)
        self.assertIn("aria-selected=\"true\"", self.home)
        self.assertIn('tabindex="0" role="button" aria-label="打开 ${esc(d)}"', self.home)
        self.assertIn("['Enter',' '].includes(event.key)", self.home)
        self.assertIn("aria-expanded", self.home)
        self.assertIn("收起目录", self.home)
        self.assertIn("item.setAttribute('aria-selected',String(item===button))", self.home)

    def test_home_uses_one_render_and_refresh_path(self) -> None:
        for legacy_patch in (
            "renderHomeBase",
            "originalOpenNote",
            "originalLoadHome",
            "originalRenderHome",
            "new MutationObserver",
        ):
            self.assertNotIn(legacy_patch, self.home)
        self.assertEqual(self.home.count("setInterval("), 1)
        self.assertEqual(self.home.count("json('/api/learning/status')"), 1)
        self.assertIn("function dataSignature(data)", self.home)
        self.assertIn("if(signature===state.notesSignature)return", self.home)

    def test_server_has_one_homepage_source(self) -> None:
        server = (ROOT / "site" / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("INDEX_HTML =", server)
        self.assertNotIn("MODERN_INDEX_HTML =", server)
        self.assertIn("payload = PUBLIC_SITE.read_bytes()", server)

    def test_project_priority_is_consistent(self) -> None:
        positions = [
            self.projects.index(f"<h3>{name}</h3>")
            for name in ("OpenMAIC", "DeepTutor", "Matt Skills", "Archify")
        ]
        self.assertEqual(positions, sorted(positions))

    def test_agent_evaluation_is_labeled_as_self_built_and_incomplete(self) -> None:
        self.assertIn("自研 Agent 评估", self.home)
        self.assertIn("自研 Agent 评估", self.projects)
        self.assertIn("自研 Agent 评估", self.evaluation)
        self.assertIn("真实执行、Trace 接入和证据投影待开发", self.home)
        self.assertIn("尚未接入真实仓库执行", self.evaluation)

    def test_learning_center_has_real_launch_contracts(self) -> None:
        self.assertIn('href="/learn"', self.home)
        self.assertIn("/launch/openmaic", self.home)
        self.assertIn("/launch/deeptutor", self.home)
        self.assertIn("/launch/openmaic", self.projects)
        self.assertIn("/launch/deeptutor", self.projects)
        self.assertNotIn("教学入口：本机 3782 端口，先登录", self.projects)
        self.assertIn("教学入口：本机 3782", " ".join(self.projects.split()))
        self.assertIn("自动建立会话", self.projects)
        self.assertIn("/api/learning/status", self.learning)
        self.assertIn("RAG：从一次检索到有状态证据系统", self.learning)
        self.assertIn("生成前始终由你确认", self.learning)
        self.assertIn('new URLSearchParams(location.search).get("topic")', self.learning)
        compact_learning = " ".join(self.learning.split())
        self.assertIn('id="open-classroom" href="/launch/openmaic?next=%2F"', compact_learning)
        self.assertIn('id="open-tutor" href="/launch/deeptutor?next=%2Fchat"', compact_learning)
        self.assertIn('/launch/openmaic?next=%2Fclassroom%2FxzijlWOptW', self.learning)
        self.assertIn('function bindActionLaunch(link, kind)', self.learning)
        self.assertNotIn('bindActionGuide(link, "/learn/intuition")', self.learning)
        self.assertNotIn('bindActionGuide(link, "/learn/transfer")', self.learning)
        self.assertIn('window.open(url, "_blank")', self.learning)
        self.assertNotIn('window.location.href = url', self.learning)
        self.assertNotIn("location.href='/learn'", self.home)
        # The homepage renders the same four primary destinations as every
        # companion page. These links stay in the current tab.
        self.assertIn('id="tk-sidebar"', self.home)
        self.assertIn("renderSharedNav", self.home)
        self.assertIn("知识图谱", self.home)
        self.assertNotIn('id="home-button"', self.home)
        self.assertNotIn('id="graph-button"', self.home)
        # The knowledge tree and Clippings must survive the nav change.
        # 域树挂载点由 renderSharedNav() 插进 shell 渲染出的侧边栏里。
        self.assertIn("domains.id='domains'", self.home)
        self.assertIn('aside.querySelector(\'.tk-nav\')?.after(domains)', self.home)
        self.assertIn(
            'href="/learn" target="_blank" rel="noopener noreferrer" style=', self.home
        )
        self.assertIn("refreshLearningStatus", self.home)
        self.assertIn("refreshNotes", self.home)
        self.assertIn('href="/learn/openmaic"', self.home)
        self.assertIn('id="home-history"', self.home)
        self.assertNotIn("window.open('/projects', '_blank')", self.home)
        self.assertIn("/launch/openmaic", self.home)
        self.assertIn("/launch/deeptutor", self.home)
        self.assertNotIn("http://${host}:3100", self.home)
        self.assertNotIn("http://${host}:3782", self.home)
        self.assertIn("/learn/history", self.learning)
        # The page leads with the classroom list; the explanation is secondary.
        self.assertIn("我的课堂", self.history)
        self.assertIn("生成过的课堂", self.history)
        self.assertIn("复核后收录", self.history)
        self.assertIn("/api/learning/openmaic-jobs", self.history)
        # Returning learners must be able to find their classrooms from the
        # learning centre without hunting: the link sits in the hero next to
        # the topic form, not buried in body copy.
        self.assertIn("打开我的课堂", self.learning)
        self.assertIn('class="topic-secondary"', self.learning)
        self.assertNotIn("history-link", self.learning)
        # Failed jobs explain themselves; the card title is the classroom's own
        # course name rather than a fixed placeholder.
        self.assertIn("生成未完成", self.history)
        self.assertIn("job.title", self.history)
        self.assertNotIn("已保存的课堂", self.history)
        for page in (self.intuition, self.transfer):
            self.assertIn('/static/base.css', page)
            self.assertIn('page: "learning"', page)
        # The classroom page is its own sidebar destination, so it highlights
        # 我的课堂 rather than 学习中心.
        self.assertIn('/static/base.css', self.history)
        self.assertIn('page: "classrooms"', self.history)
        self.assertIn("形成直觉", self.intuition)
        self.assertIn("迁移验证", self.transfer)

    def test_openmaic_teaching_page_has_complete_entry_contract(self) -> None:
        self.assertIn('page: "learning"', self.openmaic)
        self.assertIn('/launch/openmaic?next=', self.openmaic)
        self.assertIn('target="_blank" rel="noopener noreferrer"', self.openmaic)
        self.assertIn('id="topic"', self.openmaic)
        self.assertIn('data-topic=', self.openmaic)
        self.assertIn("请输入访问码", self.openmaic)
        self.assertIn("手动访问端口", self.openmaic)
        self.assertIn("/api/learning/status", self.openmaic)
        self.assertIn("问题与目的", self.openmaic)
        self.assertIn("本质与机制", self.openmaic)
        self.assertIn("迁移与验证", self.openmaic)
        self.assertIn("RAG 前沿知识", self.openmaic)
        self.assertIn('href="/projects/OpenMAIC/README-zh"', self.openmaic)
        self.assertIn("缓存有效性与失效边界", self.openmaic)
        self.assertIn('/launch/openmaic?next=%2Fclassroom%2FxzijlWOptW', self.openmaic)

    def test_project_page_uses_live_service_status_asset(self) -> None:
        projects = (ROOT / "projects" / "index.html").read_text(encoding="utf-8")
        status_asset = (ROOT / "site" / "project-status.js").read_text(encoding="utf-8")
        self.assertIn('/static/project-status.js', projects)
        self.assertIn("/api/learning/status", status_asset)
        self.assertIn("状态未知", status_asset)

    def test_companion_pages_share_workbench_navigation(self) -> None:
        """Every page kind renders its sidebar from the same place.

        This used to assert that workbench.js contained a literal `const nav = [`
        array. That tested how the code was written rather than what it did, and
        it broke the moment the array moved to nav.js. Now it reads the data and
        the one renderer, which is what actually has to hold.
        """
        shared = (ROOT / "site" / "base.css").read_text(encoding="utf-8")
        shell = (ROOT / "site" / "shell.js").read_text(encoding="utf-8")
        nav_items = parse_nav_items()

        # One renderer, one set of class names.
        self.assertIn(".tk-sidebar", shared)
        self.assertIn(".tk-nav a", shared)
        self.assertIn("sidebar", shell)
        self.assertNotIn("dataset.page", shell)
        # No wb-* selectors or class names survive. The bare string appears in a
        # comment explaining that the prefix was retired, so look for actual uses:
        # a CSS selector, or a class attribute / className assignment.
        for text, name in ((shared, "base.css"), (shell, "shell.js")):
            self.assertNotRegex(text, r"\.wb-[a-z]", f"{name} still has a .wb- selector")
            self.assertNotRegex(text, r'class="[^"]*\bwb-', f"{name} still has a wb- class")
            self.assertNotRegex(text, r'wb-host', f"{name} still references wb-host")

        keys = [item["key"] for item in nav_items]
        # 中台 (/insights) 在数据里，但标了 localOnly：它列出访客 IP 和反馈内容，
        # 只对本机开放，由 /api/access 决定是否渲染。别人浏览器里不该有。
        self.assertIn("insights", keys)
        local_only = {i["key"] for i in nav_items if i.get("localOnly")}
        self.assertEqual(local_only, {"insights"})
        for entry in ("knowledge", "graph", "projects", "evaluation"):
            self.assertIn(entry, keys)

        # The shell must withhold localOnly entries from the public list.
        self.assertIn("!i.localOnly", shell)

        self.assertNotIn('target="_blank" rel="noopener noreferrer"', shell)

        for page, name in ((self.learning, "learning"), (self.projects, "projects"), (self.evaluation, "evaluation"), (self.intuition, "learning"), (self.transfer, "learning"), (self.history, "classrooms")):
            self.assertIn('/static/base.css', page)
            self.assertIn(f'TKShell.sidebar({{', page)
            self.assertIn(f'page: "{name}"', page)
            self.assertIn('class="purpose"', page)

    def test_brand_and_knowledge_graph_are_shared_navigation(self) -> None:
        shared = (ROOT / "site" / "base.css").read_text(encoding="utf-8")
        shell = (ROOT / "site" / "shell.js").read_text(encoding="utf-8")
        brand = (ROOT / "site" / "brand.css").read_text(encoding="utf-8")
        home_nav = self.home.split("function renderSharedNav(){", 1)[1].split(
            "function updateSharedNav", 1
        )[0]

        self.assertIn('@import url("/static/brand.css")', shared)
        self.assertIn('href="/static/brand.css"', self.home)
        # The brand block is rendered by the shell on every page, so it is no
        # longer spelled out in index.html — that duplication was the point.
        self.assertIn('class="tk-brand"', shell)
        self.assertNotIn('class="tk-brand"', self.home)
        self.assertIn(".tk-brand-text strong", brand)
        self.assertIn("font-weight: 700", brand)
        self.assertNotIn("wb-brand-text strong", shared)
        # The sidebar is fixed and the page body reserves its width. The main
        # site used to do this with a grid column instead, so the two mechanisms
        # fought and .main rendered underneath the sidebar at x=0.
        # 只有一套机制：侧边栏 fixed，body 用 padding-left 让位。
        self.assertIn("padding-left: var(--sidebar-width)", shared)
        self.assertIn("width: var(--sidebar-width)", shared)
        self.assertNotIn("grid-template-columns:var(--sidebar-width)", self.home)
        self.assertIn('class="tk-host"', self.home)

        nav_items = parse_nav_items()
        self.assertIn("知识图谱", [i.get("label") for i in nav_items])
        self.assertNotIn("knowledge: [pages.graph]", shell)
        # 主站的图谱是页内视图，点击要拦截而不是跳转。
        self.assertIn("network:['知识图谱'", self.home)
        self.assertIn('aria-label="文章知识图谱"', self.home)
        self.assertIn("item.key==='graph'", home_nav)
        self.assertNotIn("sn-sub", home_nav)
        self.assertNotIn("关系图谱", self.projects)

        # Page rhythm now lives in base.css under the tk- names.
        self.assertIn("tk-shell", shared)
        self.assertIn(".tk-shell > .hero:first-child", shared)
        self.assertIn(".usage-grid .usage-item", shared)

    def test_navigation_stays_in_current_tab_and_links_have_no_default_underlines(self) -> None:
        home_nav = self.home.split("function renderSharedNav(){", 1)[1].split("function updateSharedNav", 1)[0]
        # The nav entries come from TKShell.sidebar() now, so the page names the
        # nav keys rather than spelling the labels out itself.
        labels = [i.get("label") for i in parse_nav_items()]
        self.assertIn("项目与教学", labels)
        self.assertIn("Agent 评估", labels)
        self.assertNotIn('target="_blank"', home_nav)

        shell = (ROOT / "site" / "shell.js").read_text(encoding="utf-8")
        self.assertNotIn('target="_blank"', shell)
        shared = (ROOT / "site" / "base.css").read_text(encoding="utf-8")
        self.assertIn("body.tk-host a:hover { text-decoration: none; }", shared)
        for page in (self.projects, self.evaluation, self.history, self.intuition, self.transfer, self.openmaic):
            self.assertNotIn("text-decoration: underline;", page)

    def test_my_classrooms_is_reachable_from_the_sidebar(self) -> None:
        """Returning to a generated classroom must not require knowing its URL.

        Learning pages nest under 项目与工具 rather than sitting in the main nav,
        because a classroom is a tool you reach for, not a second way to browse
        knowledge. They still have to be one click from that section.
        """
        items = parse_nav_items()
        by_key = {i["key"]: i for i in items}
        self.assertIn("classrooms", by_key)
        self.assertEqual(by_key["classrooms"]["label"], "我的课堂")
        self.assertEqual(by_key["classrooms"]["href"], "/learn/history")
        # 学习入口带 parent，所以只进二级导航，不进主导航。
        self.assertTrue(by_key["learning"].get("parent"))
        self.assertTrue(by_key["classrooms"].get("parent"))
        # 二级导航由 shell 渲染，挂在"项目与教学"下。
        shell = (ROOT / "site" / "shell.js").read_text(encoding="utf-8")
        self.assertIn("tk-subnav", shell)
        # 知识图谱 stays in the primary nav from every page; learning does not.
        primary = [i["key"] for i in items if not i.get("parent") and not i.get("localOnly")]
        self.assertIn("graph", primary)
        self.assertNotIn("learning", primary)
        self.assertNotIn("classrooms", primary)
        for page, name in ((self.learning, "learning"), (self.projects, "projects"),
                           (self.evaluation, "evaluation"), (self.history, "classrooms")):
            self.assertIn(f'page: "{name}"', page)

    def test_legacy_workbench_route_is_not_used_by_launch_contract(self) -> None:
        self.assertNotIn("/workbench/new", self.learning)
        self.assertIn("/launch/openmaic?next=", self.home)
        self.assertIn("/launch/openmaic?next=", self.projects)

    def test_login_return_path_is_same_origin(self) -> None:
        self.assertIn("target.origin===location.origin", SERVER_MODULE.LOGIN_HTML)
        self.assertIn("location.replace(safeNext)", SERVER_MODULE.LOGIN_HTML)


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
    """PaperNotes 索引：会议解析、去重、抓取脚本的形状。

    不联网。测的是脚本自己的逻辑，以及入库文件是否可读。
    """

    def test_parse_location_reads_venue_and_year(self) -> None:
        venue, conf = PAPERNOTES_MODULE.parse_location(
            "ICLR2026/llm_agent/a2flow_automating_agentic_workflow"
        )
        self.assertEqual(venue, "ICLR")
        self.assertEqual(conf, "ICLR 2026")

    def test_parse_location_accepts_digit_leading_subfield(self) -> None:
        """子领域可以是 `3d_vision` 这种数字打头的。

        第一版写的 [a-z_]+ 漏了它们，2101 条论文被判成「没有会议」——
        首屏因此少了一大块，而且不报错。
        """
        _, conf = PAPERNOTES_MODULE.parse_location(
            "AAAI2026/3d_vision/3d-anc_adaptive_neural_collapse"
        )
        self.assertEqual(conf, "AAAI 2026")

    def test_parse_location_accepts_url_encoded_slug(self) -> None:
        """标题里的重音符号和希腊字母是 URL 编码的（g%C3%B6del、vggt-%CF%89）。"""
        _, conf = PAPERNOTES_MODULE.parse_location(
            "ACL2025/llm_agent/g%C3%B6del_agent_a_self-referential"
        )
        self.assertEqual(conf, "ACL 2025")

    def test_parse_location_refuses_unlikely_year(self) -> None:
        """年份是唯一挡住非论文路径的东西 —— 标题段放宽到任意字符之后。"""
        self.assertEqual(PAPERNOTES_MODULE.parse_location("foo/bar"), ("", ""))
        self.assertEqual(PAPERNOTES_MODULE.parse_location("ICLR9999/x/y"), ("", ""))

    def test_normalise_title_folds_case_and_punctuation(self) -> None:
        a = PAPERNOTES_MODULE.normalise_title("Attention Is All You Need")
        b = PAPERNOTES_MODULE.normalise_title("attention is all you need!")
        self.assertEqual(a, b)

    def test_normalise_title_keeps_chinese(self) -> None:
        self.assertTrue(PAPERNOTES_MODULE.normalise_title("机器遗忘"))
        self.assertNotEqual(
            PAPERNOTES_MODULE.normalise_title("机器遗忘"),
            PAPERNOTES_MODULE.normalise_title("记忆"),
        )

    def test_build_drops_duplicate_titles(self) -> None:
        docs = [
            {"title": "Same Paper", "location": "ICLR2026/llm_agent/same_paper",
             "tags": ["LLM Agent"]},
            {"title": "Same Paper", "location": "ACL2026/llm_agent/same_paper",
             "tags": ["LLM Agent"]},
            {"title": "Other Paper", "location": "ICLR2026/llm_agent/other",
             "tags": []},
        ]
        index = PAPERNOTES_MODULE.build(docs)
        self.assertEqual(len(index["papers"]), 2)
        self.assertEqual(index["dropped"], 1)

    def test_build_skips_entries_without_title_or_location(self) -> None:
        index = PAPERNOTES_MODULE.build([
            {"title": "", "location": "ICLR2026/llm_agent/x"},
            {"title": "No location", "location": ""},
            {"title": "Good", "location": "ICLR2026/llm_agent/good"},
        ])
        self.assertEqual(len(index["papers"]), 1)
        self.assertEqual(index["dropped"], 2)

    def test_build_links_back_to_papernotes(self) -> None:
        index = PAPERNOTES_MODULE.build([
            {"title": "X", "location": "ICLR2026/llm_agent/x", "tags": []},
        ])
        self.assertEqual(index["papers"][0]["url"], "https://papernotes.org/ICLR2026/llm_agent/x/")

    def test_committed_index_is_readable(self) -> None:
        """入库的索引必须可读且形状对。这是 --check 的同一条保证。"""
        index = json.loads(PAPERNOTES_MODULE.INDEX.read_text(encoding="utf-8"))
        papers = index["papers"]
        self.assertGreater(len(papers), 20000)
        for paper in papers[:200]:
            self.assertTrue(paper["title"])
            self.assertTrue(paper["url"].startswith("https://papernotes.org/"))
            self.assertIsInstance(paper["tags"], list)

    def test_committed_index_has_recent_venues(self) -> None:
        """索引必须含 2025/2026 的会议。

        页面叫「追踪新论文」——如果抓来的数据全是几年前的，那这个页面
        就又变回它原来那个坏样子了。这条守着那个前提。
        """
        index = json.loads(PAPERNOTES_MODULE.INDEX.read_text(encoding="utf-8"))
        conferences = {p["conference"] for p in index["papers"] if p["conference"]}
        self.assertTrue(
            any("2026" in c for c in conferences),
            f"索引里没有 2026 的会议: {sorted(conferences)}",
        )
        self.assertTrue(any("2025" in c for c in conferences))

    def test_committed_index_covers_agent_and_memory_topics(self) -> None:
        """索引必须能支撑按方向筛选 —— 这是这一页主要的用法。"""
        index = json.loads(PAPERNOTES_MODULE.INDEX.read_text(encoding="utf-8"))
        all_tags = {t for p in index["papers"] for t in p["tags"]}
        for tag in ("LLM Agent", "RAG", "多智能体"):
            self.assertIn(tag, all_tags)


class FeedTests(unittest.TestCase):
    """外部源抓取：清洗、链接、编码、解析、失败隔离。

    这些测试**完全不碰网络** —— 外部站抖一下就让测试变红，那种测试没人会信。
    只测纯函数，以及在空缓存下返回结构的形状。
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
        """script/style 要连**内容**一起丢。

        只剥标签的话 `<script>alert(1)</script>` 会留下 `alert(1)` 这段文本，
        虽然不可执行，但会混进摘要里冒充正文。
        """
        result = FEEDS_MODULE.clean_text(
            "<script>alert('xss')</script><style>.a{color:red}</style><p>真正的正文</p>"
        )
        self.assertIn("真正的正文", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("color:red", result)

    def test_clean_text_strips_all_tags(self) -> None:
        result = FEEDS_MODULE.clean_text('<a href="x">链接文字</a><div>块级</div>')
        self.assertNotIn("<", result)
        self.assertIn("链接文字", result)
        self.assertIn("块级", result)

    def test_clean_text_survives_malformed_html(self) -> None:
        """畸形输入返回空串，不能抛 —— 一个坏页面不该让整个源失败。"""
        for bad in ("<p>未闭合", "</unopened>", "<a href='>'>", ""):
            self.assertIsInstance(FEEDS_MODULE.clean_text(bad), str)

    def test_clean_text_truncates(self) -> None:
        result = FEEDS_MODULE.clean_text("字" * 500, limit=50)
        self.assertLessEqual(len(result), 51)  # 50 + 省略号
        self.assertTrue(result.endswith("…"))

    def test_absolute_url_rewrites_relative(self) -> None:
        self.assertEqual(
            FEEDS_MODULE.absolute_url("/foo", "https://x.com/blog/"),
            "https://x.com/foo",
        )
        self.assertEqual(
            FEEDS_MODULE.absolute_url("a/b", "https://x.com/blog/"),
            "https://x.com/blog/a/b",
        )

    def test_absolute_url_rejects_dangerous_schemes(self) -> None:
        """协议白名单是必需的：urljoin 不拦 javascript:，原样进 href 就在本站执行。"""
        for bad in (
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:x",
            "file:///etc/passwd",
        ):
            self.assertEqual(FEEDS_MODULE.absolute_url(bad, "https://x.com/"), "", bad)

    def test_decode_body_prefers_declared_charset(self) -> None:
        raw = "中文内容".encode("gbk")
        self.assertEqual(FEEDS_MODULE.decode_body(raw, "text/html; charset=gbk"), "中文内容")

    def test_decode_body_falls_back_to_utf8(self) -> None:
        self.assertEqual(
            FEEDS_MODULE.decode_body("中文内容".encode("utf-8"), "text/html"), "中文内容"
        )

    def test_decode_body_never_raises_on_broken_bytes(self) -> None:
        self.assertIsInstance(FEEDS_MODULE.decode_body(b"\xff\xfe\x00bad", ""), str)

    def test_parse_rss(self) -> None:
        items, error = FEEDS_MODULE.parse_xml_feed(self.RSS_SAMPLE, "https://readhub.cn/rss")
        self.assertEqual(error, "")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "某公司发布某产品")
        self.assertEqual(items[0]["url"], "https://readhub.cn/topic/abc")
        self.assertIn("正文", items[0]["summary"])
        self.assertNotIn("<b>", items[0]["summary"])
        # 相对链接要补成绝对，否则点了会打到本站。
        self.assertEqual(items[1]["url"], "https://readhub.cn/topic/relative")

    def test_parse_atom_prefers_published_over_updated(self) -> None:
        """`updated` 是 feed 重新生成的时间，不是文章日期。

        实测阮一峰的 Atom 里 413 期和 411 期的 updated 都是今天，
        按 updated 排会出现 413、411、412 这种乱序。
        """
        items, error = FEEDS_MODULE.parse_xml_feed(self.ATOM_SAMPLE, "http://example.com/blog/atom.xml")
        self.assertEqual(error, "")
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["published"].startswith("2026-09-11"), items[0]["published"])

    def test_parse_xml_reports_bad_input(self) -> None:
        _, error = FEEDS_MODULE.parse_xml_feed("not xml at all", "https://x.com/")
        self.assertEqual(error, "parse_error")

    def test_html_parser_missing_container_reports_selector_missing(self) -> None:
        """选择器失效必须报错，不能当成「今天没更新」。

        抓到 200 但解不出条目时，代码是「成功」的，items 为空 ——
        如果报 empty，站方改版就会静默变成空列表，没人会去修。
        """
        items, error = FEEDS_MODULE.parse_arxivdaily("<html>完全不同的页面</html>", "https://x.com/")
        self.assertEqual(items, [])
        self.assertEqual(error, "selector_missing")

    def test_source_failure_does_not_break_others(self) -> None:
        """一个源抛异常，其余源必须照常返回。

        `_refresh_all()` 结尾会调 `_save_to_disk()` 把缓存写进
        data/feeds-cache.json。测试里必须把它换掉 —— 否则这个桩数据
        （`{"title": "t"}`）会覆盖真实缓存，页面上的「最新几条」就变成
        一个字母 `t`。这个坑犯过一次：写进真实缓存后，四个源的 feed
        全成了同一份假数据，而且每次跑测试都会再写一次。
        """
        original_fetch = FEEDS_MODULE.fetch_one
        original_save = FEEDS_MODULE._save_to_disk
        calls: list[str] = []

        def fake(source: dict) -> tuple[list[dict], str]:
            calls.append(source["key"])
            if source["key"] == "readhub":
                return [], "unreachable"
            return ([{"title": "t", "url": "https://x.com/a", "summary": "", "published": ""}], "")

        FEEDS_MODULE.fetch_one = fake
        FEEDS_MODULE._save_to_disk = lambda: None   # 不碰真实缓存文件
        try:
            FEEDS_MODULE._refresh_all()
        finally:
            FEEDS_MODULE.fetch_one = original_fetch
            FEEDS_MODULE._save_to_disk = original_save
            FEEDS_MODULE._CACHE.clear()

        self.assertIn("readhub", calls)
        # 每个源都被尝试过，没有因为第一个失败就中断。
        self.assertGreaterEqual(len(calls), 5)

    def test_snapshot_exposes_no_html_field(self) -> None:
        """守着一个安全属性：响应里不能有 HTML 字段。

        外部 HTML 一旦有字段承载，前端就得靠「记得转义」来兜；
        让它根本不存在，XSS 面就从源头没了。有人以后想加回原始字段时这条会红。
        """
        payload = FEEDS_MODULE.snapshot()
        # 白名单。新增字段必须同时改这里 —— 那道"要改测试"的门槛就是
        # 这条测试的全部作用：让加字段这件事必须被看到一次。
        #
        # 白名单里全是标量：字符串、数字。**不允许**出现承载 HTML 的键
        # （content / html / body / rendered 之类）。
        allowed = {
            "title", "url", "summary", "published",
            "cover", "source", "source_icon", "word_count", "read_minutes",
            "tags", "title_cn", "authors", "affiliations", "arxiv_id", "category",
        }
        forbidden = {"html", "content", "body", "rendered", "innerHTML"}
        for source in payload["sources"]:
            for item in source["items"]:
                self.assertTrue(
                    set(item) <= allowed,
                    f"{source['key']} 的条目出现了越界字段: {set(item) - allowed}",
                )
                # 即便有人把 forbidden 里的名字加进白名单，这条也会红。
                self.assertFalse(
                    set(item) & forbidden,
                    f"{source['key']} 的条目带了 HTML 承载字段: {set(item) & forbidden}",
                )
                # tags 必须是字符串数组 —— 不接受对象或嵌套结构，
                # 那会重新打开"通过字段传结构化内容"的口子。
                # 这几个也必须是字符串或字符串数组 —— 不接受对象或嵌套结构。
                for key in ("tags", "affiliations"):
                    if key in item:
                        self.assertIsInstance(item[key], list)
                        for entry in item[key]:
                            self.assertIsInstance(entry, str)
                for key in ("title_cn", "authors", "arxiv_id", "category"):
                    if key in item:
                        self.assertIsInstance(item[key], str)

    def test_snapshot_includes_bestblogs(self) -> None:
        """BestBlogs 必须在响应里出现。

        它以前走页面抓取（JS 渲染 + 要登录，抓不到），所以标 unavailable。
        现在走它自己的 OpenAPI，是正常的源 —— 但这条测试守的东西没变：
        源列表里必须有它，不能因为抓取方式换过就从 FEEDS 里漏掉。
        """
        payload = FEEDS_MODULE.snapshot()
        keys = {source["key"] for source in payload["sources"]}
        self.assertIn("bestblogs", keys)

    def test_snapshot_covers_every_declared_source(self) -> None:
        payload = FEEDS_MODULE.snapshot()
        self.assertEqual(
            {s["key"] for s in payload["sources"]},
            {s["key"] for s in FEEDS_MODULE.FEEDS},
        )

    def test_feeds_declare_a_known_kind(self) -> None:
        for source in FEEDS_MODULE.FEEDS:
            # api = 走对方提供的开放接口，而不是抓页面（bestblogs 用这个）。
            self.assertIn(source["kind"], {"rss", "atom", "html", "api", "none"}, source["key"])
            self.assertTrue(source["url"].startswith("https://"), source["key"])
            self.assertIn("ttl", source)


if __name__ == "__main__":
    unittest.main()


    def test_homepage_samples_across_days(self) -> None:
        """首页的条目要跨天交替，不能全落在最新那一天。

        数据是"近三天"的，按发布时间倒序。直接取前 N 条的话，最新一天条数
        够多就会占满名额 —— 首页 12 张卡全是同一天的，"近三天"这个标题就
        不成立了。所以服务端按天轮流抽。
        """
        items = (
            [{"published": "2026-09-18", "title": f"a{i}"} for i in range(10)]
            + [{"published": "2026-09-17", "title": f"b{i}"} for i in range(8)]
            + [{"published": "2026-09-16", "title": f"c{i}"} for i in range(2)]
        )
        out = SERVER_MODULE._interleave_by_day(items, 6)
        self.assertEqual(len(out), 6)
        days = [i["published"] for i in out]
        self.assertEqual(days[0], "2026-09-18", "最新的排最前")
        self.assertEqual(len(set(days)), 3, "六条应当覆盖全部三天")
        # 顺序是轮流来，不是按天分块
        self.assertNotEqual(days, sorted(days, reverse=True))

    def test_interleave_handles_missing_days(self) -> None:
        """某天没内容时不能卡住或重复。"""
        items = [{"published": "2026-09-18", "title": f"a{i}"} for i in range(3)]
        out = SERVER_MODULE._interleave_by_day(items, 10)
        self.assertEqual(len(out), 3, "只有 3 条就返回 3 条，不补空")
        self.assertEqual(SERVER_MODULE._interleave_by_day(items, 0), [])
        self.assertEqual(SERVER_MODULE._interleave_by_day([], 5), [])

BESTBLOGS_SPEC = importlib.util.spec_from_file_location(
    "knowledge_site_bestblogs", ROOT / "site" / "bestblogs.py"
)
BESTBLOGS_MODULE = importlib.util.module_from_spec(BESTBLOGS_SPEC)
assert BESTBLOGS_SPEC.loader is not None
BESTBLOGS_SPEC.loader.exec_module(BESTBLOGS_MODULE)


class BestBlogsRequestTests(unittest.TestCase):
    """BestBlogs 的请求参数必须和文档一致。

    这类 bug 的代价在于**它是静默的**：服务端对无效取值不报错，直接忽略，
    于是返回的是默认排序的旧内容 —— 表面看"接口通了、有数据"，实际拿到的
    是错的数据。

    实测踩过：type=ARTICLE 和 language=zh_CN 都是无效值（文档规定小写
    article、zh/en/all）。两者都被忽略，结果那批数据多数是 2024-2025 的，
    看起来就像"这个 API 捞不到新文章"，而真正的原因是参数从没生效过。
    排查时试遍了排序和时间窗参数，方向完全错了。

    所以这里用假的请求函数把**实际发出的参数**截下来断言，不打网络。
    """

    def setUp(self) -> None:
        if not BESTBLOGS_MODULE.api_key():
            self.skipTest("未配置 bestblogs.key")
        self.calls: list[tuple[str, dict]] = []
        self._orig_get = BESTBLOGS_MODULE._get
        self._orig_save = BESTBLOGS_MODULE._save_cache
        self._orig_save_brief = BESTBLOGS_MODULE._save_brief_cache
        # 不打网络，也不写盘。
        BESTBLOGS_MODULE._save_cache = lambda: None
        BESTBLOGS_MODULE._save_brief_cache = lambda: None
        self.respond_with([], "")

    def respond_with(self, data: object, error: str) -> None:
        """让下一次请求返回指定的结果，同时照旧记录调用参数。

        注入错误时必须走这里，不能自己写 lambda —— 那样就绕过了 self.calls
        的记录，测试会看到"0 次调用"而误报。这个坑踩过。
        """
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
                             "type 必须是小写 article；大写 ARTICLE 是无效值，会被静默忽略")
            self.assertEqual(params.get("language"), "zh",
                             "language 必须是 zh/en/all；zh_CN 是无效值，会被静默忽略")

    def test_resources_sends_a_time_window(self) -> None:
        """time 必须是文档列的取值之一，否则同样被忽略。"""
        allowed = {"24h", "3d", "1w", "1m", "all"}
        BESTBLOGS_MODULE.digest(limit=3, force=True)
        calls = [c for c in self.calls if c[0] == "resources"]
        self.assertTrue(calls)
        for _, params in calls:
            self.assertIn(params.get("time"), allowed)

    def test_brief_uses_the_briefs_public_path(self) -> None:
        """早报走 /openapi/v2/briefs/public/<date>。

        文档把它写成 `GET /openapi/v2/brief` 加 `date` 查询参数 —— 那个是
        404。真实路径多一层 `briefs/public/`，日期在路径段里。都试过：

            briefs/public/today          ✅ 200
            briefs/public/2026-09-19     ✅ 200（历史日期也能取）
            briefs/public?date=...       ❌ 404
            brief?date=...&language=zh   ❌ 404
            briefs/public/yesterday      ❌ 400（只认 ISO 日期或 today）

        断言实际请求的 path，免得谁"照文档改回去"。
        """
        self.respond_with({"contentItems": []}, "")
        BESTBLOGS_MODULE.brief(force=True)
        paths = [c[0] for c in self.calls]
        self.assertTrue(paths, "应当请求过早报端点")
        for path in paths:
            self.assertTrue(path.startswith("briefs/public/"),
                            f"{path} 不在 briefs/public/ 下（文档里的 /brief 是 404）")
            tail = path.split("/")[-1]
            self.assertTrue(
                tail == "today" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", tail),
                f"{path} 的最后一段既不是 today 也不是 ISO 日期",
            )

    def test_brief_covers_three_days(self) -> None:
        """早报要覆盖近几天，不是只取今天。

        只取今天的话，今天没更新（或周日没有早报）时整块就是空的。
        """
        self.respond_with({"contentItems": []}, "")
        BESTBLOGS_MODULE.brief(force=True)
        days = [c[1] for c in self.calls if c[0].startswith("briefs/public/")]
        self.assertGreaterEqual(len(days), 2, "应当请求多天的早报")

    def test_brief_fetches_details_by_batch(self) -> None:
        """早报候选只有 id，完整字段要再批量取一次。

        候选里没有发布日期，而页面要按时间排、要显示日期 —— 所以这次
        补取不是可选的。用两次调用换全部字段，比翻四页精选省。
        """
        self.respond_with(
            {"candidates": [{"resourceId": "RAW_a"}, {"resourceId": "RAW_b"}]}, ""
        )
        # 第二次（batch-meta）返回两条完整记录
        original = BESTBLOGS_MODULE._batch_meta
        seen: list[list[str]] = []

        def fake_batch(ids: list[str]) -> list[dict]:
            seen.append(list(ids))
            return [
                {"id": "RAW_a", "title": "甲", "readUrl": "https://x.test/a",
                 "publishDateTimeStr": "2026-09-19 10:00:00",
                 "publishTimeStamp": 1789794000000},
                {"id": "RAW_b", "title": "乙", "readUrl": "https://x.test/b",
                 "publishDateTimeStr": "2026-09-18 10:00:00",
                 "publishTimeStamp": 1789707600000},
            ]

        BESTBLOGS_MODULE._batch_meta = fake_batch
        try:
            result = BESTBLOGS_MODULE.brief(force=True)
        finally:
            BESTBLOGS_MODULE._batch_meta = original
        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(len(result.get("items") or []), 2)
        self.assertEqual(seen, [["RAW_a", "RAW_b"]], "应当把候选 id 一次批量传过去")
        # 按发布时间倒序
        self.assertEqual([i["title"] for i in result["items"]], ["甲", "乙"])

    def test_a_failed_fetch_is_not_cached_for_a_whole_day(self) -> None:
        """抓失败只能锁一小段时间，不能锁一天。

        这是两个不同的判断，第一版把它们混成了一个：

          · 那天确实没有内容  → 结果稳定，锁一天没问题
          · 配额耗尽 / 网络不通 → 暂时的，恢复后该立刻能抓到

        混在一起的后果：配额中午恢复，页面却要空到第二天。缓存把"这次没
        抓到"当成了"确认没有"。

        digest 和 brief 两条路径都要守 —— 修完 digest 才发现 brief 同样有
        这个问题。
        """
        retry = float(BESTBLOGS_MODULE._RETRY_TTL)
        day = float(BESTBLOGS_MODULE._CACHE_TTL)
        self.assertLess(retry, day, "失败的重试间隔必须短于成功的缓存时长")

        # 让请求返回配额错误，看缓存里写的 ttl 是哪一档。
        self.respond_with(None, "quota")

        digest_cache_backup = dict(BESTBLOGS_MODULE._CACHE)
        BESTBLOGS_MODULE._CACHE.clear()
        BESTBLOGS_MODULE._CACHE.update({"at": 0.0, "items": [], "status": "unknown", "ttl": 0.0})
        result = BESTBLOGS_MODULE.digest(limit=3, force=True)
        self.assertEqual(result.get("status"), "quota")
        self.assertLessEqual(
            float(BESTBLOGS_MODULE._CACHE.get("ttl") or 0), retry,
            "配额耗尽后写入的 ttl 必须是短档，否则要等一天才会重试",
        )
        BESTBLOGS_MODULE._CACHE.clear()
        BESTBLOGS_MODULE._CACHE.update(digest_cache_backup)

        brief_cache_backup = dict(BESTBLOGS_MODULE._brief_cache)
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update({"at": 0.0, "payload": {}, "ttl": 0.0})
        result = BESTBLOGS_MODULE.brief(force=True)
        # 报真实原因（quota），不要谎报成"没有内容" —— 这两件事在页面上
        # 是不同的提示，混淆会让人往错的方向排查。这条断言踩过一次。
        self.assertEqual(result.get("status"), "quota")
        self.assertLessEqual(
            float(BESTBLOGS_MODULE._brief_cache.get("ttl") or 0), retry,
            "早报抓失败后写入的 ttl 也必须是短档",
        )
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update(brief_cache_backup)

    def test_a_successful_fetch_is_cached_long(self) -> None:
        """抓成功之后锁一天 —— 别把长短两档也搞反了。"""
        # 走真实的链路：候选（只有 id）→ batch-meta（完整字段）
        self.respond_with({"candidates": [{"resourceId": "RAW_a"}]}, "")
        original = BESTBLOGS_MODULE._batch_meta
        BESTBLOGS_MODULE._batch_meta = lambda ids: [{
            "id": "RAW_a", "title": "标题",
            "url": "https://example.test/a", "readUrl": "https://example.test/a",
            "publishDateTimeStr": "2026-09-19 10:00:00",
            "publishTimeStamp": 1789794000000,
        }]
        brief_cache_backup = dict(BESTBLOGS_MODULE._brief_cache)
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update({"at": 0.0, "payload": {}, "ttl": 0.0})
        try:
            result = BESTBLOGS_MODULE.brief(force=True)
        finally:
            BESTBLOGS_MODULE._batch_meta = original
        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(
            float(BESTBLOGS_MODULE._brief_cache.get("ttl") or 0),
            float(BESTBLOGS_MODULE._BRIEF_TTL),
            "成功抓到之后应当锁一整天",
        )
        BESTBLOGS_MODULE._brief_cache.clear()
        BESTBLOGS_MODULE._brief_cache.update(brief_cache_backup)


