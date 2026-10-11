from __future__ import annotations

"""发布门禁的三种情形：测试失败、内容审计 ERROR、全部通过。

用真的 git 仓库（临时目录里的 upstream + clone）跑真的 update-knowledge.sh，
内容门禁用真的 check_knowledge.sh。重启命令由 KNOWLEDGE_RESTART_CMD 换成
写标记文件——测试不碰 systemd，但「有没有重启」这件事照样可断言。

守的是最容易出错的那一条：门禁不过时线上目录必须一个字节都不动。原来的脚本
先 git pull 再重启，失败时工作目录已经是新版本、进程还是旧版本。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = Path("scripts") / "deploy" / "update-knowledge.sh"
REPORTER = Path("scripts") / "deploy" / "write_deploy_report.py"
CHECK_SCRIPT = ROOT.parent / "knowledge-governor" / "scripts" / "check_knowledge.sh"

GOOD_ARTICLE = """---
title: 门禁测试文章
type: concept
status: active
updated: 2026-01-05
review_after: 2027-01-05
change_rate: low
confidence: high
tags:
  - test/deploy
sources:
  - "https://example.org/spec"
---

# 门禁测试文章

正文。要解决的问题、机制、验证、代价、边界、预期都在这里。
"""

# title 缺失是 check_knowledge.sh 的 ERROR 级判定（契约字段缺失）
ERROR_ARTICLE = GOOD_ARTICLE.replace("title: 门禁测试文章\n", "")
# tags 缺失与已过复查日都是 WARN：天天都有，不能用来挡发布
WARN_ARTICLE = (GOOD_ARTICLE
                .replace("tags:\n  - test/deploy\n", "")
                .replace("review_after: 2027-01-05", "review_after: 2026-01-06"))

PASSING_TEST = "def test_smoke():\n    assert True\n"
FAILING_TEST = "def test_smoke():\n    assert 1 == 2, '候选版本把这条测试弄坏了'\n"


class DeployGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CHECK_SCRIPT.is_file():
            raise unittest.SkipTest("找不到 check_knowledge.sh: %s" % CHECK_SCRIPT)

    def setUp(self) -> None:
        base = ROOT / ".agent" / "tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=base, prefix="deploy-gate-"))
        self.upstream = self.tmp / "upstream"
        self.live = self.tmp / "live"
        self.marker = self.tmp / "restarted"
        # 空模板：git 默认往每个仓库塞 26 个 hook 样例，两个仓库 × 五个用例就是
        # 二百多个一次性文件，建了又删。假仓库只需要 git 的版本控制行为
        self.template = self.tmp / "git-template"
        self.template.mkdir()
        self._make_upstream()
        self._git(self.tmp, "clone", "--quiet", "--template", str(self.template),
                  str(self.upstream), str(self.live))

    def tearDown(self) -> None:
        # worktree 可能还挂着（门禁脚本自己会清，异常退出时这里兜底）
        subprocess.run(["git", "-C", str(self.live), "worktree", "prune"],
                       capture_output=True, text=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-c", "user.email=gate@test", "-c", "user.name=gate",
             "-C", str(cwd), *args],
            capture_output=True, text=True, check=True,
        )

    def _write(self, relative: str, content: str) -> None:
        target = self.upstream / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def _make_upstream(self) -> None:
        self.upstream.mkdir(parents=True)
        self._git(self.upstream, "init", "--quiet", "-b", "main",
                  "--template", str(self.template))
        self._write(".gitignore", "/.editorial/\n")
        self._write("tests/test_smoke.py", PASSING_TEST)
        self._write("vault/工程知识/域/主题/文章.md", GOOD_ARTICLE)
        for script in (GATE, REPORTER):
            target = self.upstream / script
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / script, target)
        self._git(self.upstream, "add", "-A")
        self._git(self.upstream, "commit", "--quiet", "-m", "初始版本")

    def _new_revision(self, message: str) -> str:
        self._git(self.upstream, "add", "-A")
        self._git(self.upstream, "commit", "--quiet", "-m", message)
        return self._git(self.upstream, "rev-parse", "HEAD").stdout.strip()

    def _head(self) -> str:
        return self._git(self.live, "rev-parse", "HEAD").stdout.strip()

    def _run_gate(self) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["KNOWLEDGE_RESTART_CMD"] = "touch %s" % self.marker
        env["KNOWLEDGE_CHECK_SCRIPT"] = str(CHECK_SCRIPT)
        env["PYTHON"] = sys.executable
        env.pop("KNOWLEDGE_REPO", None)
        return subprocess.run(
            ["bash", str(self.live / GATE)],
            capture_output=True, text=True, env=env, timeout=600,
        )

    def _latest(self) -> dict:
        marker = self.live / ".editorial" / "reports" / "deploy-latest.json"
        self.assertTrue(marker.is_file(), "门禁必须留下 deploy-latest.json")
        return json.loads(marker.read_text(encoding="utf-8"))

    def _reports(self) -> list[Path]:
        return sorted((self.live / ".editorial" / "reports").glob("deploy-*.md"))

    def test_failing_tests_block_the_release(self) -> None:
        """候选版本测试失败：不切换、不重启，原因写进报告。"""
        old = self._head()
        self._write("tests/test_smoke.py", FAILING_TEST)
        new = self._new_revision("弄坏一条测试")
        result = self._run_gate()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self._head(), old, "门禁不过时线上目录必须还在旧版本")
        self.assertNotEqual(self._head(), new)
        self.assertFalse(self.marker.exists(), "门禁不过时不许重启")
        latest = self._latest()
        self.assertTrue(latest["blocked"])
        self.assertEqual(latest["stage"], "pytest")
        self.assertIn("测试未通过", latest["reason"])
        report = (self.live / ".editorial" / "reports" / latest["report"]).read_text(encoding="utf-8")
        self.assertIn("线上保持旧版本继续服务", report)
        self.assertIn("候选版本把这条测试弄坏了", report)
        # 临时 worktree 用完即清，不留在仓库里
        self.assertEqual(list((self.live / ".editorial" / "deploy").glob("candidate-*")), [])

    def test_audit_errors_block_the_release(self) -> None:
        """内容审计有 ERROR：同样不切换不重启，线上旧版本继续服务。"""
        old = self._head()
        self._write("vault/工程知识/域/主题/文章.md", ERROR_ARTICLE)
        self._new_revision("文章缺 title")
        result = self._run_gate()

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self._head(), old)
        self.assertFalse(self.marker.exists())
        latest = self._latest()
        self.assertTrue(latest["blocked"])
        self.assertEqual(latest["stage"], "knowledge-audit")
        self.assertIn("ERROR", latest["reason"])
        report = (self.live / ".editorial" / "reports" / latest["report"]).read_text(encoding="utf-8")
        self.assertIn("缺 title", report)

    def test_warnings_do_not_block_and_release_switches_and_restarts(self) -> None:
        """只有 WARN 时照常发布：切换到新版本并重启，WARN 只记录。"""
        old = self._head()
        self._write("vault/工程知识/域/主题/文章.md", WARN_ARTICLE)
        new = self._new_revision("只留 WARN 级问题")
        result = self._run_gate()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self._head(), new, "门禁通过后必须切换到候选版本")
        self.assertNotEqual(self._head(), old)
        self.assertTrue(self.marker.exists(), "门禁通过后必须重启")
        latest = self._latest()
        self.assertFalse(latest["blocked"])
        self.assertEqual(latest["revision"], new[:12])
        report = (self.live / ".editorial" / "reports" / latest["report"]).read_text(encoding="utf-8")
        self.assertIn("已切换到候选版本并重启站点服务", report)
        self.assertIn("WARN", report)
        self.assertIn("ERROR: 0", report)

    def test_no_new_revision_does_nothing(self) -> None:
        """远端没有新版本：不跑门禁、不重启、不写报告。"""
        result = self._run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self._reports(), [])

    def test_repo_root_comes_from_the_script_location(self) -> None:
        """仓库路径从脚本位置推导：换个目录名照样工作，不认写死的路径。"""
        moved = self.tmp / "另一个位置"
        shutil.move(str(self.live), str(moved))
        self.live = moved
        self._write("vault/工程知识/域/主题/文章.md", WARN_ARTICLE)
        new = self._new_revision("换目录后再发布")
        result = self._run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self._head(), new)
        self.assertIn(str(moved), (moved / ".editorial" / "reports" / self._latest()["report"])
                      .read_text(encoding="utf-8"))
        self.assertNotIn("/data/code/technical-knowledge",
                         (self.live / GATE).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
