#!/usr/bin/env python3
"""A dependency-free knowledge site for this Obsidian vault."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import mimetypes
import os
import posixpath
import pwd
import re
import secrets
import socket
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
UL_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
OL_RE = re.compile(r"^\s*\d+[.)]\s+(.+)$")
AUTH_COOKIE = "knowledge_site_access"
AUTH_SERVICE = "knowledge-site-access"
AUTH_MAX_AGE = 60 * 60 * 24 * 14
AUTH_FAILURE_WINDOW = 5 * 60
AUTH_FAILURE_LIMIT = 5
REPOSITORY_ROOT = Path(
    os.environ.get("KNOWLEDGE_REPOSITORY_ROOT") or Path(__file__).resolve().parents[1]
).resolve()
PUBLIC_SITE = REPOSITORY_ROOT / "index.html"
PUBLIC_PROJECTS_README = REPOSITORY_ROOT / "projects" / "README.md"
PUBLIC_PROJECTS_INDEX = REPOSITORY_ROOT / "projects" / "index.html"
PUBLIC_PROJECTS_ROOT = REPOSITORY_ROOT / "projects"
PUBLIC_EVALUATION = REPOSITORY_ROOT / "apps" / "agent-evaluation" / "index.html"
PUBLIC_LEARNING = REPOSITORY_ROOT / "apps" / "learning" / "index.html"
PUBLIC_OPENMAIC_LEARNING = REPOSITORY_ROOT / "apps" / "learning" / "openmaic.html"
PUBLIC_INTUITION = REPOSITORY_ROOT / "apps" / "learning" / "intuition.html"
PUBLIC_TRANSFER = REPOSITORY_ROOT / "apps" / "learning" / "transfer.html"
PUBLIC_HISTORY = REPOSITORY_ROOT / "apps" / "learning" / "history.html"
OPENMAIC_ACCESS_SERVICE = "knowledge-tools-model-access"
OPENMAIC_JOBS_ROOT = Path(
    os.environ.get("OPENMAIC_HOME") or Path.home() / "Developer" / "knowledge-tools" / "OpenMAIC"
) / "data" / "classroom-jobs"
DEEPTUTOR_HOME = Path(
    os.environ.get("DEEPTUTOR_HOME") or Path.home() / "Developer" / "knowledge-tools" / "DeepTutor"
)


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _keychain_account() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, OSError):
        return os.environ.get("USER", "knowledge-site")


def read_keychain_secret(service: str) -> str:
    """Read one local secret without putting it in command output or URLs."""
    try:
        query = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                _keychain_account(),
                "-s",
                service,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return query.stdout.strip() if query.returncode == 0 else ""


def load_site_password() -> str:
    """Read the login password from an explicit secret source or macOS Keychain."""
    configured = os.environ.get("KNOWLEDGE_SITE_PASSWORD", "").strip()
    if configured:
        return configured
    password_file = os.environ.get("KNOWLEDGE_SITE_PASSWORD_FILE", "").strip()
    if password_file:
        try:
            configured = Path(password_file).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(f"Unable to read KNOWLEDGE_SITE_PASSWORD_FILE: {password_file}") from exc
        if configured:
            return configured
    account = _keychain_account()
    password = read_keychain_secret(AUTH_SERVICE)
    if password:
        return password
    password = secrets.token_urlsafe(18)
    try:
        stored = subprocess.run(
            [
                "/usr/bin/security",
                "add-generic-password",
                "-a",
                account,
                "-s",
                AUTH_SERVICE,
                "-w",
                password,
                "-U",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "Unable to initialize the macOS Keychain password. Set KNOWLEDGE_SITE_PASSWORD "
            "or KNOWLEDGE_SITE_PASSWORD_FILE."
        ) from exc
    if stored.returncode != 0:
        raise RuntimeError("Unable to initialize the knowledge-site password in macOS Keychain")
    return password


def auth_cookie(password: str, issued_at: int | None = None) -> str:
    timestamp = str(issued_at or int(time.time()))
    signature = hmac.new(password.encode("utf-8"), timestamp.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def valid_auth_cookie(value: str | None, password: str) -> bool:
    if not value or "." not in value:
        return False
    timestamp, signature = value.split(".", 1)
    if not timestamp.isdigit() or len(signature) != 64:
        return False
    issued_at = int(timestamp)
    if issued_at > int(time.time()) + 60 or int(time.time()) - issued_at > AUTH_MAX_AGE:
        return False
    expected = auth_cookie(password, issued_at).split(".", 1)[1]
    return hmac.compare_digest(signature, expected)


def openmaic_auth_cookie(access_code: str, issued_at_ms: int | None = None) -> str:
    """Create the token expected by OpenMAIC's access-code middleware."""
    timestamp = str(issued_at_ms or int(time.time() * 1000))
    signature = hmac.new(access_code.encode("utf-8"), timestamp.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fetch_json(
    url: str,
    *,
    timeout: float = 2.0,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def learning_services_status() -> dict[str, object]:
    """Return capability state without exposing provider credentials."""
    openmaic = _fetch_json("http://127.0.0.1:3100/api/health")
    openmaic_providers: dict[str, object] = {}
    access_code = read_keychain_secret(OPENMAIC_ACCESS_SERVICE)
    if access_code:
        openmaic_providers = _fetch_json(
            "http://127.0.0.1:3100/api/server-providers",
            headers={"Cookie": f"openmaic_access={openmaic_auth_cookie(access_code)}"},
        )
    deeptutor = _fetch_json("http://127.0.0.1:8001/api/auth/status")
    catalog = _read_json(DEEPTUTOR_HOME / "data" / "user" / "settings" / "model_catalog.json")
    services = catalog.get("services") if isinstance(catalog.get("services"), dict) else {}

    def selected(service: str) -> bool:
        value = services.get(service) if isinstance(services, dict) else None
        return bool(
            isinstance(value, dict)
            and value.get("active_profile_id")
            and (service == "search" or value.get("active_model_id"))
        )

    knowledge_root = DEEPTUTOR_HOME / "data" / "knowledge_bases"
    knowledge_bases = 0
    if knowledge_root.is_dir():
        try:
            knowledge_bases = sum(1 for item in knowledge_root.iterdir() if item.is_dir())
        except OSError:
            knowledge_bases = 0
    # Obsidian and linked knowledge bases are pointers recorded in kb_config,
    # so they do not have a local directory under data/knowledge_bases.
    kb_config = _read_json(knowledge_root / "kb_config.json")
    configured_bases = kb_config.get("knowledge_bases")
    if isinstance(configured_bases, dict):
        knowledge_bases = max(knowledge_bases, len(configured_bases))
    capabilities = openmaic.get("capabilities") if isinstance(openmaic.get("capabilities"), dict) else {}
    provider_map = openmaic_providers.get("providers")
    provider_map = provider_map if isinstance(provider_map, dict) else {}
    llm_provider = provider_map.get("openai")
    image_provider = openmaic_providers.get("image")
    web_search_provider = openmaic_providers.get("webSearch")
    llm_ready = isinstance(llm_provider, dict) and bool(llm_provider.get("models"))
    image_ready = isinstance(image_provider, dict) and bool(image_provider)
    web_search_ready = isinstance(web_search_provider, dict) and bool(web_search_provider)
    return {
        "openmaic": {
            "online": openmaic.get("status") == "ok" or openmaic.get("success") is True,
            "llm": llm_ready,
            "image": image_ready and bool(capabilities.get("imageGeneration")),
            "web_search": web_search_ready and bool(capabilities.get("webSearch")),
        },
        "deeptutor": {
            "online": bool(deeptutor),
            "auth": bool(deeptutor.get("enabled")),
            "llm": selected("llm"),
            "embedding": selected("embedding"),
            "search": selected("search"),
            "knowledge_bases": knowledge_bases,
        },
    }


def openmaic_generation_jobs(limit: int = 12) -> list[dict[str, object]]:
    """Expose redacted local generation state for the learning history page."""
    if not OPENMAIC_JOBS_ROOT.is_dir():
        return []
    jobs: list[dict[str, object]] = []
    try:
        files = sorted(
            OPENMAIC_JOBS_ROOT.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return []
    for file in files[: max(1, min(limit, 50))]:
        data = _read_json(file)
        if not data:
            continue
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        job_id = str(data.get("id") or file.stem)
        classroom_id = result.get("classroomId") if isinstance(result, dict) else None
        try:
            updated_at = int(file.stat().st_mtime)
        except OSError:
            updated_at = 0
        jobs.append(
            {
                "id": job_id,
                "status": str(data.get("status") or "unknown"),
                "step": str(data.get("step") or ""),
                "progress": data.get("progress"),
                "scenesGenerated": data.get("scenesGenerated"),
                "totalScenes": data.get("totalScenes"),
                "error": str(data.get("error") or ""),
                "classroomId": str(classroom_id) if classroom_id else "",
                "updatedAt": updated_at,
            }
        )
    return jobs


def deeptutor_login_cookie(password: str) -> str:
    """Create a DeepTutor session using its local bootstrap account."""
    request = Request(
        "http://127.0.0.1:8001/api/auth/login",
        data=json_bytes({"username": "admin", "password": password}),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            header = response.headers.get("Set-Cookie", "")
    except (OSError, HTTPError, URLError) as exc:
        raise RuntimeError("DeepTutor authentication is unavailable") from exc
    cookies = SimpleCookie()
    cookies.load(header)
    token = cookies.get("dt_token")
    if token is None or not token.value:
        raise RuntimeError("DeepTutor did not issue a session")
    return token.value


def safe_return_path(value: str, allowed_roots: tuple[str, ...]) -> str:
    parsed = urlsplit(value or "/")
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return "/"
    if not any(parsed.path == root or parsed.path.startswith(root + "/") for root in allowed_roots):
        return "/"
    # ``Location`` is emitted through BaseHTTPRequestHandler, whose header
    # writer only accepts latin-1.  Launch topics and prompts are intentionally
    # allowed to contain Chinese, so normalize the path and query back to an
    # ASCII URL before putting them in a response header.  Preserve existing
    # percent escapes and query separators while encoding Unicode values.
    encoded_path = quote(parsed.path, safe="/%:@-._~!$&'()*+,;=")
    encoded_query = quote(parsed.query, safe="=&%/:?@-._~!$'()*+,;")
    return encoded_path + (("?" + encoded_query) if parsed.query else "")


def canonical_root_location(raw_path: str) -> str | None:
    """Collapse legacy home aliases so bookmarks and shared links have one URL."""
    parsed = urlsplit(raw_path)
    query = parse_qs(parsed.query)
    is_root_alias = parsed.path in {"", "/", "/index.html"}
    if is_root_alias and (
        query.get("path", [""])[0] in {"知识库首页.md", "知识库首页"}
        or query.get("domain", [""])[0] == "总览"
        or query.get("topic", [""])[0] == "首页"
    ):
        return "/"
    if parsed.path == "/index.html":
        return "/" + (("?" + parsed.query) if parsed.query else "")
    return None


def local_addresses() -> set[str]:
    addresses = {"127.0.0.1", "::1"}
    interfaces = ["en0", "en1", "bridge0", "bridge100"]
    try:
        output = subprocess.run(
            ["/sbin/ifconfig"], capture_output=True, text=True, timeout=2, check=False
        ).stdout
        interfaces.extend(re.findall(r"^([A-Za-z0-9]+):", output, re.MULTILINE))
    except (OSError, subprocess.SubprocessError):
        pass
    for interface in dict.fromkeys(interfaces):
        try:
            output = subprocess.run(
                ["/sbin/ifconfig", interface], capture_output=True, text=True, timeout=2, check=False
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        addresses.update(re.findall(r"\binet6?\s+([0-9a-fA-F:.]+)", output))
    addresses.add(detect_host())
    return {
        address
        for address in addresses
        if address and (not address.startswith("127.0.0.") or address in {"127.0.0.1", "::1"})
    }


def is_local_client(address: str) -> bool:
    normalized = address[7:] if address.startswith("::ffff:") else address
    return normalized in local_addresses()


LOGIN_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>工程知识库 · 工具授权</title><style>
:root{color-scheme:light;--bg:#f3f5f2;--panel:#fff;--ink:#202826;--muted:#68736f;--line:#d9dfdb;--accent:#137766}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif}
main{width:min(420px,calc(100% - 32px));background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:30px;box-shadow:0 16px 40px #23302b14}h1{font-size:21px;margin:0 0 7px}p{color:var(--muted);margin:0 0 21px}label{display:block;font-size:13px;font-weight:600;margin-bottom:7px}input{width:100%;padding:12px 13px;border:1px solid var(--line);border-radius:7px;font:inherit;outline:0}input:focus{border-color:var(--accent);box-shadow:0 0 0 3px #13776620}button{width:100%;margin-top:16px;padding:11px 13px;border:0;border-radius:7px;background:var(--accent);color:white;font:600 14px inherit;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.error{min-height:24px;color:#ad3e4f;margin:13px 0 0;font-size:13px}
</style></head><body><main><h1>教学工具授权</h1><p>知识库内容仍可直接阅读；只有启动会使用本机默认模型凭据的教学工具需要授权。</p><form id="form"><label for="password">访问密码</label><input id="password" type="password" autocomplete="current-password" autofocus required><button id="submit" type="submit">继续打开工具</button><div class="error" id="error" role="alert"></div></form></main><script>
const requestedNext=new URLSearchParams(location.search).get('next')||'/';const safeNext=(()=>{try{const target=new URL(requestedNext,location.origin);return target.origin===location.origin&&target.pathname.startsWith('/')?target.pathname+target.search+target.hash:'/'}catch{return '/'}})();const form=document.querySelector('#form');const input=document.querySelector('#password');const button=document.querySelector('#submit');const error=document.querySelector('#error');
form.addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;error.textContent='';try{const response=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:input.value})});if(!response.ok)throw new Error('invalid');location.replace(safeNext)}catch{error.textContent='密码不正确';input.value='';input.focus()}finally{button.disabled=false}});
</script></body></html>'''


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    raw = text[4:marker]
    data: dict[str, object] = {}
    active_list: str | None = None
    for line in raw.splitlines():
        if re.match(r"^\s+-\s+", line) and active_list:
            item = re.sub(r"^\s+-\s+", "", line).strip().strip('"\'')
            data.setdefault(active_list, [])
            if isinstance(data[active_list], list):
                data[active_list].append(item)
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        active_list = None
        if not value:
            data[key] = []
            active_list = key
        elif value.startswith("[") and value.endswith("]"):
            items = [x.strip().strip('"\'') for x in value[1:-1].split(",") if x.strip()]
            data[key] = items
        elif value.lower() in {"true", "false"}:
            data[key] = value.lower() == "true"
        else:
            data[key] = value.strip('"\'')
    return data, text[marker + 5 :]


def scalar(value: object, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    return str(value)


def excerpt(body: str, title: str) -> str:
    in_fence = False
    for raw in body.splitlines():
        line = raw.strip()
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line or line.startswith(("#", "|", "![", "> [!")):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = WIKILINK_RE.sub(lambda m: m.group(2) or Path(m.group(1)).stem, line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"[*_`>]", "", line).strip()
        if line and line != title:
            return line[:190]
    return ""


class Vault:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.notes: dict[str, dict[str, object]] = {}
        self.by_stem: dict[str, list[str]] = {}
        self._signature: tuple[tuple[str, int, int], ...] | None = None
        self._edges_cache: list[dict[str, str]] | None = None
        self.refresh()

    def refresh(self) -> bool:
        files: list[tuple[Path, str, int, int]] = []
        for path in sorted(self.root.rglob("*.md")):
            if not path.is_file() or any(part.startswith(".") for part in path.relative_to(self.root).parts):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = path.relative_to(self.root).as_posix()
            files.append((path, rel, stat.st_mtime_ns, stat.st_size))
        signature = tuple((rel, mtime_ns, size) for _, rel, mtime_ns, size in files)
        if signature == self._signature:
            return False

        notes: dict[str, dict[str, object]] = {}
        for path, rel, mtime_ns, _ in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            front, body = parse_frontmatter(text)
            parts = rel.split("/")
            if parts[0] == "工程知识" and len(parts) > 2:
                category = parts[1]
                topic = parts[2] if len(parts) > 3 else "概览"
            elif parts[0] == "知识库管理":
                category = "知识库管理"
                topic = parts[1] if len(parts) > 2 else "概览"
            elif parts[0] == "Clippings":
                category = "Clippings"
                topic = "剪藏"
            else:
                category = "总览"
                topic = "首页"
            title = scalar(front.get("title"), path.stem)
            tags = front.get("tags", [])
            if not isinstance(tags, list):
                tags = [str(tags)] if tags else []
            notes[rel] = {
                "path": rel,
                "title": title,
                "category": category,
                "topic": topic,
                "type": scalar(front.get("type"), "note"),
                "status": scalar(front.get("status"), "active"),
                "updated": scalar(front.get("updated"), ""),
                "review_after": scalar(front.get("review_after"), ""),
                "change_rate": scalar(front.get("change_rate"), ""),
                "confidence": scalar(front.get("confidence"), ""),
                "tags": tags,
                "sources": front.get("sources", []) if isinstance(front.get("sources", []), list) else [],
                "body": body,
                "mtime": mtime_ns,
                "words": len(re.findall(r"\S+", body)),
                "listed": parts[0] in {"工程知识", "Clippings"} or rel == "知识库首页.md",
            }
        self.notes = notes
        self.by_stem = {}
        for rel, note in notes.items():
            self.by_stem.setdefault(Path(rel).stem, []).append(rel)
        self._signature = signature
        self._edges_cache = None
        return True

    def resolve_note(self, target: str, current: str = "") -> str | None:
        target = unquote(target).strip().replace("\\", "/")
        target = target[1:] if target.startswith("/") else target
        if target.endswith(".md") and target in self.notes:
            return target
        if "/" in target and f"{target}.md" in self.notes:
            return f"{target}.md"
        if target in self.notes:
            return target
        if "/" not in target:
            candidates = self.by_stem.get(Path(target).stem, [])
            if len(candidates) == 1:
                return candidates[0]
            current_dir = str(Path(current).parent)
            for candidate in candidates:
                if str(Path(candidate).parent) == current_dir:
                    return candidate
        return None

    def note(self, rel: str) -> dict[str, object] | None:
        return self.notes.get(rel)

    def edges(self) -> list[dict[str, str]]:
        if self._edges_cache is not None:
            return list(self._edges_cache)
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for rel, note in self.notes.items():
            body = str(note["body"])
            for match in WIKILINK_RE.finditer(body):
                target = self.resolve_note(match.group(1), rel)
                if target and target != rel and (rel, target) not in seen:
                    seen.add((rel, target))
                    result.append({"source": rel, "target": target})
        self._edges_cache = result
        return list(result)

    def safe_file(self, rel: str) -> Path | None:
        try:
            relative = Path(unquote(rel))
            if any(part.startswith(".") for part in relative.parts):
                return None
            path = (self.root / relative).resolve()
        except (OSError, ValueError):
            return None
        if path != self.root and self.root not in path.parents:
            return None
        try:
            return path if path.is_file() else None
        except OSError:
            return None


def render_inline(source: str, vault: Vault, current: str) -> str:
    tokens: dict[str, str] = {}

    def token(value: str) -> str:
        key = f"\x00{len(tokens)}\x00"
        tokens[key] = value
        return key

    def image(match: re.Match[str]) -> str:
        alt, src = match.group(1), match.group(2).strip()
        if src.startswith(("http://", "https://")):
            href = src
        elif src.startswith("data:image/"):
            href = src
        else:
            # A leading "/" means "relative to the vault root"; anything else
            # is relative to the note being rendered.
            candidate = (
                posixpath.normpath(src.lstrip("/"))
                if src.startswith("/")
                else (Path(current).parent / src).as_posix()
            )
            if vault.safe_file(candidate) is None:
                return html.escape(match.group(0))
            href = "/asset?path=" + quote(candidate)
        return token(f'<img loading="lazy" src="{html.escape(href, quote=True)}" alt="{html.escape(alt, quote=True)}">')

    def link(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2).strip()
        if href.endswith(".md") or href in vault.notes:
            resolved = vault.resolve_note(href, current)
            if resolved:
                return token(f'<a data-note="{html.escape(resolved, quote=True)}" href="/?path={quote(resolved)}">{html.escape(label)}</a>')
        safe = href if href.startswith(("http://", "https://", "mailto:", "/", "?")) else "#"
        extra = ' target="_blank" rel="noreferrer"' if safe != "#" else ""
        return token(f'<a href="{html.escape(safe, quote=True)}"{extra}>{html.escape(label)}</a>')

    def wiki(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        explicit_label = (match.group(2) or "").strip()
        resolved = vault.resolve_note(target, current)
        if not resolved:
            label = explicit_label or target
            return token(f'<span class="unresolved">[[{html.escape(label)}]]</span>')
        note = vault.note(resolved) or {}
        label = explicit_label or str(note.get("title") or Path(resolved).stem)
        return token(f'<a data-note="{html.escape(resolved, quote=True)}" href="/?path={quote(resolved)}">{html.escape(label)}</a>')

    source = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image, source)
    source = WIKILINK_RE.sub(wiki, source)
    source = re.sub(r"\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)", link, source)
    source = re.sub(r"`([^`]+)`", lambda m: token(f"<code>{html.escape(m.group(1))}</code>"), source)
    escaped = html.escape(source)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    # A link can contain a token created by an earlier image/link pass.  Keep
    # expanding placeholders until no nested token remains; otherwise a NUL
    # placeholder leaks into the HTML response.
    for _ in range(len(tokens) + 1):
        changed = False
        for key, value in tokens.items():
            marker = html.escape(key)
            if marker in escaped:
                escaped = escaped.replace(marker, value)
                changed = True
        if not changed:
            break
    return escaped


def render_markdown(body: str, vault: Vault, current: str) -> str:
    lines = body.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0

    def is_table_header(index: int) -> bool:
        return index + 1 < len(lines) and "|" in lines[index] and bool(re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]))

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = FENCE_RE.match(line)
        if fence:
            marker, lang = fence.groups()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith(marker[0] * len(marker)):
                code.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            if lang.lower() == "mermaid":
                out.append(f'<pre class="mermaid">{html.escape(chr(10).join(code))}</pre>')
                continue
            klass = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre class=\"code-block\"><code{klass}>{html.escape(chr(10).join(code))}</code></pre>")
            continue
        heading = HEADING_RE.match(line)
        if heading:
            level, text = len(heading.group(1)), heading.group(2)
            ident = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", re.sub(r"<[^>]+>", "", text)).strip("-").lower()
            out.append(f'<h{level} id="{html.escape(ident)}">{render_inline(text, vault, current)}</h{level}>')
            i += 1
            continue
        if line.startswith("> [!"):
            callout: list[str] = [line[2:].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                callout.append(lines[i][1:].lstrip())
                i += 1
            first = callout[0]
            match = re.match(r"\[!([^\]]+)\]\s*(.*)", first)
            kind, first_text = (match.group(1).lower(), match.group(2)) if match else ("note", first)
            content = "\n".join([first_text] + callout[1:])
            out.append(f'<aside class="callout {html.escape(kind)}"><strong>{html.escape(kind.title())}</strong><div>{render_inline(content, vault, current)}</div></aside>')
            continue
        if line.startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(lines[i][1:].lstrip())
                i += 1
            rendered_quote = render_inline("\n".join(quote_lines), vault, current)
            out.append(f"<blockquote>{rendered_quote}</blockquote>")
            continue
        if is_table_header(i):
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not (len(rows) == 1 and all(re.match(r"^:?-{3,}:?$", c) for c in cells)):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join(f"<th>{render_inline(c, vault, current)}</th>" for c in rows[0])
                body_rows = "".join("<tr>" + "".join(f"<td>{render_inline(c, vault, current)}</td>" for c in row) + "</tr>" for row in rows[1:])
                out.append(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body_rows}</tbody></table></div>')
            continue
        ul = UL_RE.match(line)
        ol = OL_RE.match(line)
        if ul or ol:
            ordered = bool(ol)
            items: list[str] = []
            while i < len(lines):
                match = (OL_RE if ordered else UL_RE).match(lines[i])
                if not match:
                    break
                items.append(f"<li>{render_inline(match.group(1), vault, current)}</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if re.match(r"^\s*((---+)|(\*\s*\*\s*\*))\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        paragraph: list[str] = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not FENCE_RE.match(lines[i]) and not HEADING_RE.match(lines[i]):
            if lines[i].startswith((">", "- ", "* ", "+ ")) or OL_RE.match(lines[i]) or is_table_header(i):
                break
            paragraph.append(lines[i])
            i += 1
        out.append(f"<p>{render_inline(' '.join(x.strip() for x in paragraph), vault, current)}</p>")
    return "\n".join(out)


def render_project_markdown_page(path: Path, relative: str, title: str) -> bytes:
    """Render a checked-in project README without exposing it as raw text."""
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return b""
    # The upstream README starts with badge-heavy raw HTML.  Preserve local
    # images as Markdown, while letting this site's renderer own the layout.
    document_dir = posixpath.dirname(relative)

    def image_markdown(match: re.Match[str]) -> str:
        attributes = match.group(1)
        src_match = re.search(r"\bsrc=[\"']([^\"']+)[\"']", attributes, flags=re.IGNORECASE)
        alt_match = re.search(r"\balt=[\"']([^\"']*)[\"']", attributes, flags=re.IGNORECASE)
        alt = alt_match.group(1) if alt_match else ""
        if not src_match:
            return ""
        src = src_match.group(1)
        if src.startswith(("http://", "https://", "data:", "//")):
            # Remote badge images are third-party widgets.  Keep their alt
            # text so a badge row reads as labels instead of disappearing.
            return alt
        # Each README lives at a different depth, and upstream writes image
        # paths relative to the README itself (DeepTutor uses
        # ../../assets/figs/...).  Node paths are resolved against the vault
        # root, and Vault.safe_file rejects any ".." segment, so emit the
        # already-normalised project-relative path instead of the raw one.
        resolved = posixpath.normpath(posixpath.join(document_dir, src))
        if resolved.startswith(("..", "/")):
            return alt
        return f"![{alt}](/{resolved})"

    body = re.sub(r"<img\b([^>]*)>", image_markdown, body, flags=re.IGNORECASE)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    body = re.sub(r"</?(?:p|a|div|br|picture|source|details|summary)\b[^>]*>", "", body, flags=re.IGNORECASE)
    body = html.unescape(body).replace("\xa0", " ")
    project_vault = Vault(PUBLIC_PROJECTS_ROOT)
    rendered = render_markdown(body, project_vault, relative)
    # Markdown links and images are resolved by render_inline against the
    # project root; map those generated URLs back to the project file route.
    def project_asset_url(match: re.Match[str]) -> str:
        relative_asset = unquote(match.group(1)).lstrip("/")
        if not relative_asset or relative_asset.startswith((".", "..")):
            return "#"
        encoded_asset = quote(relative_asset, safe="/%:@-._~!$&'()*+,;=")
        return f'/projects/{encoded_asset}'

    rendered = re.sub(r'href="/\?path=([^"]+)"', lambda match: f'href="{project_asset_url(match)}"', rendered)
    rendered = re.sub(r'src="/asset\?path=([^"]+)"', lambda match: f'src="{project_asset_url(match)}"', rendered)
    # The header used to be hardcoded to OpenMAIC, which leaked the wrong
    # project name onto every other README.  Derive it from the document.
    if relative.startswith("OpenMAIC/"):
        back_href, back_label = "/learn/openmaic", "返回课堂指南 →"
    else:
        back_href, back_label = "/projects", "返回项目与工具 →"
    document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · technical-knowledge</title>
<link rel="stylesheet" href="/static/workbench.css"><script src="/static/workbench.js" data-page="projects" defer></script>
<style>
:root{{--doc-bg:#f4f7f5;--doc-paper:#fff;--doc-ink:#18231f;--doc-muted:#65716c;--doc-line:#dce4df;--doc-accent:#087663;--doc-shadow:0 10px 28px rgba(20,42,35,.07)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--doc-bg);color:var(--doc-ink);font:15px/1.75 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif}}a{{color:var(--doc-accent)}}
.doc-shell{{max-width:1100px;margin:auto;padding:0 30px 70px}}.doc-top{{display:flex;align-items:center;justify-content:space-between;min-height:76px;border-bottom:1px solid var(--doc-line);color:var(--doc-muted);font-size:12px}}.doc-top a{{font-weight:700;text-decoration:none}}
.doc-body{{margin-top:27px;padding:30px 34px;background:var(--doc-paper);border:1px solid var(--doc-line);border-radius:7px;box-shadow:var(--doc-shadow);overflow-wrap:anywhere}}.doc-body h1,.doc-body h2,.doc-body h3,.doc-body h4{{line-height:1.35}}.doc-body h1{{margin:0 0 22px;font-size:31px}}.doc-body h2{{margin:31px 0 10px;padding-bottom:5px;border-bottom:1px solid var(--doc-line);font-size:22px}}.doc-body h3{{margin:24px 0 7px;font-size:18px}}.doc-body p{{margin:12px 0;color:#40504a}}.doc-body ul,.doc-body ol{{padding-left:24px;color:#40504a}}.doc-body li{{margin:4px 0}}.doc-body img{{display:block;max-width:100%;height:auto;margin:13px auto;border:1px solid var(--doc-line);border-radius:5px}}.doc-body p:has(>img){{display:inline-block;vertical-align:middle;margin:4px 7px}}.doc-body p:has(>img[alt="OpenMAIC Banner"]){{display:block;text-align:center;margin:0 0 13px}}.doc-body blockquote{{margin:16px 0;padding:8px 15px;border-left:3px solid var(--doc-accent);background:#f1f6f3;color:var(--doc-muted)}}.doc-body code{{padding:1px 4px;border:1px solid #d8e5e0;border-radius:3px;background:#edf3f0;color:#0e6657;font-family:"SF Mono",monospace;font-size:.9em}}.doc-body .code-block{{padding:15px;overflow:auto;border-radius:6px;background:#202724;color:#e6ece9;line-height:1.6}}.doc-body .code-block code{{padding:0;border:0;background:none;color:inherit}}.doc-body .callout{{padding:12px 15px;border:1px solid #b9d5cd;border-radius:6px;background:#eff7f4}}.doc-body table{{border-collapse:collapse;width:100%;min-width:560px}}.doc-body .table-wrap{{overflow:auto;margin:15px 0}}.doc-body th,.doc-body td{{padding:8px 10px;border:1px solid var(--doc-line);text-align:left;vertical-align:top}}.doc-body th{{background:#edf3f0}}
@media(max-width:700px){{.doc-shell{{padding:0 14px 46px}}.doc-top{{min-height:58px}}.doc-body{{margin-top:18px;padding:20px 17px}}.doc-body h1{{font-size:26px}}.doc-body h2{{font-size:20px}}}}
</style></head><body><div class="doc-shell"><header class="doc-top"><span>{html.escape(title)}</span><a href="{back_href}">{back_label}</a></header><main class="doc-body">{rendered}</main></div></body></html>'''
    return document.encode("utf-8")


INDEX_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>工程知识库</title>
<style>
:root{--bg:#f3f5f2;--panel:#fff;--text:#202826;--muted:#68736f;--line:#d9dfdb;--accent:#137766;--accent2:#a14e32;--warn:#9b6816;--danger:#ad3e4f;--shadow:0 10px 30px rgba(35,48,43,.07)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.7 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.app{max-width:1540px;margin:0 auto;padding:22px 24px 48px}.topbar{display:flex;align-items:center;gap:18px;margin-bottom:22px}.brand{display:flex;align-items:center;gap:12px;min-width:270px}.mark{width:34px;height:34px;border:1px solid #2d8979;border-radius:8px;display:grid;place-items:center;color:var(--accent);font-weight:800}.brand h1{font-size:18px;letter-spacing:0;margin:0}.search{flex:1;position:relative}.search input{width:100%;background:#fff;border:1px solid var(--line);border-radius:8px;color:var(--text);padding:11px 15px 11px 40px;outline:0}.search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px #13776618}.search span{position:absolute;left:14px;top:8px;color:var(--muted);font-size:18px}.layout{display:grid;grid-template-columns:270px minmax(0,1fr);gap:20px}.sidebar,.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}.sidebar{padding:17px;height:max-content;position:sticky;top:18px}.side-title{font-size:11px;text-transform:uppercase;letter-spacing:1.3px;color:var(--muted);margin:4px 0 9px}.side-item{display:flex;align-items:center;justify-content:space-between;color:#43504c;padding:7px 9px;border-radius:6px;cursor:pointer}.side-item:hover,.side-item.active{background:#e3efeb;color:#0e5f51}.count{font-size:11px;color:var(--muted);background:#edf0ed;padding:1px 7px;border-radius:20px}.main{min-width:0}.toolbar{display:flex;align-items:center;justify-content:space-between;margin:0 0 11px}.toolbar h3{margin:0;font-size:16px}.tabs{display:flex;gap:7px}.tab{border:1px solid var(--line);background:#fff;color:#56625e;border-radius:6px;padding:6px 10px;cursor:pointer}.tab.active,.tab:hover{border-color:var(--accent);color:var(--accent);background:#f5fbf9}.note-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:12px}.note-card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:15px;cursor:pointer;min-height:138px;transition:.16s}.note-card:hover{transform:translateY(-2px);border-color:#6bab9f;box-shadow:0 10px 25px #2c4a4314}.note-card h4{margin:0 0 7px;font-size:15px;line-height:1.35}.note-card p{color:var(--muted);font-size:12px;line-height:1.55;margin:0 0 13px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.meta{color:#7a8581;font-size:11px;display:flex;flex-wrap:wrap;gap:5px}.reader{display:none}.reader.open{display:block}.reader-head{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px}.reader h2{font-size:27px;line-height:1.3;margin:0}.reader-sources{font-size:12px;line-height:1.7;color:#586964;background:#f5f8f6;border:1px solid var(--line);border-radius:6px;padding:9px 12px;margin:-7px 0 19px;overflow-wrap:anywhere}.reader-sources:empty{display:none}.source-label{color:var(--accent);font-weight:600}.source-sep{color:#a4aca9;padding:0 3px}.reader-body{font-size:15px;line-height:1.85}.reader-body h1{font-size:29px}.reader-body h2{font-size:22px;border-bottom:1px solid var(--line);padding-bottom:5px}.reader-body h3{font-size:18px}.reader-body p{margin:13px 0}.reader-body ul,.reader-body ol{padding-left:25px}.reader-body li{margin:4px 0}.reader-body blockquote{border-left:3px solid var(--accent2);padding:4px 15px;color:#59635f;background:#f7f3f1;margin:16px 0}.reader-body img{max-width:100%;max-height:520px;border:1px solid var(--line);border-radius:6px;margin:7px 0}.reader-body code{background:#edf3f0;color:#0e6657;border:1px solid #d8e5e0;border-radius:4px;padding:1px 5px;font-family:"SF Mono",monospace;font-size:.88em}.reader-body .code-block{background:#202724;border:1px solid #303a36;border-radius:6px;padding:15px;overflow:auto;color:#e6ece9;line-height:1.6}.reader-body .code-block code{background:none;border:0;padding:0;color:inherit}.table-wrap{overflow:auto;margin:15px 0}.reader-body table{border-collapse:collapse;width:100%;min-width:480px}.reader-body th,.reader-body td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}.reader-body th{color:#31443e;background:#edf3f0}.reader-body td{color:#36423e}.callout{padding:11px 15px;border:1px solid #b9d5cd;border-radius:6px;background:#eff7f4;margin:16px 0;display:flex;gap:10px}.callout.warning{border-color:#dcc995;background:#faf6e8}.callout.danger{border-color:#e2b7bf;background:#fbf0f2}.callout strong{color:var(--accent);font-size:11px;text-transform:uppercase}.callout.warning strong{color:var(--warn)}.unresolved{color:var(--danger);border-bottom:1px dashed var(--danger)}.graph-panel{margin-top:20px;padding:17px}.graph-head h3{margin:0}#graph{width:100%;height:590px;background:#fafbf9;border-radius:6px;margin-top:12px;border:1px solid var(--line);cursor:grab}#graph:active{cursor:grabbing}.edge{stroke:#8b9994;stroke-width:1;opacity:.42}.node circle{stroke:#fff;stroke-width:2}.node text{fill:#44514d;font-size:10px;pointer-events:none}.node:hover circle{stroke:#202826;stroke-width:3}.legend{display:flex;flex-wrap:wrap;gap:9px;margin-top:9px;color:var(--muted);font-size:11px}.legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}.empty{color:var(--muted);padding:30px;text-align:center;border:1px dashed var(--line);border-radius:6px}@media(max-width:850px){.app{padding:14px}.layout{grid-template-columns:1fr}.sidebar{position:static;display:flex;gap:8px;overflow:auto;padding:10px}.side-title{display:none}.side-item{white-space:nowrap}.topbar{flex-wrap:wrap;gap:11px}.brand{min-width:0}.search{order:3;flex-basis:100%}#graph{height:450px}}
</style></head>
<body><div class="app">
<header class="topbar"><div class="brand"><div class="mark">⌁</div><div><h1>工程知识库</h1></div></div><div class="search"><span>⌕</span><input id="search" placeholder="搜索知识" autocomplete="off"></div></header>
<div class="layout"><aside class="sidebar"><div class="side-title">知识主题</div><div id="categories"></div><div class="side-title" style="margin-top:18px">入口</div><div class="side-item" data-view="all">全部内容 <span class="count" id="all-count">—</span></div><div class="side-item" data-view="graph">关系图谱</div></aside>
<main class="main">
<section id="listing"><div class="toolbar"><h3 id="listing-title">全部知识</h3><div class="tabs"><button class="tab active" data-sort="updated">最近更新</button><button class="tab" data-sort="title">按标题</button></div></div><div id="notes" class="note-grid"></div></section>
<section id="reader" class="panel reader" style="padding:25px"><div class="reader-head"><div><h2 id="reader-title"></h2></div></div><div id="reader-sources" class="reader-sources"></div><div id="reader-body" class="reader-body"></div></section>
<section id="graph-panel" class="panel graph-panel"><div class="graph-head"><h3>知识关系图谱</h3></div><svg id="graph" viewBox="0 0 1200 590" role="img" aria-label="知识关系图谱"></svg><div id="legend" class="legend"></div></section></main></div></div>
<script>
const state={notes:[],edges:[],category:'all',query:'',sort:'updated',selected:null,zoom:1,pan:{x:0,y:0}};
const colors=['#70d6c2','#8ca6ff','#f2bd74','#f28ca7','#b79cff','#67b6e8','#d8e17d','#a8b6cc'];
const $=s=>document.querySelector(s);
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
async function getJSON(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(await r.text());return r.json();}
function filtered(){let a=state.notes.filter(n=>(state.category==='all'||n.category===state.category)&&(!state.query||[n.title,n.path,n.type,n.status,(n.tags||[]).join(' '),(n.sources||[]).join(' '),n.search_text||''].join(' ').toLowerCase().includes(state.query.toLowerCase())));a.sort((x,y)=>state.sort==='title'?x.title.localeCompare(y.title,'zh-CN'):(y.updated||'').localeCompare(x.updated||''));return a;}
function orderedCategories(values){const order=['总览','人工智能','软件工程','数据系统','计算机系统与性能','分布式系统','编程语言','质量工程','Clippings'];return [...values].sort((a,b)=>(order.indexOf(a)<0?999:order.indexOf(a))-(order.indexOf(b)<0?999:order.indexOf(b))||a.localeCompare(b,'zh-CN'));}
function renderCategories(){const counts={};state.notes.forEach(n=>counts[n.category]=(counts[n.category]||0)+1);const cats=orderedCategories(Object.keys(counts));$('#categories').innerHTML=cats.map(c=>`<div class="side-item ${state.category===c?'active':''}" data-category="${esc(c)}"><span>${esc(c)}</span><span class="count">${counts[c]}</span></div>`).join('');$('#all-count').textContent=state.notes.length;document.querySelectorAll('[data-category]').forEach(e=>e.onclick=()=>showListing(e.dataset.category));}
function renderNotes(){const list=filtered();$('#listing-title').textContent=state.category==='all'?'全部知识':state.category;$('#notes').innerHTML=list.length?list.map(n=>`<article class="note-card" data-path="${esc(n.path)}"><h4>${esc(n.title)}</h4><p>${esc(n.excerpt||'')}</p>${n.updated?`<div class="meta"><span>${esc(n.updated)}</span></div>`:''}</article>`).join(''):`<div class="empty">没有匹配内容</div>`;document.querySelectorAll('.note-card').forEach(e=>e.onclick=()=>openNote(e.dataset.path));}
function renderSources(sources){if(!sources||!sources.length)return '';return '<span class="source-label">来源</span> '+sources.map(s=>{const value=String(s);if(value.startsWith('http://')||value.startsWith('https://'))return `<a href="${esc(value)}" target="_blank" rel="noreferrer">${esc(value)}</a>`;const match=value.match(/^\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]$/);if(match){const target=match[1],label=match[2]||target;return `<a data-note="${esc(target)}" href="/?path=${encodeURIComponent(target)}">${esc(label)}</a>`;}return esc(value);}).join('<span class="source-sep"> · </span>');}
async function openNote(path){try{const n=await getJSON('/api/note?path='+encodeURIComponent(path));state.selected=path;$('#listing').style.display='none';$('#reader').classList.add('open');$('#reader-title').textContent=n.title;$('#reader-sources').innerHTML=renderSources(n.sources);$('#reader-body').innerHTML=n.html;history.replaceState({},'', '/?path='+encodeURIComponent(path));window.scrollTo({top:0,behavior:'smooth'});}catch(e){console.error(e);}}
function closeReader(){if(!state.selected)return;state.selected=null;$('#listing').style.display='block';$('#reader').classList.remove('open');history.replaceState({},'', '/');}
function showListing(category){state.category=category;state.selected=null;$('#listing').style.display='block';$('#reader').classList.remove('open');history.replaceState({},'', '/');renderAll();window.scrollTo({top:0,behavior:'smooth'});}
function renderGraph(){const svg=$('#graph');const W=1200,H=590;svg.innerHTML='';const cats=orderedCategories(new Set(state.notes.map(n=>n.category)));const positions=new Map();const cx=W/2,cy=H/2;cats.forEach((c,ci)=>{const angle=-Math.PI/2+ci*2*Math.PI/cats.length;const anchor={x:cx+Math.cos(angle)*185,y:cy+Math.sin(angle)*145};const group=state.notes.filter(n=>n.category===c);group.forEach((n,ni)=>{const a=ni*2*Math.PI/Math.max(group.length,1);const r=48+Math.min(group.length,25)*2;positions.set(n.path,{x:anchor.x+Math.cos(a)*r,y:anchor.y+Math.sin(a)*r});});});const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.id='graph-world';const edges=document.createElementNS('http://www.w3.org/2000/svg','g');edges.classList.add('edges');state.edges.forEach(e=>{const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return;const line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);line.classList.add('edge');edges.append(line);});g.append(edges);state.notes.forEach(n=>{const p=positions.get(n.path);if(!p)return;const node=document.createElementNS('http://www.w3.org/2000/svg','g');node.classList.add('node');node.setAttribute('transform',`translate(${p.x},${p.y})`);node.onclick=()=>openNote(n.path);const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('r',n.path===state.selected?'8':'5');circle.setAttribute('fill',colors[cats.indexOf(n.category)%colors.length]);const titleEl=document.createElementNS('http://www.w3.org/2000/svg','title');titleEl.textContent=n.title;circle.append(titleEl);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('y','-9');label.setAttribute('text-anchor','middle');label.textContent=n.title.length>18?n.title.slice(0,17)+'…':n.title;node.append(circle,label);g.append(node);});svg.append(g);$('#legend').innerHTML=cats.map((c,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>${esc(c)}</span>`).join('');}
function bindGraph(){const svg=$('#graph');let drag=null;svg.onwheel=e=>{e.preventDefault();state.zoom=Math.max(.45,Math.min(2.5,state.zoom*(e.deltaY<0?1.1:.9)));$('#graph-world').setAttribute('transform',`translate(${state.pan.x} ${state.pan.y}) scale(${state.zoom})`);};svg.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,px:state.pan.x,py:state.pan.y};svg.setPointerCapture(e.pointerId)};svg.onpointermove=e=>{if(!drag)return;state.pan.x=drag.px+e.clientX-drag.x;state.pan.y=drag.py+e.clientY-drag.y;const w=$('#graph-world');if(w)w.setAttribute('transform',`translate(${state.pan.x} ${state.pan.y}) scale(${state.zoom})`)};svg.onpointerup=()=>drag=null;}
function renderAll(){renderCategories();renderNotes();renderGraph();}
async function load(){try{const data=await getJSON('/api/notes');state.notes=data.notes;state.edges=data.edges;renderAll();if(state.selected)openNote(state.selected);}catch(e){console.error(e);}}
$('#search').oninput=e=>{state.query=e.target.value;state.selected=null;$('#reader').classList.remove('open');$('#listing').style.display='block';history.replaceState({},'', '/');renderNotes();};document.querySelectorAll('[data-sort]').forEach(e=>e.onclick=()=>{state.sort=e.dataset.sort;document.querySelectorAll('[data-sort]').forEach(x=>x.classList.toggle('active',x===e));renderNotes();});document.querySelector('[data-view="all"]').onclick=()=>showListing('all');document.querySelector('[data-view="graph"]').onclick=()=>$('#graph-panel').scrollIntoView({behavior:'smooth'});document.addEventListener('click',e=>{const a=e.target.closest('a[data-note]');if(a){e.preventDefault();openNote(a.dataset.note);}});window.onpopstate=()=>{const p=new URLSearchParams(location.search).get('path');p?p&&openNote(p):closeReader();};bindGraph();const initial=new URLSearchParams(location.search).get('path');load().then(()=>initial&&openNote(initial));setInterval(load,10000);
</script></body></html>'''


MODERN_INDEX_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>工程知识库</title>
<style>
:root{
  --canvas:#f7f8f6;--paper:#fff;--ink:#18201d;--muted:#66716c;
  --line:#dce2de;--line-strong:#c8d1cc;--accent:#0b705e;--accent-soft:#e9f3f0;
  --code:#202622;--warn:#9b5b23;--max:1480px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.7 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Noto Sans CJK SC",sans-serif}
button,input{font:inherit}
button{color:inherit}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.shell{max-width:var(--max);margin:auto;min-height:100vh;padding:0 24px 48px}
.topbar{height:72px;display:grid;grid-template-columns:260px minmax(280px,620px) 1fr;gap:24px;align-items:center;border-bottom:1px solid var(--line)}
.brand{border:0;background:none;padding:0;display:flex;align-items:center;gap:11px;cursor:pointer;text-align:left}
.brand-mark{width:30px;height:30px;border:1px solid var(--accent);color:var(--accent);display:grid;place-items:center;font:700 14px/1 ui-monospace,monospace;border-radius:6px}
.brand-name{font-size:17px;font-weight:700}
.search{position:relative}
.search input{width:100%;height:40px;border:1px solid var(--line-strong);background:var(--paper);border-radius:6px;padding:0 40px 0 14px;outline:0}
.search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(11,112,94,.09)}
.search kbd{position:absolute;right:10px;top:9px;border:1px solid var(--line);background:var(--canvas);color:var(--muted);padding:0 6px;border-radius:4px;font-size:11px}
.top-actions{display:flex;justify-content:flex-end;gap:6px}
.quiet-button{height:36px;border:1px solid transparent;background:none;border-radius:6px;padding:0 10px;cursor:pointer;color:var(--muted)}
.quiet-button:hover,.quiet-button.active{background:var(--accent-soft);color:var(--accent)}
.workspace{display:grid;grid-template-columns:260px minmax(0,1fr);gap:34px;padding-top:26px}
.sidebar{position:sticky;top:20px;align-self:start;max-height:calc(100vh - 40px);overflow:auto;padding-right:12px}
.nav-heading{margin:0 0 12px;padding:0 8px;color:#8a948f;font-size:11px;font-weight:700;letter-spacing:.08em}
.domain{margin-bottom:4px}
.domain-button,.topic-button{width:100%;border:0;background:none;text-align:left;cursor:pointer;border-radius:5px}
.domain-button{display:flex;align-items:center;gap:8px;padding:8px;font-weight:650}
.domain-button:hover,.domain.active>.domain-button{background:var(--accent-soft);color:var(--accent)}
.chevron{width:12px;color:#8a948f;font-size:10px}
.topic-list{display:none;padding:2px 0 5px 20px}
.domain.open .topic-list{display:block}
.topic-button{padding:5px 9px;color:var(--muted);font-size:13px}
.topic-button:hover,.topic-button.active{color:var(--accent);background:#f0f5f3}
.content{min-width:0}
.directory-head{display:flex;align-items:end;justify-content:space-between;border-bottom:1px solid var(--line);padding:2px 0 16px;margin-bottom:4px}
.directory-head h1{margin:0;font-size:25px;line-height:1.25;letter-spacing:0}
.directory-head p{margin:4px 0 0;color:var(--muted)}
.sorts{display:flex;gap:4px}
.sort{border:0;background:none;color:var(--muted);padding:5px 8px;border-radius:5px;cursor:pointer}
.sort.active,.sort:hover{color:var(--accent);background:var(--accent-soft)}
.topic-section{padding:23px 0 9px;border-bottom:1px solid var(--line)}
.topic-title{display:flex;align-items:center;gap:10px;margin:0 0 3px;font-size:12px;color:var(--muted);font-weight:700}
.topic-title::after{content:"";height:1px;background:var(--line);flex:1}
.topic-title small{font-size:11px;color:#9aa39f;font-weight:500}
.note-row{display:grid;grid-template-columns:minmax(230px,38%) minmax(0,1fr);gap:26px;padding:13px 8px;border-radius:6px;cursor:pointer}
.note-row:hover{background:var(--paper)}
.note-row h2{font-size:15px;line-height:1.45;margin:0;font-weight:650}
.note-row p{margin:0;color:var(--muted);font-size:13px;line-height:1.6}
.note-row .path{font-size:11px;color:#929b97;margin-top:4px}
.empty{padding:60px 0;text-align:center;color:var(--muted)}
.reader{display:none;max-width:930px;margin:0 auto}
.reader.open{display:block}
.reader-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.back{border:0;background:none;color:var(--muted);padding:4px 0;cursor:pointer}
.back:hover{color:var(--accent)}
.reader-context{display:flex;align-items:center;gap:7px;margin-bottom:10px;color:var(--muted);font-size:12px}
.reader-context .context-domain{color:var(--accent);font-weight:700}
.reader-context .context-sep{color:#b4bdb8}
.reader-title{font-size:32px;line-height:1.3;letter-spacing:0;margin:0 0 15px}
.tool-entry-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 28px}
.tool-entry{border:1px solid var(--line);border-top:3px solid var(--accent);background:var(--paper);padding:15px 16px;min-height:216px;display:flex;flex-direction:column}
.tool-entry:nth-child(2){border-top-color:#a05b37}.tool-entry:nth-child(3){border-top-color:#3f70a8}.tool-entry:nth-child(4){border-top-color:#7862a3}
.tool-entry h2{font-size:16px;line-height:1.35;margin:0 0 4px;letter-spacing:0}.tool-entry .tool-entry-kicker{color:var(--muted);font-size:12px;margin:0 0 9px}.tool-entry p{color:#53615c;font-size:12px;line-height:1.65;margin:0 0 11px}.tool-entry-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:auto}.tool-entry-primary,.tool-entry-secondary{display:inline-flex;align-items:center;justify-content:center;min-height:32px;padding:0 11px;border-radius:5px;font-size:12px;font-weight:650}.tool-entry-primary{background:var(--accent);color:#fff}.tool-entry-primary:hover{background:#085b4c;text-decoration:none}.tool-entry-secondary{border:1px solid var(--line-strong);color:var(--ink);background:var(--canvas)}.tool-entry-secondary:hover{border-color:var(--accent);color:var(--accent);text-decoration:none}
.study-launch{border:1px solid var(--line);border-left:3px solid var(--accent);background:var(--accent-soft);padding:13px 15px;margin:0 0 22px;display:flex;gap:18px;align-items:center;justify-content:space-between}
.study-launch-copy{display:flex;flex-direction:column;gap:2px;min-width:190px}.study-launch-copy strong{font-size:14px}.study-launch-copy span{font-size:12px;color:var(--muted)}
.study-launch-form{display:flex;gap:7px;flex:1;justify-content:flex-end}.study-launch-form input{min-width:240px;max-width:430px;flex:1;border:1px solid var(--line);border-radius:5px;padding:8px 10px;background:var(--paper);font:inherit;outline:0}.study-launch-form input:focus{border-color:var(--accent)}.study-launch-form button{border:1px solid var(--accent);border-radius:5px;padding:7px 10px;background:var(--paper);color:var(--accent);font:inherit;cursor:pointer;white-space:nowrap}.study-launch-form button:hover{background:var(--accent);color:#fff}
.sources{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:27px;color:var(--muted);font-size:12px;overflow-wrap:anywhere}
.sources:empty{display:none}
.source-label{font-weight:700;color:var(--ink);margin-right:8px}
.source-sep{color:#b3bbb7;padding:0 5px}
.article{font-size:15px;line-height:1.9}
.article h2{font-size:22px;line-height:1.45;margin:38px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line);letter-spacing:0}
.article h3{font-size:17px;line-height:1.5;margin:27px 0 8px}
.article p{margin:13px 0}
.article ul,.article ol{padding-left:24px}
.article li{margin:5px 0}
.article blockquote{margin:20px 0;padding:8px 18px;border-left:3px solid var(--accent);background:#f0f5f3;color:#4f5c57}
.article img{display:block;max-width:100%;max-height:620px;margin:22px auto;border:1px solid var(--line)}
.article code{font-family:"SF Mono","Cascadia Code",monospace;background:#edf2ef;border:1px solid var(--line);padding:1px 5px;border-radius:4px;font-size:.88em}
.article pre.code-block{background:var(--code);color:#edf2ef;overflow:auto;padding:17px 19px;border-radius:6px}
.article pre.code-block code{background:none;border:0;padding:0;color:inherit}
.table-wrap{overflow:auto;margin:20px 0}
.article table{width:100%;border-collapse:collapse;min-width:560px;font-size:13px}
.article th,.article td{padding:9px 11px;border:1px solid var(--line);text-align:left;vertical-align:top}
.article th{background:#f0f4f2;font-weight:650}
.callout{display:flex;gap:12px;margin:20px 0;padding:12px 15px;border-left:3px solid var(--accent);background:var(--accent-soft)}
.callout strong{font-size:11px;text-transform:uppercase;color:var(--accent)}
.unresolved{color:#a63c4d;text-decoration:underline dotted}
.mermaid{margin:22px auto;text-align:center;background:var(--paper);overflow:auto}
.graph-view{display:none}
.graph-view.open{display:block}
.graph-head{display:flex;align-items:end;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:15px}
.graph-head h1{margin:0;font-size:25px}
.graph-head p{margin:4px 0 0;color:var(--muted)}
.graph-tools{display:flex;gap:4px}
.graph-tool{width:30px;height:30px;border:1px solid var(--line);background:var(--paper);border-radius:5px;color:var(--muted);cursor:pointer;font-size:16px;line-height:1}
.graph-tool:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.visual-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-top:14px}
.visual-tab{border:1px solid var(--line);background:var(--paper);color:var(--muted);border-radius:5px;padding:7px 11px;cursor:pointer;font:inherit}
.visual-tab:hover,.visual-tab.active{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
#graph{display:block;width:100%;height:690px;margin-top:18px;background:var(--paper);border:1px solid var(--line);cursor:grab}
#graph:active{cursor:grabbing}
.domain-label{fill:#26312d;font-size:15px;font-weight:700}
.topic-link{stroke:#b7c2bc;stroke-width:1;opacity:.38}
.edge{stroke:#9ca8a2;stroke-width:.65;opacity:.14}
.edge.focused{stroke:#526b62;stroke-width:1.4;opacity:.72}
.topic-node{cursor:pointer}
.topic-node circle{fill:#fff;stroke-width:2}
.topic-node text{fill:#52605a;font-size:10px;font-weight:650;pointer-events:none}
.node circle{stroke:#fff;stroke-width:1.5;cursor:pointer}
.node text{fill:#26312d;font-size:11px;font-weight:600;opacity:0;pointer-events:none;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}
.node:hover circle{stroke:var(--ink);stroke-width:2.5}
.node:hover text{opacity:1}
.diagram-group{cursor:pointer}
.diagram-box{fill:#f7faf8;stroke:#a9bbb3;stroke-width:1.4}
.diagram-box.primary{fill:#e8f3ef;stroke:#328574}
.diagram-box.secondary{fill:#f5f1ec;stroke:#bc9d82}
.diagram-label{fill:#26312d;font-size:15px;font-weight:650;text-anchor:middle;dominant-baseline:middle}
.diagram-small{fill:#66736d;font-size:11px;text-anchor:middle;dominant-baseline:middle}
.diagram-edge{stroke:#6b867d;stroke-width:2;fill:none;marker-end:url(#graph-arrow);opacity:.82}
.diagram-edge.dashed{stroke-dasharray:6 5;opacity:.58}
.axis-line{stroke:#63746d;stroke-width:1.5;marker-end:url(#graph-arrow)}
.axis-label{fill:#52605a;font-size:13px;font-weight:600}
.quadrant-fill{fill:#f4f7f5;stroke:#dbe5df;stroke-width:1}
.quadrant-fill.alt{fill:#fbf5ef}
.quadrant-title{fill:#75827c;font-size:12px;font-weight:600}
.point{stroke:#fff;stroke-width:2;cursor:pointer}
.point-label{fill:#26312d;font-size:13px;font-weight:650}
.graph-note{fill:#75827c;font-size:12px}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-top:10px}
.legend i{display:inline-block;width:8px;height:8px;margin-right:5px;border-radius:50%}
@media(max-width:900px){
  .shell{padding:0 14px 36px}.topbar{height:auto;padding:14px 0;grid-template-columns:1fr auto}.search{grid-column:1/-1;grid-row:2}.workspace{grid-template-columns:1fr;gap:18px;padding-top:16px}
  .sidebar{position:static;max-height:none;overflow:auto;padding:0 0 9px}.sidebar #domains{display:flex;gap:7px;width:max-content}.nav-heading,.topic-list{display:none!important}.domain{flex:none;margin:0}.domain-button{white-space:nowrap;border:1px solid var(--line);background:var(--paper)}.chevron{display:none}
  .note-row{grid-template-columns:1fr;gap:5px;padding:13px 5px}.reader-title{font-size:26px}.article{font-size:14px}.reader-context{margin-top:2px}#graph{height:520px}.visual-tabs{gap:5px}.visual-tab{padding:6px 8px;font-size:13px}.study-launch{display:block}.study-launch-copy{margin-bottom:10px}.study-launch-form{display:grid;grid-template-columns:1fr 1fr}.study-launch-form input{min-width:0;max-width:none;grid-column:1/-1}.study-launch-form button{width:100%}.tool-entry-grid{grid-template-columns:1fr;gap:10px}.tool-entry{min-height:0}.tool-entry p{max-width:58ch}
}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <button class="brand" id="home-button"><span class="brand-mark">K</span><span class="brand-name">工程知识库</span></button>
    <label class="search"><input id="search" placeholder="搜索概念、机制或问题" autocomplete="off"><kbd>/</kbd></label>
    <div class="top-actions"><button class="quiet-button" id="directory-button">目录</button><button class="quiet-button" id="graph-button">关系图</button></div>
  </header>
  <div class="workspace">
    <nav class="sidebar"><p class="nav-heading">知识领域</p><div id="domains"></div></nav>
    <main class="content">
      <section id="directory">
        <header class="directory-head"><div><h1 id="directory-title">全部知识</h1><p id="directory-subtitle"></p></div><div class="sorts"><button class="sort active" data-sort="title">主题</button><button class="sort" data-sort="updated">更新</button></div></header>
        <div id="note-groups"></div>
      </section>
      <article id="reader" class="reader">
        <div class="reader-top"><button class="back" id="back-button">返回目录</button></div>
        <div class="reader-context" id="reader-context"></div>
        <h1 class="reader-title" id="reader-title"></h1>
        <section id="study-launch" class="study-launch" hidden>
          <div class="study-launch-copy"><strong>开始学习一个主题</strong><span>把问题带进互动讲解、检索和练习</span></div>
          <div class="study-launch-form"><input id="study-topic" placeholder="例如：RAG 如何从检索走向可验证系统？" autocomplete="off"><button id="open-classroom">互动课堂</button><button id="open-tutor">学习工作区</button></div>
        </section>
        <div class="sources" id="reader-sources"></div>
        <div class="article" id="reader-body"></div>
      </article>
      <section id="graph-view" class="graph-view">
        <header class="graph-head"><div><h1 id="graph-title">知识关系</h1><p id="graph-subtitle">领域、主题与笔记之间的关联</p></div><div class="graph-tools"><button class="graph-tool" id="graph-zoom-out" title="缩小" aria-label="缩小">−</button><button class="graph-tool" id="graph-reset" title="重置视图" aria-label="重置视图">↺</button><button class="graph-tool" id="graph-zoom-in" title="放大" aria-label="放大">+</button></div></header>
        <div class="visual-tabs" role="tablist" aria-label="图谱视图"><button class="visual-tab active" data-visual="network" role="tab" aria-selected="true">关系网络</button><button class="visual-tab" data-visual="flow" role="tab" aria-selected="false">知识流通</button><button class="visual-tab" data-visual="learning" role="tab" aria-selected="false">学习循环</button><button class="visual-tab" data-visual="architecture" role="tab" aria-selected="false">AI 架构</button><button class="visual-tab" data-visual="quadrant" role="tab" aria-selected="false">选型象限</button></div>
        <svg id="graph" viewBox="0 0 1200 690" role="img" aria-label="知识关系"></svg>
        <div id="legend" class="legend"></div>
      </section>
    </main>
  </div>
</div>
<script src="/static/mermaid.min.js"></script>
<script>
mermaid.initialize({startOnLoad:false,theme:'neutral',securityLevel:'strict',fontFamily:'-apple-system,BlinkMacSystemFont,PingFang SC,sans-serif'});
window.renderMermaid=async()=>{const nodes=document.querySelectorAll('.mermaid:not([data-processed])');if(nodes.length)await mermaid.run({nodes});};
</script>
<script>
const state={notes:[],edges:[],domain:'all',topic:'all',query:'',sort:'title',selected:null,view:'directory',graphMode:'network',zoom:1,pan:{x:0,y:0},navigation:0};
const domainOrder=['总览','AI系统','后端与分布式系统','数据系统','计算机系统与性能','软件构建与质量','Clippings'];
const colors=['#0b705e','#3f70a8','#a05b37','#7862a3','#567b42','#9b4660','#697772'];
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const ordered=values=>[...values].sort((a,b)=>(domainOrder.indexOf(a)<0?99:domainOrder.indexOf(a))-(domainOrder.indexOf(b)<0?99:domainOrder.indexOf(b))||a.localeCompare(b,'zh-CN'));
async function json(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(await r.text());return r.json();}
function shownNotes(){
  const q=state.query.toLowerCase();
  const list=state.notes.filter(n=>(state.domain==='all'||n.category===state.domain)&&(state.topic==='all'||n.topic===state.topic)&&(!q||[n.title,n.path,n.topic,n.search_text,(n.tags||[]).join(' ')].join(' ').toLowerCase().includes(q)));
  const relevance=n=>{if(!q)return 0;const title=String(n.title||'').toLowerCase(),topic=String(n.topic||'').toLowerCase(),tags=(n.tags||[]).join(' ').toLowerCase(),path=String(n.path||'').toLowerCase();return title.includes(q)?4:topic.includes(q)?3:tags.includes(q)||path.includes(q)?2:1};
  return list.sort((a,b)=>relevance(b)-relevance(a)||(state.sort==='updated'?(b.updated||'').localeCompare(a.updated||'')||a.title.localeCompare(b.title,'zh-CN'):a.title.localeCompare(b.title,'zh-CN')));
}
function renderDomains(){
  const domains=ordered(new Set(state.notes.map(n=>n.category)));
  $('#domains').innerHTML=domains.map(domain=>{
    const topics=[...new Set(state.notes.filter(n=>n.category===domain).map(n=>n.topic))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const open=state.domain===domain;
    return `<div class="domain ${open?'active open':''}"><button class="domain-button" data-domain="${esc(domain)}"><span class="chevron">${open?'▼':'▶'}</span><span>${esc(domain==='总览'?'首页':domain)}</span></button><div class="topic-list">${topics.map(topic=>`<button class="topic-button ${open&&state.topic===topic?'active':''}" data-domain="${esc(domain)}" data-topic="${esc(topic)}">${esc(topic)}</button>`).join('')}</div></div>`;
  }).join('');
  document.querySelectorAll('.domain-button').forEach(button=>button.onclick=()=>selectDirectory(button.dataset.domain,'all'));
  document.querySelectorAll('.topic-button').forEach(button=>button.onclick=e=>{e.stopPropagation();selectDirectory(button.dataset.domain,button.dataset.topic)});
}
function renderDirectory(){
  const list=shownNotes(),groups=new Map();
  for(const note of list){const key=state.domain==='all'?note.category:note.topic;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(note);}
  $('#directory-title').textContent=state.query?'搜索结果':state.topic!=='all'?state.topic:state.domain==='all'?'全部知识':state.domain;
  $('#directory-subtitle').textContent=state.query?`“${state.query}” · ${list.length} 篇`:state.domain==='all'?`${list.length} 篇知识`:state.topic==='all'?`${list.length} 篇知识`:'';
  $('#note-groups').innerHTML=groups.size?[...groups].map(([group,notes])=>`<section class="topic-section"><h2 class="topic-title"><span>${esc(group==='总览'?'首页':group)}</span><small>${notes.length}</small></h2>${notes.map(n=>`<article class="note-row" data-path="${esc(n.path)}"><div><h2>${esc(n.title)}</h2><div class="path">${esc(n.topic)}</div></div><p>${esc(n.excerpt||'')}</p></article>`).join('')}</section>`).join(''):`<div class="empty">没有匹配内容</div>`;
  document.querySelectorAll('.note-row').forEach(row=>row.onclick=()=>openNote(row.dataset.path));
}
function sourceLabel(value){try{const host=new URL(value).hostname;return host.startsWith('www.')?host.slice(4):host}catch{return value}}
function renderSources(sources){
  if(!sources||!sources.length)return '';
  return '<span class="source-label">来源</span>'+sources.map(source=>{
    const value=String(source);
    if(value.startsWith('http://')||value.startsWith('https://'))return `<a href="${esc(value)}" target="_blank" rel="noreferrer">${esc(sourceLabel(value))}</a>`;
    if(value.startsWith('[[')&&value.endsWith(']]')){const parts=value.slice(2,-2).split('|'),target=parts[0].split('#')[0],label=parts[1]||target.split('/').pop();return `<a data-note="${esc(target)}" href="/?path=${encodeURIComponent(target)}">${esc(label)}</a>`}
    return esc(value)
  }).join('<span class="source-sep">·</span>');
}
function refreshServiceLinks(){document.querySelectorAll('[data-service-port]').forEach(link=>{const current=link.getAttribute('href')||'';if(current.startsWith('/launch/'))return;const next=link.dataset.servicePort==='3782'?'/chat':'/';link.href=`${link.dataset.servicePort==='3782'?'/launch/deeptutor':'/launch/openmaic'}?next=${encodeURIComponent(next)}`})}
function toolEntryMarkup(){return `<section class="tool-entry-grid" aria-label="学习工具入口">
  <article class="tool-entry"><h2>Archify · 图谱与架构</h2><p class="tool-entry-kicker">把系统关系变成可验证、可点击的图</p><p>适合架构、工作流、序列、数据流和生命周期图。效果是关系可追踪，节点可以回到对应知识页。</p><div class="tool-entry-actions"><a class="tool-entry-primary" href="/?view=graph">打开关系图</a><a class="tool-entry-secondary" href="https://github.com/tt-a1i/archify" target="_blank" rel="noreferrer">官方 GitHub ↗</a></div></article>
  <article class="tool-entry"><h2>OpenMAIC · 互动课堂</h2><p class="tool-entry-kicker">把一个主题变成讲解、互动和练习</p><p>输入主题后生成课堂，可加入互动场景、测验、项目任务和反馈。模型调用前需要输入访问码。</p><div class="tool-entry-actions"><a class="tool-entry-primary" data-service-port="3100" href="/launch/openmaic?next=%2F" target="_blank" rel="noreferrer">打开互动课堂</a><a class="tool-entry-secondary" href="https://github.com/THU-MAIC/OpenMAIC" target="_blank" rel="noreferrer">官方 GitHub ↗</a></div></article>
  <article class="tool-entry"><h2>DeepTutor · 检索与学习</h2><p class="tool-entry-kicker">把资料、问答、记忆和复习放进一个工作区</p><p>先登录，再进入 Chat 或 Knowledge Bases。模型调用、检索、记忆和 Agent 接口都受账号保护。</p><div class="tool-entry-actions"><a class="tool-entry-primary" data-service-port="3782" href="/launch/deeptutor?next=%2Fchat" target="_blank" rel="noreferrer">打开学习工作区</a><a class="tool-entry-secondary" href="https://github.com/HKUDS/DeepTutor" target="_blank" rel="noreferrer">官方 GitHub ↗</a></div></article>
  <article class="tool-entry"><h2>Matt Skills · 工程协作</h2><p class="tool-entry-kicker">把对齐、设计、实现和验证变成可重复流程</p><p>提供 ask-matt、grill-with-docs、to-spec、TDD、代码审查和架构改进等技能，帮助模型先理解再修改。</p><div class="tool-entry-actions"><a class="tool-entry-primary" href="https://github.com/mattpocock/skills" target="_blank" rel="noreferrer">查看技能仓库 ↗</a><a class="tool-entry-secondary" href="/?path=%E7%9F%A5%E8%AF%86%E5%BA%93%E7%AE%A1%E7%90%86%2F%E7%BB%B4%E6%8A%A4%2F%E5%AD%A6%E4%B9%A0%E5%B7%A5%E5%85%B7%E4%BD%BF%E7%94%A8%E4%B8%8E%E8%B0%83%E7%94%A8%E6%88%90%E6%9C%AC.md">用法与成本</a></div></article>
</section>`}
function showView(view){
  state.view=view;
  $('#directory').style.display=view==='directory'?'block':'none';
  $('#reader').classList.toggle('open',view==='reader');
  $('#graph-view').classList.toggle('open',view==='graph');
  $('#directory-button').classList.toggle('active',view==='directory');
  $('#graph-button').classList.toggle('active',view==='graph');
}
function selectDirectory(domain='all',topic='all',push=true){
  state.navigation+=1;
  state.domain=domain;state.topic=topic;state.selected=null;showView('directory');renderDomains();renderDirectory();
  if(push)history.pushState({},'','/');window.scrollTo({top:0,behavior:'smooth'});
}
async function openNote(path,push=true){
  const navigation=++state.navigation;
  try{
    const note=await json('/api/note?path='+encodeURIComponent(path));
    if(navigation!==state.navigation)return;
    state.selected=note.path;showView('reader');$('#study-launch').hidden=note.path!=='知识库首页.md';
    $('#reader-context').innerHTML=`<span class="context-domain">${esc(note.category==='总览'?'首页':note.category)}</span><span class="context-sep">/</span><span>${esc(note.topic==='首页'?'入口':note.topic)}</span>`;
    $('#reader-title').textContent=note.title;$('#reader-sources').innerHTML=renderSources(note.sources);$('#reader-body').innerHTML=(note.path==='知识库首页.md'?toolEntryMarkup():'')+note.html;refreshServiceLinks();
    document.querySelectorAll('a[data-note]').forEach(a=>a.onclick=e=>{e.preventDefault();openNote(a.dataset.note)});
    if(window.renderMermaid)window.renderMermaid().catch(console.error);
    if(push)history.pushState({},'', '/?path='+encodeURIComponent(note.path));window.scrollTo({top:0,behavior:'smooth'});
  }catch(error){console.error(error)}
}
function launchStudy(kind){const topic=$('#study-topic').value.trim();if(!topic){$('#study-topic').focus();return}const encoded=encodeURIComponent(topic);const next=kind==='classroom'?`/?topic=${encoded}`:`/chat?prompt=${encoded}`;const url=`${kind==='classroom'?'/launch/openmaic':'/launch/deeptutor'}?next=${encodeURIComponent(next)}`;window.open(url,'_blank','noopener,noreferrer')}
function showGraph(push=true){state.navigation+=1;state.selected=null;state.query='';state.domain='all';state.topic='all';$('#search').value='';renderDomains();showView('graph');renderGraph();if(push)history.pushState({},'','/?view=graph');window.scrollTo({top:0,behavior:'smooth'});}
function renderNetworkGraph(){
  const svg=$('#graph'),mobile=window.matchMedia('(max-width:900px)').matches,W=mobile?720:1200,H=mobile?920:690,domains=ordered(new Set(state.notes.map(n=>n.category)));svg.innerHTML='';svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
  const positions=new Map(),topicPositions=new Map(),columns=3,cellW=W/columns,rows=Math.ceil(domains.length/columns),cellH=H/rows;
  domains.forEach((domain,di)=>{
    const col=di%columns,row=Math.floor(di/columns),cx=cellW*(col+.5),cy=cellH*(row+.5)+8;
    const group=state.notes.filter(n=>n.category===domain),topics=[...new Set(group.map(n=>n.topic))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const topicRadius=Math.min(cellW,cellH)*.29;
    topics.forEach((topic,ti)=>{
      const angle=-Math.PI/2+ti*2*Math.PI/Math.max(topics.length,1),tx=cx+Math.cos(angle)*topicRadius,ty=cy+Math.sin(angle)*topicRadius;
      topicPositions.set(`${domain}/${topic}`,{x:tx,y:ty,domain,topic});
      const notes=group.filter(n=>n.topic===topic),noteRadius=notes.length===1?0:Math.min(30,12+notes.length*2.2);
      notes.forEach((note,ni)=>{const noteAngle=-Math.PI/2+ni*2*Math.PI/Math.max(notes.length,1);positions.set(note.path,{x:tx+Math.cos(noteAngle)*noteRadius,y:ty+Math.sin(noteAngle)*noteRadius})});
    });
    const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x',cx);label.setAttribute('y',cy-cellH*.39);label.setAttribute('text-anchor','middle');label.classList.add('domain-label');label.textContent=`${domain==='总览'?'首页':domain} · ${group.length}`;svg.append(label);
  });
  const world=document.createElementNS('http://www.w3.org/2000/svg','g');world.id='graph-world';
  for(const edge of state.edges){const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)continue;const line=document.createElementNS('http://www.w3.org/2000/svg','line');for(const [k,v] of Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y}))line.setAttribute(k,v);line.classList.add('edge');line.dataset.source=edge.source;line.dataset.target=edge.target;world.append(line)}
  topicPositions.forEach(topic=>{const notes=state.notes.filter(n=>n.category===topic.domain&&n.topic===topic.topic);for(const note of notes){const pos=positions.get(note.path);if(!pos)continue;const line=document.createElementNS('http://www.w3.org/2000/svg','line');for(const [k,v] of Object.entries({x1:topic.x,y1:topic.y,x2:pos.x,y2:pos.y}))line.setAttribute(k,v);line.classList.add('topic-link');world.append(line)}const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.classList.add('topic-node');group.setAttribute('transform',`translate(${topic.x},${topic.y})`);group.onclick=()=>selectDirectory(topic.domain,topic.topic);const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('r',mobile?'7':'6');circle.setAttribute('stroke',colors[domains.indexOf(topic.domain)%colors.length]);const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=`${topic.topic}（${notes.length}篇）`;circle.append(title);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('y',mobile?'-12':'-10');label.setAttribute('text-anchor','middle');label.textContent=topic.topic;group.append(circle,label);world.append(group)});
  state.notes.forEach(note=>{const pos=positions.get(note.path);if(!pos)return;const group=document.createElementNS('http://www.w3.org/2000/svg','g');group.classList.add('node');group.setAttribute('transform',`translate(${pos.x},${pos.y})`);group.onclick=()=>openNote(note.path);group.onmouseenter=()=>document.querySelectorAll('.edge').forEach(edge=>{if(edge.dataset.source===note.path||edge.dataset.target===note.path)edge.classList.add('focused')});group.onmouseleave=()=>document.querySelectorAll('.edge.focused').forEach(edge=>edge.classList.remove('focused'));
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');circle.setAttribute('r',note.path===state.selected?'8':'5');circle.setAttribute('fill',colors[domains.indexOf(note.category)%colors.length]);const title=document.createElementNS('http://www.w3.org/2000/svg','title');title.textContent=note.title;circle.append(title);
    const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('y','-10');label.setAttribute('text-anchor','middle');label.textContent=note.title.length>22?note.title.slice(0,21)+'…':note.title;group.append(circle,label);world.append(group)});
  svg.append(world);applyGraphTransform();$('#legend').innerHTML=domains.map((d,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>${esc(d==='总览'?'首页':d)}</span>`).join('');
}
function svgEl(name,attrs={},label=''){const element=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([key,value])=>element.setAttribute(key,value));if(label)element.textContent=label;return element}
function graphCanvas(){const svg=$('#graph'),mobile=window.matchMedia('(max-width:900px)').matches,W=mobile?720:1200,H=mobile?920:690;svg.innerHTML='';svg.setAttribute('viewBox',`0 0 ${W} ${H}`);const defs=svgEl('defs');const marker=svgEl('marker',{id:'graph-arrow',viewBox:'0 0 10 10',refX:'8',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'});marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#6b867d'}));defs.append(marker);const world=svgEl('g',{id:'graph-world'});svg.append(defs,world);return {svg,world,W,H,mobile}}
function addBox(world,x,y,w,h,label,kind='',small='',target=''){const group=svgEl('g',{class:'diagram-group'});const box=svgEl('rect',{x,y,width:w,height:h,rx:7,class:`diagram-box ${kind}`});group.append(box,svgEl('text',{x:x+w/2,y:y+h/2-(small?8:0),class:'diagram-label'},label));if(small)group.append(svgEl('text',{x:x+w/2,y:y+h/2+14,class:'diagram-small'},small));if(target)group.onclick=()=>openNote(target);world.append(group);return group}
function addArrow(world,x1,y1,x2,y2,dashed=false){world.append(svgEl('line',{x1,y1,x2,y2,class:`diagram-edge${dashed?' dashed':''}`}))}
function renderFlowGraph(){const {world,W,H,mobile}=graphCanvas();const steps=[['问题','目标与约束','知识库首页.md'],['理解','查询与路由','工程知识/AI系统/模型与上下文/上下文工程是在有限预算内构造决策现场.md'],['召回','倒排 / 向量 / 图','工程知识/AI系统/知识与检索/RAG前沿：重排、自动优化与开放索引.md'],['验证','权限与证据','工程知识/AI系统/质量与运营/可靠生成需要结构、证据、拒答与回归.md'],['行动','模型与工具','工程知识/AI系统/Agent与工作流/构建可靠Agent应用.md'],['结果','答案或状态','工程知识/AI系统/模型与上下文/模型提出候选，系统定义正确性.md'],['反馈','评测与回归','工程知识/AI系统/质量与运营/Agent评测必须覆盖轨迹而不只看最终答案.md']];const pad=mobile?34:64,y=mobile?205:250,gap=(W-pad*2)/(steps.length-1),bw=mobile?92:132,bh=70;for(let i=0;i<steps.length-1;i++)addArrow(world,pad+i*gap+bw/2,y+bh/2,pad+(i+1)*gap-bw/2,y+bh/2);steps.forEach(([title,sub,target],i)=>addBox(world,pad+i*gap-bw/2,y,bw,bh,title,i===2?'primary':i===4?'secondary':'',sub,target));world.append(svgEl('text',{x:W/2,y:H*.7,class:'graph-note','text-anchor':'middle'},'每一步都产出可追踪的状态、证据和失败原因'));$('#legend').innerHTML='<span><i style="background:#328574"></i>证据获取</span><span><i style="background:#bc9d82"></i>模型与行动</span><span><i style="background:#a9bbb3"></i>系统边界</span>'}
function renderLearningGraph(){const {world,W,H,mobile}=graphCanvas();const steps=[['目标','要解决什么问题','知识库首页.md'],['理解','机制、边界与关系','工程知识/AI系统/Agent与工作流/Agent学习工具把资料变成可验证学习循环.md'],['预测','先说出你的判断','工程知识/AI系统/质量与运营/学习活动需要结果、轨迹与迁移证据.md'],['练习','最小实验或操作','知识库管理/维护/学习与复习方法.md'],['反馈','错误类型与证据','工程知识/AI系统/质量与运营/Agent评测必须覆盖轨迹而不只看最终答案.md'],['迁移','换场景重新使用','工程知识/AI系统/质量与运营/学习活动需要结果、轨迹与迁移证据.md']];const pad=mobile?34:64,y=mobile?205:250,gap=(W-pad*2)/(steps.length-1),bw=mobile?98:142,bh=72;for(let i=0;i<steps.length-1;i++)addArrow(world,pad+i*gap+bw/2,y+bh/2,pad+(i+1)*gap-bw/2,y+bh/2);steps.forEach(([title,sub,target],i)=>addBox(world,pad+i*gap-bw/2,y,bw,bh,title,i===0?'secondary':i===4?'primary':'',sub,target));world.append(svgEl('text',{x:W/2,y:H*.7,class:'graph-note','text-anchor':'middle'},'学习的终点是能解释、能操作、能迁移，而不是看完一页'));$('#legend').innerHTML='<span><i style="background:#bc9d82"></i>目标与迁移</span><span><i style="background:#328574"></i>证据与反馈</span><span><i style="background:#a9bbb3"></i>理解与练习</span>'}
function renderArchitectureGraph(){const {world,W,H,mobile}=graphCanvas();const layers=[['能力层','模型、Embedding、多模态','工程知识/AI系统/模型基础与训练/Transformer如何把序列建模成可扩展计算.md'],['知识层','RAG、记忆、结构化数据','工程知识/AI系统/知识与检索/RAG前沿：重排、自动优化与开放索引.md'],['编排层','工作流、Agent、状态','工程知识/AI系统/Agent与工作流/构建可靠Agent应用.md'],['工具层','API、MCP、A2A、业务系统','工程知识/AI系统/生态与选型/MCP连接能力，A2A委托任务.md'],['运行层','推理服务、队列、存储','工程知识/AI系统/推理服务与平台/推理服务的核心矛盾是延迟、吞吐、显存与质量.md'],['治理层','评测、追踪、安全、发布','工程知识/AI系统/质量与运营/Agent评测必须覆盖轨迹而不只看最终答案.md']];const x=mobile?80:180,w=mobile?560:840,top=62,gap=mobile?128:94,h=70;layers.forEach(([title,sub,target],i)=>{const y=top+i*gap;if(i<layers.length-1)addArrow(world,W/2,y+h,W/2,y+gap);addBox(world,x,y,w,h,title,i===2?'primary':i===5?'secondary':'',sub,target)});world.append(svgEl('text',{x:W/2,y:H-24,class:'graph-note','text-anchor':'middle'},'上层提出能力与决策，下层提供执行、资源和事实约束'));$('#legend').innerHTML='<span><i style="background:#328574"></i>决策编排</span><span><i style="background:#bc9d82"></i>质量与治理</span><span><i style="background:#a9bbb3"></i>能力与基础设施</span>'}
function renderQuadrantGraph(){const {world,W,H,mobile}=graphCanvas();const x=mobile?92:188,y=88,pw=mobile?536:824,ph=mobile?650:470;const midX=x+pw/2,midY=y+ph/2;world.append(svgEl('rect',{x,y,width:pw/2,height:ph/2,class:'quadrant-fill'}),svgEl('rect',{x:midX,y,width:pw/2,height:ph/2,class:'quadrant-fill alt'}),svgEl('rect',{x,y:midY,width:pw/2,height:ph/2,class:'quadrant-fill alt'}),svgEl('rect',{x:midX,y:midY,width:pw/2,height:ph/2,class:'quadrant-fill'}));world.append(svgEl('line',{x1:x,y1:midY,x2:x+pw,y2:midY,class:'axis-line'}),svgEl('line',{x1:midX,y1:y+ph,x2:midX,y2:y,class:'axis-line'}));world.append(svgEl('text',{x:x+pw/2,y:y+ph+43,class:'axis-label','text-anchor':'middle'},'单进程 / 显式路径  →  跨系统 / 动态协作'));world.append(svgEl('text',{x:x-52,y:y+ph/2,class:'axis-label','text-anchor':'middle',transform:`rotate(-90 ${x-52} ${y+ph/2})`},'显式状态  →  自适应状态'));[['本地确定性编排',x+18,y+25],['跨系统确定性协作',midX+18,y+25],['本地自适应决策',x+18,midY+25],['跨系统自适应协作',midX+18,midY+25]].forEach(([label,tx,ty])=>world.append(svgEl('text',{x:tx,y:ty,class:'quadrant-title'},label)));const points=[['工作流',.18,.18,'#0b705e'],['单 Agent',.62,.26,'#3f70a8'],['人工审批',.35,.58,'#a05b37'],['MCP',.72,.55,'#7862a3'],['A2A',.86,.82,'#9b4660']];points.forEach(([label,px,py,color])=>{const cx=x+pw*px,cy=y+ph*(1-py),g=svgEl('g',{class:'point-group'});g.append(svgEl('circle',{cx,cy,r:mobile?9:10,class:'point',fill:color}),svgEl('text',{x:cx+14,y:cy+5,class:'point-label'},label));world.append(g)});world.append(svgEl('text',{x:W/2,y:H-24,class:'graph-note','text-anchor':'middle'},'概念定位：用于理解职责边界，不表示性能、质量或成熟度排名'));$('#legend').innerHTML='<span><i style="background:#0b705e"></i>工作流</span><span><i style="background:#3f70a8"></i>Agent</span><span><i style="background:#7862a3"></i>协议</span><span><i style="background:#9b4660"></i>远程协作</span>'}
function renderGraph(){const meta={network:['知识关系','领域、主题与笔记之间的关联'],flow:['知识流通','从问题到证据、行动与反馈的路径'],learning:['学习循环','从目标、理解到练习、反馈与迁移'],architecture:['AI 系统架构','能力、知识、编排、工具、运行与治理的分层'],quadrant:['技术选型象限','用控制方式与协作范围理解常见组件的位置']};const [title,subtitle]=meta[state.graphMode]||meta.network;$('#graph-title').textContent=title;$('#graph-subtitle').textContent=subtitle;document.querySelectorAll('.visual-tab').forEach(button=>{const active=button.dataset.visual===state.graphMode;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active))});if(state.graphMode==='flow')renderFlowGraph();else if(state.graphMode==='learning')renderLearningGraph();else if(state.graphMode==='architecture')renderArchitectureGraph();else if(state.graphMode==='quadrant')renderQuadrantGraph();else renderNetworkGraph()}
function applyGraphTransform(){const world=$('#graph-world');if(world)world.setAttribute('transform',`translate(${state.pan.x} ${state.pan.y}) scale(${state.zoom})`)}
function bindGraph(){const svg=$('#graph');let drag=null;svg.onwheel=e=>{e.preventDefault();state.zoom=Math.max(.55,Math.min(2.5,state.zoom*(e.deltaY<0?1.1:.9)));applyGraphTransform()};svg.onpointerdown=e=>{if(e.target.closest('.node,.topic-node,.diagram-group,.point-group'))return;drag={x:e.clientX,y:e.clientY,px:state.pan.x,py:state.pan.y};svg.setPointerCapture(e.pointerId)};svg.onpointermove=e=>{if(!drag)return;state.pan={x:drag.px+e.clientX-drag.x,y:drag.py+e.clientY-drag.y};applyGraphTransform()};svg.onpointerup=()=>drag=null;$('#graph-zoom-in').onclick=()=>{state.zoom=Math.min(2.5,state.zoom*1.18);applyGraphTransform()};$('#graph-zoom-out').onclick=()=>{state.zoom=Math.max(.55,state.zoom/1.18);applyGraphTransform()};$('#graph-reset').onclick=()=>{state.zoom=1;state.pan={x:0,y:0};applyGraphTransform()}}
async function load(){
  const data=await json('/api/notes');state.notes=data.notes;state.edges=data.edges;renderDomains();renderDirectory();
  if(state.navigation!==0)return;
  const params=new URLSearchParams(location.search),path=params.get('path');
  if(path)await openNote(path,false);else if(params.get('view')==='graph')showGraph(false);else await openNote('知识库首页.md',false);
}
$('#home-button').onclick=()=>{state.query='';state.domain='all';state.topic='all';$('#search').value='';renderDomains();openNote('知识库首页.md')};
$('#directory-button').onclick=()=>selectDirectory(state.domain,state.topic);
$('#graph-button').onclick=()=>showGraph();
$('#back-button').onclick=()=>selectDirectory(state.domain,state.topic);
$('#search').oninput=e=>{state.navigation+=1;state.query=e.target.value;showView('directory');renderDirectory()};
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==$('#search')){e.preventDefault();$('#search').focus()}});
document.querySelectorAll('[data-sort]').forEach(button=>button.onclick=()=>{state.sort=button.dataset.sort;document.querySelectorAll('[data-sort]').forEach(x=>x.classList.toggle('active',x===button));renderDirectory()});
document.querySelectorAll('.visual-tab').forEach(button=>button.onclick=()=>{state.graphMode=button.dataset.visual;state.zoom=1;state.pan={x:0,y:0};renderGraph()});
$('#open-classroom').onclick=()=>launchStudy('classroom');$('#open-tutor').onclick=()=>launchStudy('tutor');
window.onpopstate=()=>{const params=new URLSearchParams(location.search),path=params.get('path');if(path)openNote(path,false);else if(params.get('view')==='graph')showGraph(false);else selectDirectory(state.domain,state.topic,false)};
bindGraph();load().catch(console.error);document.addEventListener('DOMContentLoaded',refreshServiceLinks);setInterval(async()=>{try{const data=await json('/api/notes');state.notes=data.notes;state.edges=data.edges;renderDomains();if(state.view==='directory')renderDirectory();if(state.view==='reader'&&state.selected)await openNote(state.selected,false);if(state.view==='graph')renderGraph()}catch(error){console.error(error)}},10000);
</script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "KnowledgeSite/1.0"

    @property
    def vault(self) -> Vault:
        return self.server.vault  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def send_bytes(self, payload: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # Clients can navigate away while a large response is in flight.
            pass

    def send_json(self, value: object, status: int = 200) -> None:
        self.send_bytes(json_bytes(value), "application/json; charset=utf-8", status)

    @property
    def site_password(self) -> str:
        return self.server.site_password  # type: ignore[attr-defined]

    def is_authenticated(self) -> bool:
        if is_local_client(self.client_address[0]):
            return True
        cookies = self.headers.get("Cookie", "")
        token = next(
            (part.strip().split("=", 1)[1] for part in cookies.split(";") if part.strip().startswith(f"{AUTH_COOKIE}=")),
            None,
        )
        return valid_auth_cookie(token, self.site_password)

    def redirect(self, location: str, status: int = 302) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def require_tool_access(self) -> bool:
        """Protect only launches that mint a session for a model-backed tool."""
        if self.is_authenticated():
            return True
        next_path = self.path if self.path.startswith("/") else "/projects"
        self.redirect("/auth/login?next=" + quote(next_path, safe="/?=&%"))
        return False

    def tool_host(self) -> str:
        """Keep the launch host equal to the host that set the tool cookie.

        A fixed public hostname is useful for generated links, but redirecting an
        IP request to that hostname loses the host-scoped cookie in the browser.
        Only known local addresses/names are accepted from the Host header;
        untrusted values fall back to the configured public host.
        """
        raw = self.headers.get("Host", "")
        try:
            requested = urlsplit("//" + raw).hostname or ""
        except ValueError:
            requested = ""
        requested = requested.rstrip(".").lower()
        known = {address.rstrip(".").lower() for address in local_addresses()}
        known.update({"localhost", socket.gethostname().rstrip(".").lower(), "macbook-pro-2.local"})
        if requested in known:
            return requested
        return public_host()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        canonical = canonical_root_location(self.path)
        if canonical is not None and canonical != self.path:
            self.redirect(canonical, 308)
            return
        if path == "/auth/login":
            self.send_bytes(LOGIN_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/auth/logout":
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie",
                f"{AUTH_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax",
            )
            self.end_headers()
            return
        if path in {"/", "/index.html"}:
            try:
                payload = PUBLIC_SITE.read_bytes()
            except OSError:
                self.send_json({"error": "site unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn", "/learn/", "/apps/learning/index.html"}:
            try:
                payload = PUBLIC_LEARNING.read_bytes()
            except OSError:
                self.send_json({"error": "learning center unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn/openmic", "/learn/openmic/"}:
            self.redirect("/learn/openmaic", 308)
            return
        if path in {"/learn/openmaic", "/learn/openmaic/", "/apps/learning/openmaic.html"}:
            try:
                payload = PUBLIC_OPENMAIC_LEARNING.read_bytes()
            except OSError:
                self.send_json({"error": "OpenMAIC learning page unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn/intuition", "/learn/intuition/", "/apps/learning/intuition.html"}:
            try:
                payload = PUBLIC_INTUITION.read_bytes()
            except OSError:
                self.send_json({"error": "intuition lesson unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn/transfer", "/learn/transfer/", "/apps/learning/transfer.html"}:
            try:
                payload = PUBLIC_TRANSFER.read_bytes()
            except OSError:
                self.send_json({"error": "transfer lesson unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn/history", "/learn/history/", "/apps/learning/history.html"}:
            try:
                payload = PUBLIC_HISTORY.read_bytes()
            except OSError:
                self.send_json({"error": "classroom history unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path == "/launch/openmaic":
            if not self.require_tool_access():
                return
            destination = safe_return_path(
                query.get("next", ["/"])[0],
                ("/", "/classroom", "/generation-preview"),
            )
            access_code = read_keychain_secret(OPENMAIC_ACCESS_SERVICE)
            if not access_code:
                self.send_json({"error": "OpenMAIC access is not configured"}, 503)
                return
            host = self.tool_host()
            self.send_response(303)
            self.send_header("Location", f"http://{host}:3100{destination}")
            self.send_header(
                "Set-Cookie",
                f"openmaic_access={openmaic_auth_cookie(access_code)}; "
                "Max-Age=604800; Path=/; HttpOnly; SameSite=Lax",
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/launch/deeptutor":
            if not self.require_tool_access():
                return
            destination = safe_return_path(
                query.get("next", ["/chat"])[0],
                ("/", "/chat", "/mastery", "/reading", "/knowledge-bases", "/notebooks", "/space"),
            )
            try:
                token = deeptutor_login_cookie(self.site_password)
            except RuntimeError:
                self.send_json({"error": "DeepTutor login is unavailable"}, 503)
                return
            host = self.tool_host()
            self.send_response(303)
            self.send_header("Location", f"http://{host}:3782{destination}")
            self.send_header(
                "Set-Cookie",
                f"dt_token={token}; Max-Age=86400; Path=/; HttpOnly; SameSite=Lax",
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path in {
            "/apps/agent-evaluation",
            "/apps/agent-evaluation/",
            "/apps/agent-evaluation/index.html",
        }:
            try:
                payload = PUBLIC_EVALUATION.read_bytes()
            except OSError:
                self.send_json({"error": "evaluation app unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path == "/projects/README.md":
            try:
                payload = PUBLIC_PROJECTS_README.read_bytes()
            except OSError:
                self.send_json({"error": "projects index unavailable"}, 503)
                return
            self.send_bytes(payload, "text/markdown; charset=utf-8")
            return
        if path in {
            "/projects/OpenMAIC/README-zh",
            "/projects/OpenMAIC/README-zh/",
            "/projects/OpenMAIC/README-zh.md",
        }:
            payload = render_project_markdown_page(
                PUBLIC_PROJECTS_ROOT / "OpenMAIC" / "README-zh.md",
                "OpenMAIC/README-zh.md",
                "OpenMAIC 中文项目说明",
            )
            if not payload:
                self.send_json({"error": "project document unavailable"}, 404)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {
            "/projects/DeepTutor/README-zh",
            "/projects/DeepTutor/README-zh/",
            "/projects/DeepTutor/README-zh.md",
        }:
            # DeepTutor 上游把简体中文说明放在 assets/README/README_CN.md，
            # 且其中的图片路径是相对该文件（../../assets/...）书写的。
            payload = render_project_markdown_page(
                PUBLIC_PROJECTS_ROOT / "DeepTutor" / "assets" / "README" / "README_CN.md",
                "DeepTutor/assets/README/README_CN.md",
                "DeepTutor 中文项目说明",
            )
            if not payload:
                self.send_json({"error": "project document unavailable"}, 404)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/projects", "/projects/"}:
            try:
                payload = PUBLIC_PROJECTS_INDEX.read_bytes()
            except OSError:
                self.send_json({"error": "projects index unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path.startswith("/projects/"):
            relative = unquote(path[len("/projects/") :])
            candidate = (PUBLIC_PROJECTS_ROOT / relative).resolve()
            if (
                candidate != PUBLIC_PROJECTS_ROOT
                and PUBLIC_PROJECTS_ROOT in candidate.parents
                and candidate.is_file()
                and not any(part.startswith(".") for part in candidate.relative_to(PUBLIC_PROJECTS_ROOT).parts)
                and candidate.suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".mjs", ".ts", ".tsx", ".css", ".html", ".sh", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
            ):
                try:
                    if candidate.suffix.lower() == ".md":
                        payload = render_project_markdown_page(
                            candidate,
                            candidate.relative_to(PUBLIC_PROJECTS_ROOT).as_posix(),
                            f"{candidate.stem} · {candidate.parent.name}",
                        )
                        content_type = "text/html; charset=utf-8"
                    else:
                        payload = candidate.read_bytes()
                        content_type = mimetypes.guess_type(candidate.name)[0] or "text/plain; charset=utf-8"
                except OSError:
                    self.send_json({"error": "project file unavailable"}, 404)
                    return
                if len(payload) > 4 * 1024 * 1024:
                    self.send_json({"error": "project file too large"}, 413)
                    return
                self.send_bytes(payload, content_type)
                return
        if path.startswith("/static/"):
            name = path[8:]
            if "/" in name or name.startswith("."):
                self.send_json({"error": "asset not found"}, 404)
                return
            file = (Path(__file__).resolve().parent / name).resolve()
            if file.parent != Path(__file__).resolve().parent or not file.is_file():
                self.send_json({"error": "asset not found"}, 404)
                return
            allowed = {".css", ".js", ".mjs", ".map"}
            if file.suffix.lower() not in allowed:
                self.send_json({"error": "asset not found"}, 404)
                return
            self.send_bytes(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            return
        if path == "/health":
            self.vault.refresh()
            bound_host = self.server.server_address[0]  # type: ignore[attr-defined]
            host = detect_host() if bound_host in {"0.0.0.0", "::"} else bound_host
            self.send_json({"ok": True, "host": host, "port": self.server.server_address[1], "notes": len(self.vault.notes)})  # type: ignore[attr-defined]
            return
        if path == "/api/learning/status":
            self.send_json(learning_services_status())
            return
        if path == "/api/learning/openmaic-jobs":
            self.send_json({"jobs": openmaic_generation_jobs()})
            return
        if path == "/api/access":
            self.send_json(
                {
                    "local_client": is_local_client(self.client_address[0]),
                    "knowledge_public": True,
                    "tool_launch_requires_auth": not self.is_authenticated(),
                }
            )
            return
        if path == "/api/notes":
            self.vault.refresh()
            notes = []
            for n in self.vault.notes.values():
                if not n["listed"]:
                    continue
                public = {k: v for k, v in n.items() if k not in {"body", "mtime", "listed"}}
                body = str(n["body"])
                public["excerpt"] = excerpt(body, str(n["title"]))
                public["search_text"] = body
                notes.append(public)
            listed_paths = {str(n["path"]) for n in notes}
            edges = [e for e in self.vault.edges() if e["source"] in listed_paths and e["target"] in listed_paths]
            self.send_json({"notes": notes, "edges": edges})
            return
        if path == "/api/note":
            self.vault.refresh()
            rel = query.get("path", [""])[0]
            note = self.vault.note(rel) or (self.vault.note(self.vault.resolve_note(rel) or "") if rel else None)
            if not note:
                self.send_json({"error": "note not found"}, 404)
                return
            public = {k: v for k, v in note.items() if k not in {"body", "mtime", "listed"}}
            rendered = render_markdown(str(note["body"]), self.vault, rel)
            public["html"] = re.sub(r"^<h1\b[^>]*>.*?</h1>\s*", "", rendered, count=1, flags=re.DOTALL)
            public["raw"] = str(note["body"])
            self.send_json(public)
            return
        if path == "/asset":
            rel = query.get("path", [""])[0]
            file = self.vault.safe_file(rel)
            if not file or file.suffix.lower() in {".md", ".html", ".py", ".json", ".plist", ".sh"}:
                self.send_json({"error": "asset not found"}, 404)
                return
            try:
                payload = file.read_bytes()
            except OSError:
                self.send_json({"error": "asset unavailable"}, 404)
                return
            if len(payload) > 20 * 1024 * 1024:
                self.send_json({"error": "asset too large"}, 413)
                return
            self.send_bytes(payload, mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            return
        self.send_json({"error": "not found"}, 404)

    def do_HEAD(self) -> None:  # noqa: N802
        """Serve the same headers as GET without writing a response body."""
        self.do_GET()

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Reject browser cross-origin preflights instead of enabling CORS implicitly."""
        self.send_json({"error": "cross-origin access is disabled"}, 403)

    def do_POST(self) -> None:  # noqa: N802
        if urlsplit(self.path).path != "/auth/login":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 16 * 1024)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "invalid request"}, 400)
            return
        password = str(body.get("password") or "")
        if not self.server.allow_login_attempt(self.client_address[0]):  # type: ignore[attr-defined]
            self.send_json({"error": "too many attempts"}, 429)
            return
        if not password or not hmac.compare_digest(password, self.site_password):
            self.send_json({"error": "invalid password"}, 401)
            return
        self.server.clear_login_attempts(self.client_address[0])  # type: ignore[attr-defined]
        self.send_response(204)
        self.send_header(
            "Set-Cookie",
            f"{AUTH_COOKIE}={auth_cookie(self.site_password)}; Max-Age={AUTH_MAX_AGE}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def detect_host() -> str:
    interfaces: list[str] = []
    try:
        route = subprocess.run(
            ["/sbin/route", "-n", "get", "default"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        ).stdout
        match = re.search(r"^\s*interface:\s*([A-Za-z0-9]+)\s*$", route, re.MULTILINE)
        if match:
            interfaces.append(match.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    interfaces.extend(["en0", "en1", "en7", "en8", "bridge0", "bridge100"])
    try:
        all_interfaces = subprocess.run(
            ["/sbin/ifconfig"], capture_output=True, text=True, timeout=2, check=False
        ).stdout
        interfaces.extend(re.findall(r"^([A-Za-z0-9]+):", all_interfaces, re.MULTILINE))
    except (OSError, subprocess.SubprocessError):
        pass
    for interface in dict.fromkeys(interfaces):
        try:
            output = subprocess.run(
                ["/sbin/ifconfig", interface], capture_output=True, text=True, timeout=2, check=False
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for value in re.findall(r"^\s*inet\s+([0-9.]+)\b", output, re.MULTILINE):
            if value and not value.startswith("127."):
                return value
    return "0.0.0.0"


def public_host() -> str:
    """Use an explicit public host when set; never trust a request Host header."""
    configured = os.environ.get("KNOWLEDGE_PUBLIC_HOST", "").strip()
    if configured and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", configured):
        return configured
    return detect_host()


class KnowledgeHTTPServer(ThreadingHTTPServer):
    """Threaded server with a small in-memory login throttle."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler, vault, site_password):
        super().__init__(address, handler)
        self.vault = vault
        self.site_password = site_password
        self._login_attempts: dict[str, list[float]] = {}
        self._login_lock = threading.Lock()

    def allow_login_attempt(self, address: str) -> bool:
        now = time.monotonic()
        with self._login_lock:
            attempts = [stamp for stamp in self._login_attempts.get(address, []) if now - stamp < AUTH_FAILURE_WINDOW]
            if len(attempts) >= AUTH_FAILURE_LIMIT:
                self._login_attempts[address] = attempts
                return False
            attempts.append(now)
            self._login_attempts[address] = attempts
            return True

    def clear_login_attempts(self, address: str) -> None:
        with self._login_lock:
            self._login_attempts.pop(address, None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Obsidian vault as a live knowledge site")
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT / "vault")
    parser.add_argument("--host", default=os.environ.get("KNOWLEDGE_HOST") or detect_host())
    parser.add_argument("--port", type=int, default=int(os.environ.get("KNOWLEDGE_PORT", "8787")))
    args = parser.parse_args()
    vault = Vault(args.root)
    server = KnowledgeHTTPServer((args.host, args.port), Handler, vault, load_site_password())
    print(f"Knowledge site serving {vault.root}", flush=True)
    display_host = detect_host() if args.host in {"0.0.0.0", "::"} else args.host
    print(f"Open from this Mac or LAN: http://{display_host}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
