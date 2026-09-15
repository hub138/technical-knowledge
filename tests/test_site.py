from __future__ import annotations

import http.client
import importlib.util
import json
import threading
import unittest
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
        note_path = "工程知识/AI系统/知识与检索/RAG前沿：重排、自动优化与开放索引.md"
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
            "/static/workbench.css",
            "/static/workbench.js",
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
        unresolved: list[str] = []
        for relative, note in self.vault.notes.items():
            for target, _label in SERVER_MODULE.WIKILINK_RE.findall(str(note["body"])):
                if not self.vault.resolve_note(target, relative):
                    unresolved.append(f"{relative} -> {target}")
        self.assertEqual(unresolved, [])

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
        self.assertEqual(len(rows), 130)
        durable = [row for row in rows if row["durable"]]
        self.assertEqual(len(durable), 115)
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
        self.assertIn("把当前笔记标题带入学习中心", self.home)
        self.assertIn("attributeFilter:['class']", self.home)
        self.assertIn("alertUser('这篇笔记暂时无法打开", self.home)
        self.assertIn("状态未知", self.home)
        self.assertIn("学习工具状态暂时不可用", self.home)
        self.assertIn("if(matchMedia('(max-width:760px)').matches)$('#sidebar').classList.add('collapsed')", self.home)
        self.assertIn("filter(d=>d!=='总览'&&d!=='Clippings')", self.home)
        self.assertIn("domain==='总览'||topic==='首页'", self.home)
        self.assertIn("history.replaceState({},'','/')", self.home)

    def test_graph_has_quiet_labels_and_keyboard_contract(self) -> None:
        self.assertIn('.node:hover text,.node:focus text,.node:focus-within text', self.home)
        self.assertIn("tabindex:'0',role:'button','aria-label':n.title", self.home)
        self.assertIn("aria-selected=\"true\"", self.home)
        self.assertIn(".domain-card,.note-row", self.home)
        self.assertIn("['Enter',' '].includes(event.key)", self.home)
        self.assertIn("aria-expanded", self.home)
        self.assertIn("收起目录", self.home)
        self.assertIn("homeButton.classList.toggle('active',view==='home')", self.home)

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
        # The homepage renders the same three destinations as every companion
        # page (知识库 / 项目与工具 / Agent 评估) with 关系图谱 nested under
        # 知识库, instead of its own four flat buttons.
        self.assertIn('id="shared-nav"', self.home)
        self.assertIn("renderSharedNav", self.home)
        self.assertIn("关系图谱", self.home)
        self.assertNotIn('id="home-button"', self.home)
        self.assertNotIn('id="graph-button"', self.home)
        # The knowledge tree and Clippings must survive the nav change.
        self.assertIn('id="domains"', self.home)
        self.assertIn(
            'href="/learn" target="_blank" rel="noopener noreferrer" style=', self.home
        )
        self.assertIn("Keep navigation state stable", self.home)
        self.assertIn("if (key === homeKey) return;", self.home)
        self.assertIn("refreshHomeStatus", self.home)
        self.assertIn("decorateProjectLinks", self.home)
        self.assertIn("window.open('/projects', '_blank')", self.home)
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
            self.assertIn('/static/workbench.css', page)
            self.assertIn('data-page="learning"', page)
        # The classroom page is its own sidebar destination, so it highlights
        # 我的课堂 rather than 学习中心.
        self.assertIn('/static/workbench.css', self.history)
        self.assertIn('data-page="classrooms"', self.history)
        self.assertIn("形成直觉", self.intuition)
        self.assertIn("迁移验证", self.transfer)

    def test_openmaic_teaching_page_has_complete_entry_contract(self) -> None:
        self.assertIn('data-page="learning"', self.openmaic)
        self.assertIn('/launch/openmaic?next=', self.openmaic)
        self.assertIn('target="_blank" rel="noopener noreferrer"', self.openmaic)
        self.assertIn('id="topic"', self.openmaic)
        self.assertIn('data-topic=', self.openmaic)
        self.assertIn("请输入访问码", self.openmaic)
        self.assertIn("不要直接输入 3100", self.openmaic)
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
        shared = (ROOT / "site" / "workbench.css").read_text(encoding="utf-8")
        shared_script = (ROOT / "site" / "workbench.js").read_text(encoding="utf-8")
        self.assertIn(".wb-sidebar", shared)
        self.assertIn("dataset.page", shared_script)
        self.assertIn('target="_blank" rel="noopener noreferrer"', shared_script)
        self.assertIn("item !== current && item !== pages.knowledge", shared_script)
        for page, name in ((self.learning, "learning"), (self.projects, "projects"), (self.evaluation, "evaluation"), (self.intuition, "learning"), (self.transfer, "learning"), (self.history, "classrooms")):
            self.assertIn('/static/workbench.css', page)
            self.assertIn(f'data-page="{name}"', page)
            self.assertIn('class="purpose"', page)

    def test_my_classrooms_is_reachable_from_the_sidebar(self) -> None:
        """Returning to a generated classroom must not require knowing its URL.

        Learning pages nest under 项目与工具 rather than sitting in the main nav,
        because a classroom is a tool you reach for, not a second way to browse
        knowledge. They still have to be one click from that section.
        """
        shared_script = (ROOT / "site" / "workbench.js").read_text(encoding="utf-8")
        self.assertIn("我的课堂", shared_script)
        self.assertIn("/learn/history", shared_script)
        # It is rendered by the sub-nav, which appears inside 项目与工具.
        self.assertIn("subNav", shared_script)
        self.assertIn("pages.classrooms", shared_script)
        self.assertIn('parent: "projects"', shared_script)
        # The main nav stays short: 知识库 / 项目与工具 / Agent 评估.
        nav_block = shared_script.split("const nav = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("pages.learning", nav_block)
        self.assertNotIn("pages.classrooms", nav_block)
        for page in (self.learning, self.projects, self.evaluation, self.history):
            self.assertIn('data-page=', page)

    def test_legacy_workbench_route_is_not_used_by_launch_contract(self) -> None:
        self.assertNotIn("/workbench/new", self.learning)
        self.assertIn("/launch/openmaic?next=", self.home)
        self.assertIn("/launch/openmaic?next=", self.projects)

    def test_login_return_path_is_same_origin(self) -> None:
        self.assertIn("target.origin===location.origin", SERVER_MODULE.LOGIN_HTML)
        self.assertIn("location.replace(safeNext)", SERVER_MODULE.LOGIN_HTML)


if __name__ == "__main__":
    unittest.main()
