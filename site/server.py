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
WECOM_SERVICE = "knowledge-site-wecom"
FEEDBACK_MAX_CHARS = 4000
FEEDBACK_RATE_WINDOW = 60
FEEDBACK_RATE_LIMIT = 5
FEEDBACK_KINDS = ("bug", "confusing", "suggestion", "praise", "other")
VISIT_RETENTION_DAYS = 180
REPOSITORY_ROOT = Path(
    os.environ.get("KNOWLEDGE_REPOSITORY_ROOT") or Path(__file__).resolve().parents[1]
).resolve()
PUBLIC_SITE = REPOSITORY_ROOT / "index.html"
PUBLIC_PROJECTS_README = REPOSITORY_ROOT / "projects" / "README.md"
PUBLIC_PROJECTS_PAGE = REPOSITORY_ROOT / "projects" / "index.html"
PUBLIC_PROJECTS_ROOT = REPOSITORY_ROOT / "projects"
PUBLIC_EVALUATION = REPOSITORY_ROOT / "apps" / "agent-evaluation" / "index.html"
PUBLIC_INSIGHTS = REPOSITORY_ROOT / "site" / "insights.html"
# 反馈和访问记录落在这里。放在仓库内便于本机查看，但必须 gitignore ——
# 内容是访客数据，不该进版本库。
DATA_HOME = Path(
    os.environ.get("KNOWLEDGE_DATA_HOME") or REPOSITORY_ROOT / "data"
)
FEEDBACK_LOG = DATA_HOME / "feedback.jsonl"
VISIT_LOG = DATA_HOME / "visits.jsonl"
OPENMAIC_ACCESS_SERVICE = "knowledge-tools-model-access"
OPENMAIC_JOBS_ROOT = Path(
    os.environ.get("OPENMAIC_HOME") or Path.home() / "Developer" / "knowledge-tools" / "OpenMAIC"
) / "data" / "classroom-jobs"
OPENMAIC_CLASSROOMS_ROOT = OPENMAIC_JOBS_ROOT.parent / "classrooms"
DEEPTUTOR_HOME = Path(
    os.environ.get("DEEPTUTOR_HOME") or Path.home() / "Developer" / "knowledge-tools" / "DeepTutor"
)

# 学习中心的页面：多个 URL 指向同一份 HTML，方便旧链接和站内导航都能用。
# 集中成一张表，避免再加页面时只改一处、漏掉另一处（/learn 曾经整组丢失）。
LEARNING_PAGES: dict[str, Path] = {
    "/learn": REPOSITORY_ROOT / "apps" / "learning" / "index.html",
    "/learn/openmaic": REPOSITORY_ROOT / "apps" / "learning" / "openmaic.html",
    "/learn/intuition": REPOSITORY_ROOT / "apps" / "learning" / "intuition.html",
    "/learn/transfer": REPOSITORY_ROOT / "apps" / "learning" / "transfer.html",
    "/learn/history": REPOSITORY_ROOT / "apps" / "learning" / "history.html",
}


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
    """Read or create the shared LAN login password without putting it on disk."""
    account = _keychain_account()
    query = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", account, "-s", AUTH_SERVICE, "-w"],
        capture_output=True,
        text=True,
        timeout=4,
        check=False,
    )
    password = query.stdout.strip() if query.returncode == 0 else ""
    if password:
        return password
    password = secrets.token_urlsafe(18)
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


def local_addresses() -> set[str]:
    """Every address this machine answers on, whatever interface it arrived on.

    Enumerating a fixed list (en0/en1/bridge*) breaks the moment the machine is
    on a different interface — a USB or Thunderbolt adapter, a VPN tunnel, a
    tethered phone — and the operator gets locked out of their own /insights
    page. So: ask ifconfig which interfaces exist, then read all of them.
    """
    addresses = {"127.0.0.1", "::1"}
    interfaces = []
    try:
        listing = subprocess.run(
            ["/sbin/ifconfig", "-l"], capture_output=True, text=True, timeout=2, check=False
        ).stdout
        interfaces = listing.split()
    except (OSError, subprocess.SubprocessError):
        interfaces = []
    # Fall back to the usual names if `ifconfig -l` is unavailable.
    for name in interfaces or ("en0", "en1", "en2", "en3", "bridge0", "bridge100"):
        try:
            output = subprocess.run(
                ["/sbin/ifconfig", name], capture_output=True, text=True, timeout=2, check=False
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        addresses.update(re.findall(r"\binet6?\s+([0-9a-fA-F:.]+)", output))
    # `ifconfig` drops the address once an interface goes down; the loopback
    # answer and whatever the OS reports as the primary address are also us.
    addresses.add(detect_host())
    return {
        address
        for address in addresses
        if address and (not address.startswith("127.0.0.") or address in {"127.0.0.1", "::1"})
    }


def is_local_client(address: str) -> bool:
    normalized = address[7:] if address.startswith("::ffff:") else address
    if normalized in {"127.0.0.1", "::1"}:
        return True
    # Any 127.0.0.0/8 address is this machine talking to itself.
    if normalized.startswith("127."):
        return True
    return normalized in local_addresses()


LOGIN_HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>工程知识库 · 登录</title><style>
:root{color-scheme:light;--bg:#f3f5f2;--panel:#fff;--ink:#202826;--muted:#68736f;--line:#d9dfdb;--accent:#137766}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC",sans-serif}
main{width:min(420px,calc(100% - 32px));background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:30px;box-shadow:0 16px 40px #23302b14}h1{font-size:21px;margin:0 0 7px}p{color:var(--muted);margin:0 0 21px}label{display:block;font-size:13px;font-weight:600;margin-bottom:7px}input{width:100%;padding:12px 13px;border:1px solid var(--line);border-radius:7px;font:inherit;outline:0}input:focus{border-color:var(--accent);box-shadow:0 0 0 3px #13776620}button{width:100%;margin-top:16px;padding:11px 13px;border:0;border-radius:7px;background:var(--accent);color:white;font:600 14px inherit;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.error{min-height:24px;color:#ad3e4f;margin:13px 0 0;font-size:13px}
</style></head><body><main><h1>工程知识库</h1><p>此地址来自其他设备，请输入访问密码。</p><form id="form"><label for="password">访问密码</label><input id="password" type="password" autocomplete="current-password" autofocus required><button id="submit" type="submit">进入知识库</button><div class="error" id="error" role="alert"></div></form></main><script>
const next=new URLSearchParams(location.search).get('next')||'/';
/* `//evil.com` 以 '/' 开头，但它跳到别的站点。startsWith 挡不住，
   必须比 origin 与 pathname。 */
const safeNext=(()=>{try{const target=new URL(next,location.origin);
return target.origin===location.origin&&target.pathname.startsWith('/')
?target.pathname+target.search+target.hash:'/'}catch{return '/'}})();const form=document.querySelector('#form');const input=document.querySelector('#password');const button=document.querySelector('#submit');const error=document.querySelector('#error');
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


def truthy(value: object) -> bool:
    """Read a frontmatter flag. YAML already gives us real booleans; tolerate
    the quoted string forms too, since hand-written frontmatter is common."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "on", "1"}
    return bool(value)


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


# ── 反馈与访问记录 ────────────────────────────────────────────────────────
# 这是本服务唯一的写盘路径。ThreadingHTTPServer 会并发写同一个文件，
# 所以所有追加都要过这把锁：拼好完整一行再原子写入，避免读到半行。
_LOG_LOCK = threading.Lock()
_LOCAL_NAME_CACHE: dict[str, str] = {}


def _ensure_data_home() -> None:
    try:
        DATA_HOME.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _append_jsonl(path: Path, record: dict[str, object]) -> bool:
    """Append one JSON line. Returns False if the write failed."""
    _ensure_data_home()
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        with _LOG_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except OSError:
        return False
    return True


def _read_jsonl(path: Path, limit: int = 2000) -> list[dict[str, object]]:
    """Read recent records, newest last. Tolerates a truncated final line."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    records: list[dict[str, object]] = []
    for line in raw.splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def local_git_name() -> str:
    """The operator's git user.name, read once and cached.

    Browsers cannot read git config, so the only honest way to prefill a name
    for the person at this machine is to ask git on this machine.
    """
    if "name" not in _LOCAL_NAME_CACHE:
        name = ""
        try:
            result = subprocess.run(
                ["git", "config", "--get", "user.name"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
                cwd=str(REPOSITORY_ROOT),
            )
            if result.returncode == 0:
                name = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            name = ""
        _LOCAL_NAME_CACHE["name"] = name[:60]
    return _LOCAL_NAME_CACHE["name"]


_UA_BROWSER_RE = re.compile(r"(Edg|Chrome|Firefox|Safari|curl|python-requests|Wget)/?([\d.]+)?")
# 系统版本号在第一个括号里，但格式不统一：Mac/iPhone 用下划线（10_15_7），
# Windows 用点分（NT 10.0）。直接匹配 token，不要在前面加通配组去抢匹配。
_UA_OS_RE = re.compile(
    r"(Windows NT [\d.]+|Mac OS X [\d_.]+|Android [\d.]+|iPhone OS [\d_]+|Linux|X11)"
)
_BROWSER_LABELS = {"Edg": "Edge", "Chrome": "Chrome", "Firefox": "Firefox", "Safari": "Safari"}


def describe_agent(user_agent: str) -> str:
    """Turn a User-Agent into something readable for the insights table."""
    if not user_agent:
        return "未知"
    system = _UA_OS_RE.search(user_agent)
    # Safari 的版本号在 "Version/x.y" 里；UA 里的 "Safari/604" 是 WebKit 版本，
    # 直接取会把所有 Safari 都显示成 604。
    browser_name, browser_version = "", ""
    for pattern in (r"(Edg)/([\d.]+)", r"(Chrome)/([\d.]+)", r"(Firefox)/([\d.]+)"):
        match = re.search(pattern, user_agent)
        if match:
            browser_name, browser_version = match.group(1), match.group(2)
            break
    if not browser_name:
        safari = re.search(r"Version/([\d.]+).*Safari", user_agent)
        if safari:
            browser_name, browser_version = "Safari", safari.group(1)
        else:
            other = re.search(r"(Safari|curl|python-requests|Wget)/?([\d.]*)", user_agent)
            if other:
                browser_name, browser_version = other.group(1), other.group(2)
    label = _BROWSER_LABELS.get(browser_name, browser_name or "其他")
    if browser_version:
        label = f"{label} {browser_version.split('.')[0]}"
    if system:
        label += " · " + system.group(1).replace("_", ".")
    return label[:80]


def wecom_webhook_key() -> str:
    """Read the group-bot key from the Keychain. Never from a committed file."""
    return read_keychain_secret(WECOM_SERVICE)


def notify_wecom(summary: str) -> None:
    """Push a notification, but never let a failure affect the caller.

    Runs on a background thread from the request handler so a slow or down
    webhook cannot delay the feedback response.
    """
    key = wecom_webhook_key()
    if not key:
        return
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    payload = json_bytes({"msgtype": "text", "text": {"content": summary[:1900]}})
    request = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=6) as response:
            response.read()
    except (OSError, HTTPError, URLError) as error:
        # 通知失败不影响已经落盘的反馈，只记录日志。
        print(f"[wecom] notify failed: {error}", flush=True)


def learning_services_status() -> dict[str, object]:
    """Return capability state without exposing provider credentials.

    The home page and the learning pages show a status chip per tool; a missing
    or unconfigured provider downgrades that chip instead of failing the page.
    """
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


def openmaic_classroom_title(classroom_id: str) -> str:
    """Read the course title OpenMAIC stored for a generated classroom.

    The job record only keeps a preview of the raw request, so the human-facing
    title has to come from the classroom itself (`stage.name`, e.g.
    "RAG重排与混合检索").
    """
    if not classroom_id:
        return ""
    path = OPENMAIC_CLASSROOMS_ROOT / f"{classroom_id}.json"
    data = _read_json(path)
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    name = stage.get("name") if isinstance(stage, dict) else None
    return str(name).strip() if name else ""


def openmaic_job_topic(data: dict[str, object]) -> str:
    """Recover a short human-readable topic from the request preview.

    Fallback for jobs that produced no classroom, so a failed run still says
    what it was trying to build instead of showing only an opaque error.
    """
    summary = data.get("inputSummary")
    if not isinstance(summary, dict):
        return ""
    preview = str(summary.get("requirementPreview") or "").strip()
    if not preview:
        return ""
    # Requests are long and templated. Look for an explicit topic first, then
    # for the title that commonly follows "课堂：" ("...互动课堂：RAG 的演进...").
    for pattern in (
        r"主题[是为：:”\"']*\s*([^。；;\n]+)",
        r"课堂[：:]\s*([^。；;\n]+)",
    ):
        match = re.search(pattern, preview)
        if match:
            topic = match.group(1).strip(" “”\"'‘’、,")
            if topic:
                return topic[:60]
    return preview[:60]


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
        classroom_id = str(classroom_id) if classroom_id else ""
        title = openmaic_classroom_title(classroom_id) or openmaic_job_topic(data)
        try:
            updated_at = int(file.stat().st_mtime)
        except OSError:
            updated_at = 0
        jobs.append(
            {
                "id": job_id,
                "title": title,
                "status": str(data.get("status") or "unknown"),
                "step": str(data.get("step") or ""),
                "progress": data.get("progress"),
                "scenesGenerated": data.get("scenesGenerated"),
                "totalScenes": data.get("totalScenes"),
                "error": str(data.get("error") or ""),
                "classroomId": classroom_id,
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


class Vault:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.notes: dict[str, dict[str, object]] = {}
        self.by_stem: dict[str, list[str]] = {}
        self.refresh()

    def refresh(self) -> None:
        notes: dict[str, dict[str, object]] = {}
        for path in sorted(self.root.rglob("*.md")):
            if not path.is_file() or any(part.startswith(".") for part in path.relative_to(self.root).parts):
                continue
            rel = path.relative_to(self.root).as_posix()
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
            # 知识库管理记录的是维护方法、工具和变更日志，不是技术知识本身。
            # 它的文章照常可读，但不进图谱：图谱表达"工程知识之间怎么连"，
            # 混入维护资料会把领域间的真实关系淹掉。
            # 按 category 判定而不是只认 frontmatter，新增文章无需作者记得加字段。
            exclude_from_graph = truthy(front.get("exclude_from_graph")) or category == "知识库管理"
            notes[rel] = {
                "path": rel,
                "title": title,
                "category": category,
                "topic": topic,
                "exclude_from_graph": exclude_from_graph,
                "type": scalar(front.get("type"), "note"),
                "status": scalar(front.get("status"), "active"),
                "updated": scalar(front.get("updated"), ""),
                "review_after": scalar(front.get("review_after"), ""),
                "change_rate": scalar(front.get("change_rate"), ""),
                "confidence": scalar(front.get("confidence"), ""),
                "tags": tags,
                "sources": front.get("sources", []) if isinstance(front.get("sources", []), list) else [],
                "body": body,
                "mtime": path.stat().st_mtime_ns,
                "words": len(re.findall(r"\S+", body)),
                "listed": parts[0] in {"工程知识", "Clippings", "知识库管理"} or rel == "知识库首页.md",
            }
        self.notes = notes
        self.by_stem = {}
        for rel, note in notes.items():
            self.by_stem.setdefault(Path(rel).stem, []).append(rel)

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
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for rel, note in self.notes.items():
            body = str(note["body"])
            for match in WIKILINK_RE.finditer(body):
                target = self.resolve_note(match.group(1), rel)
                if target and target != rel and (rel, target) not in seen:
                    seen.add((rel, target))
                    result.append({"source": rel, "target": target})
        return result

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
            candidate = (Path(current).parent / src).as_posix()
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
    source = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, source)
    source = re.sub(r"`([^`]+)`", lambda m: token(f"<code>{html.escape(m.group(1))}</code>"), source)
    escaped = html.escape(source)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    for key, value in tokens.items():
        escaped = escaped.replace(html.escape(key), value)
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


class Handler(BaseHTTPRequestHandler):
    server_version = "KnowledgeSite/1.0"

    @property
    def vault(self) -> Vault:
        return self.server.vault  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def send_bytes(
        self, payload: bytes, content_type: str, status: int = 200, download: str = ""
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if download:
            # 中文文件名不能直接放进头（头是 latin-1），必须用 RFC 5987 的
            # filename* 形式；同时给一个 ASCII 的 filename 作为旧浏览器回退。
            # 纯中文标题会退化成只有扩展名，所以给个有意义的兜底名。
            ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", download).strip("_")
            if ascii_name in {"", ".md"}:
                ascii_name = "knowledge-note.md"
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"{ascii_name}\"; "
                f"filename*=UTF-8''{quote(download, safe='')}",
            )
        self.end_headers()
        self.wfile.write(payload)

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
        self.end_headers()

    def require_tool_access(self) -> bool:
        """Protect only launches that mint a session for a model-backed tool.

        Reading the knowledge base stays open; handing out a model credential
        (OpenMAIC access code, DeepTutor session) is what needs the password.
        """
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

    def require_access(self) -> bool:
        parsed = urlsplit(self.path)
        if parsed.path.startswith("/auth/") or self.is_authenticated():
            return True
        if parsed.path.startswith("/api/") or parsed.path == "/health":
            self.send_json({"error": "authentication required"}, 401)
        else:
            next_path = self.path if self.path.startswith("/") else "/"
            self.redirect("/auth/login?next=" + quote(next_path, safe="/?=&%"))
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
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
        if not self.require_access():
            return
        if path in {"/", "/index.html"}:
            try:
                payload = PUBLIC_SITE.read_bytes()
            except OSError:
                self.send_json({"error": "site unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path == "/apps/agent-evaluation/index.html":
            try:
                payload = PUBLIC_EVALUATION.read_bytes()
            except OSError:
                self.send_json({"error": "evaluation app unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/projects", "/projects/"}:
            # 项目入口有自己的一页（projects/index.html），它列出了工具、源码和用法。
            # 以前这里重定向到 总览/项目与工具.md —— 那篇笔记早已不存在，
            # 于是访问 /projects 得到 "note not found"。直接提供真实的页面。
            try:
                payload = PUBLIC_PROJECTS_PAGE.read_bytes()
            except OSError:
                self.send_json({"error": "projects page unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        # ---- 教学工具的启动入口 ----------------------------------------------
        # 这些入口会为工具签发一次会话（OpenMAIC 访问码 / DeepTutor 登录），
        # 所以要过站点密码；阅读知识库本身不需要。
        if path == "/launch/openmaic":
            if not self.require_tool_access():
                return
            destination = safe_return_path(
                query.get("next", ["/"])[0],
                # Keep this in step with OpenMAIC's top-level pages. An
                # unlisted path silently falls back to the tool homepage, so a
                # working page would appear to vanish instead of erroring.
                ("/", "/classroom", "/generation-preview", "/workbench", "/workspace", "/eval"),
            )
            access_code = read_keychain_secret(OPENMAIC_ACCESS_SERVICE)
            if not access_code:
                self.send_json({"error": "OpenMAIC access is not configured"}, 503)
                return
            self.send_response(303)
            self.send_header("Location", f"http://{self.tool_host()}:3100{destination}")
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
            self.send_response(303)
            self.send_header("Location", f"http://{self.tool_host()}:3782{destination}")
            self.send_header(
                "Set-Cookie",
                f"dt_token={token}; Max-Age=86400; Path=/; HttpOnly; SameSite=Lax",
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
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
        # ── 中台数据 ───────────────────────────────────────────────────────
        # 这是运营者自己的界面，不是知识库的一部分：它列出访客 IP 和谁说了
        # 什么。之前只走 require_access()，而那个判断把"持有站点密码的局域网
        # 用户"也算已认证 —— 等于把所有人的访问记录和反馈暴露给任何拿到密码
        # 的人。现在只认本机回环/本机网卡，密码不再能解锁它。
        # 聚合只在访问时计算。数据量是"一个人读知识库"的量级，
        # 预先建索引或缓存反而是多余的复杂度。
        if path == "/insights" or path.startswith("/api/insights/"):
            if not is_local_client(self.client_address[0]):
                self.send_json(
                    {"error": "insights is only available from this machine"}, 403
                )
                return
        if path == "/insights":
            try:
                payload = PUBLIC_INSIGHTS.read_bytes()
            except OSError:
                self.send_json({"error": "insights page unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path == "/api/insights/summary":
            self.send_json(insights_summary())
            return
        if path == "/api/insights/visitors":
            self.send_json({"visitors": insights_visitors()})
            return
        if path == "/api/insights/pages":
            self.send_json({"pages": insights_pages()})
            return
        if path == "/api/insights/feedback":
            self.send_json({"feedback": insights_feedback()})
            return
        if path.startswith("/projects/"):
            # 上游项目的 README 快照，供"查看技能说明""中文说明"这类链接直接读取。
            # 只放行项目目录下的 Markdown，且必须落在 projects/ 内，
            # 避免 ../ 之类的路径穿越读到仓库里的其他文件。
            rel = unquote(path[len("/projects/") :])
            candidate = (REPOSITORY_ROOT / "projects" / rel).resolve()
            projects_root = (REPOSITORY_ROOT / "projects").resolve()
            if (
                candidate.suffix.lower() not in {".md", ".markdown"}
                or projects_root not in candidate.parents
                or not candidate.is_file()
            ):
                self.send_json({"error": "project document not found"}, 404)
                return
            self.send_bytes(candidate.read_bytes(), "text/markdown; charset=utf-8")
            return
        # 学习中心的独立页面优先于下面的 /learn/* 笔记跳转：
        # /learn/openmaic 既有讲义页、也有对应笔记，讲义页才是导航要到达的地方。
        if path.rstrip("/") in LEARNING_PAGES or path in {
            "/apps/learning/index.html",
            "/apps/learning/openmaic.html",
            "/apps/learning/intuition.html",
            "/apps/learning/transfer.html",
            "/apps/learning/history.html",
        }:
            page = LEARNING_PAGES.get(path.rstrip("/")) or (
                REPOSITORY_ROOT / "apps" / "learning" / Path(path).name
            )
            try:
                payload = page.read_bytes()
            except OSError:
                self.send_json({"error": "learning page unavailable"}, 503)
                return
            self.send_bytes(payload, "text/html; charset=utf-8")
            return
        if path in {"/learn/openmic", "/learn/openmic/"}:
            self.redirect("/learn/openmaic", 308)
            return
        if path.startswith("/learn/"):
            # 其余 /learn/* 跳转到对应的知识笔记。
            # 用 vault 相对路径而非硬编码链接：这些文章位于 知识库管理/归档/ 下，
            # 归档整理时路径变过一次，硬编码就会静默失效。
            redirects = {
                "/learn/deeptutor": "知识库管理/归档/来源/论文与项目/DeepTutor多智能体学习伴侣.md",
                "/learn/matt-skills": "知识库管理/归档/来源/论文与项目/Matt Skills工程协作技能.md",
                "/learn/archify": "知识库管理/归档/来源/论文与项目/Archify可验证技术图谱.md",
            }
            rel = redirects.get(path)
            if not rel:
                self.send_json({"error": "not found"}, 404)
                return
            resolved = self.vault.resolve_note(rel)
            if not resolved:
                self.send_json({"error": "note not found"}, 404)
                return
            # Location 头必须是 latin-1：中文路径要先按 URL 规则编码，
            # 否则 send_header 抛 UnicodeEncodeError，请求会直接断开。
            self.redirect("/?path=" + quote(resolved, safe=""))
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
        if path == "/api/notes":
            self.vault.refresh()
            notes = []
            for n in self.vault.notes.values():
                if not n["listed"]:
                    continue
                public = {k: v for k, v in n.items() if k not in {"body", "mtime", "listed"}}
                body = str(n["body"])
                public["excerpt"] = excerpt(body, str(n["title"]))
                # The frontend searches over search_text and hashes it to detect
                # changes, so it stays in the payload until search moves server-side.
                public["search_text"] = body
                notes.append(public)
            # 图谱与"入链/延伸"的唯一事实源：在服务端一次收口。
            # 前端三个渲染器（关系网络、阅读页关系、目录）都只读这个结果，
            # 不再各自判断，否则迟早会像以前那样漏掉一处。
            graph_paths = {
                str(n["path"]) for n in notes if not n.get("exclude_from_graph")
            }
            edges = [
                e
                for e in self.vault.edges()
                if e["source"] in graph_paths and e["target"] in graph_paths
            ]
            self.send_json({"notes": notes, "edges": edges})
            return
        # 导出：给 curl/wget 这类没有 JS 的场景用。前端按钮走的是
        # /api/note 的 raw + Blob，不依赖这个接口，但保留它让链接可分享。
        if path == "/api/note/export":
            self.vault.refresh()
            rel = query.get("path", [""])[0]
            note = self.vault.note(rel) or (self.vault.note(self.vault.resolve_note(rel) or "") if rel else None)
            if not note:
                self.send_json({"error": "note not found"}, 404)
                return
            title = str(note["title"])
            payload = f"<!-- {title} · {note['updated']} -->\n\n".encode("utf-8") + str(note["body"]).encode("utf-8")
            self.send_bytes(
                payload,
                "text/markdown; charset=utf-8",
                download=f"{title}.md",
            )
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

    def read_json_body(self, limit: int) -> tuple[dict[str, object] | None, int]:
        """Read a JSON body. Returns (body, 0) or (None, http_status).

        The limit is enforced rather than silently truncating: a truncated body
        fails to parse and the caller reports a confusing 400 instead of 413.
        """
        try:
            declared = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, 400
        if declared > limit:
            return None, 413
        try:
            raw = self.rfile.read(declared) if declared else b""
            value = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None, 400
        if not isinstance(value, dict):
            return None, 400
        return value, 0

    def visitor_record(self, body: dict[str, object]) -> dict[str, object]:
        """Identify who is talking to us, using only what we can actually get.

        The browser cannot read git config, so the local operator's name comes
        from git on this machine and is only offered as a default when the
        request is genuinely local. A LAN visitor has to say who they are; we
        store what they type and never pretend it is verified.
        """
        address = self.client_address[0]
        local = is_local_client(address)
        agent = describe_agent(self.headers.get("User-Agent", ""))
        claimed = str(body.get("name") or "").strip()[:60]
        if claimed:
            name, source = claimed, "manual"
        elif local:
            name, source = local_git_name(), "git"
        else:
            name, source = "", "unknown"
        return {
            "ip": address,
            "host_kind": "local" if local else "lan",
            "agent": agent,
            "name": name,
            "name_source": source,
        }

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/auth/login":
            self.handle_login()
            return
        if not self.require_access():
            return
        if path == "/api/feedback":
            self.handle_feedback()
            return
        if path == "/api/visit":
            self.handle_visit()
            return
        if path == "/api/insights/feedback/status":
            # 改反馈状态也是运营者操作，同样只认本机。
            if not is_local_client(self.client_address[0]):
                self.send_json(
                    {"error": "insights is only available from this machine"}, 403
                )
                return
            self.handle_feedback_status()
            return
        self.send_json({"error": "not found"}, 404)

    def handle_login(self) -> None:
        body, error = self.read_json_body(16 * 1024)
        if body is None:
            self.send_json({"error": "invalid request"}, error)
            return
        password = str(body.get("password") or "")
        if not password or not hmac.compare_digest(password, self.site_password):
            self.send_json({"error": "invalid password"}, 401)
            return
        self.send_response(204)
        self.send_header(
            "Set-Cookie",
            f"{AUTH_COOKIE}={auth_cookie(self.site_password)}; Max-Age={AUTH_MAX_AGE}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def recent_feedback_count(self, address: str) -> int:
        cutoff = time.time() - FEEDBACK_RATE_WINDOW
        return sum(
            1
            for record in _read_jsonl(FEEDBACK_LOG, limit=200)
            if record.get("ip") == address and float(record.get("ts") or 0) >= cutoff
        )

    def handle_feedback(self) -> None:
        body, error = self.read_json_body((FEEDBACK_MAX_CHARS + 1024) * 4)
        if body is None:
            if error == 413:
                self.send_json(
                    {"error": f"反馈太长，请控制在 {FEEDBACK_MAX_CHARS} 字以内"}, 413
                )
            else:
                self.send_json({"error": "invalid request"}, error)
            return
        message = str(body.get("message") or "").strip()
        if not message:
            self.send_json({"error": "请先写下反馈内容"}, 400)
            return
        if len(message) > FEEDBACK_MAX_CHARS:
            self.send_json(
                {"error": f"反馈太长（{len(message)} 字），请控制在 {FEEDBACK_MAX_CHARS} 字以内"},
                413,
            )
            return
        kind = str(body.get("kind") or "other")
        if kind not in FEEDBACK_KINDS:
            kind = "other"
        # 只接受真实存在的文章路径，避免伪造或路径穿越写入无意义记录。
        rel = unquote(str(body.get("path") or "")).strip().lstrip("/")
        note = self.vault.note(rel) if rel else None
        if rel and not note:
            resolved = self.vault.resolve_note(rel)
            note = self.vault.note(resolved) if resolved else None
        visitor = self.visitor_record(body)
        if self.recent_feedback_count(visitor["ip"]) >= FEEDBACK_RATE_LIMIT:
            self.send_json({"error": "提交太频繁，请稍后再试"}, 429)
            return
        record = {
            "ts": time.time(),
            "kind": kind,
            "message": message,
            "path": str(note["path"]) if note else "",
            "title": str(note["title"]) if note else str(body.get("title") or "")[:120],
            "contact": str(body.get("contact") or "").strip()[:120],
            "status": "open",
            **visitor,
        }
        if not _append_jsonl(FEEDBACK_LOG, record):
            self.send_json({"error": "反馈保存失败，请稍后重试"}, 500)
            return
        kind_labels = {
            "bug": "内容有错",
            "confusing": "看不懂",
            "suggestion": "建议",
            "praise": "有用",
            "other": "其他",
        }
        summary = (
            f"【知识库反馈】{kind_labels.get(kind, kind)}"
            f"{' · ' + record['title'] if record['title'] else ''}\n"
            f"来自：{record['name'] or record['ip']}（{record['host_kind']}）\n"
            f"{message[:400]}"
        )
        threading.Thread(target=notify_wecom, args=(summary,), daemon=True).start()
        self.send_json({"ok": True, "message": "收到，谢谢反馈！"})

    def handle_visit(self) -> None:
        body, error = self.read_json_body(4 * 1024)
        if body is None:
            self.send_json({"error": "invalid request"}, error)
            return
        rel = unquote(str(body.get("path") or "")).strip().lstrip("/")
        note = self.vault.note(rel) if rel else None
        record = {
            "ts": time.time(),
            "path": str(note["path"]) if note else "",
            "title": str(note["title"]) if note else str(body.get("title") or "")[:120],
            "referrer": str(self.headers.get("Referer") or "")[:200],
            "screen": str(body.get("screen") or "")[:20],
            **self.visitor_record(body),
        }
        _append_jsonl(VISIT_LOG, record)
        self.send_json({"ok": True})

    def handle_feedback_status(self) -> None:
        body, error = self.read_json_body(4 * 1024)
        if body is None:
            self.send_json({"error": "invalid request"}, error)
            return
        target = str(body.get("ts") or "")
        status = str(body.get("status") or "")
        if status not in {"open", "read", "done"}:
            self.send_json({"error": "invalid status"}, 400)
            return
        records = _read_jsonl(FEEDBACK_LOG, limit=100000)
        changed = 0
        _ensure_data_home()
        try:
            with _LOG_LOCK:
                with FEEDBACK_LOG.open("w", encoding="utf-8") as handle:
                    for record in records:
                        if str(record.get("ts")) == target:
                            record["status"] = status
                            changed += 1
                        handle.write(
                            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                        )
        except OSError:
            self.send_json({"error": "更新失败"}, 500)
            return
        self.send_json({"ok": True, "changed": changed})


# ── 中台聚合 ──────────────────────────────────────────────────────────────
# 规模是"一个人读知识库"，所以在访问时现算即可。加缓存或索引只会
# 引入失效逻辑，换不来可感知的速度。


def _day_key(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _trim_visits(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Drop records past the retention window so the log cannot grow forever."""
    cutoff = time.time() - VISIT_RETENTION_DAYS * 86400
    return [r for r in records if float(r.get("ts") or 0) >= cutoff]


def insights_summary() -> dict[str, object]:
    visits = _trim_visits(_read_jsonl(VISIT_LOG, limit=100000))
    feedback = _read_jsonl(FEEDBACK_LOG, limit=100000)
    today = _day_key(time.time())
    visitors = {str(v.get("ip") or "?") for v in visits}
    return {
        "visits_total": len(visits),
        "visitors_total": len(visitors),
        "visits_today": sum(1 for v in visits if _day_key(float(v.get("ts") or 0)) == today),
        "feedback_total": len(feedback),
        "feedback_open": sum(1 for f in feedback if f.get("status") == "open"),
        "local_name": local_git_name(),
        "retention_days": VISIT_RETENTION_DAYS,
    }


def insights_visitors(limit: int = 60) -> list[dict[str, object]]:
    visits = _trim_visits(_read_jsonl(VISIT_LOG, limit=100000))
    grouped: dict[str, dict[str, object]] = {}
    for record in visits:
        ip = str(record.get("ip") or "?")
        entry = grouped.setdefault(
            ip,
            {
                "ip": ip,
                "host_kind": record.get("host_kind") or "lan",
                "agent": record.get("agent") or "未知",
                "name": "",
                "name_source": "unknown",
                "visits": 0,
                "first": float(record.get("ts") or 0),
                "last": 0.0,
                "pages": set(),
            },
        )
        entry["visits"] = int(entry["visits"]) + 1
        entry["last"] = max(float(entry["last"]), float(record.get("ts") or 0))
        entry["first"] = min(float(entry["first"]), float(record.get("ts") or 0))
        if record.get("name"):
            entry["name"] = record["name"]
            entry["name_source"] = record.get("name_source") or "manual"
        if record.get("path"):
            entry["pages"].add(str(record["path"]))
    result = []
    for entry in sorted(grouped.values(), key=lambda e: float(e["last"]), reverse=True)[:limit]:
        entry["pages"] = len(entry["pages"])
        entry["first"] = _day_key(float(entry["first"])) + " " + time.strftime(
            "%H:%M", time.localtime(float(entry["first"]))
        )
        entry["last"] = _day_key(float(entry["last"])) + " " + time.strftime(
            "%H:%M", time.localtime(float(entry["last"]))
        )
        result.append(entry)
    return result


def insights_pages(limit: int = 25) -> list[dict[str, object]]:
    visits = _trim_visits(_read_jsonl(VISIT_LOG, limit=100000))
    counts: dict[str, dict[str, object]] = {}
    for record in visits:
        path = str(record.get("path") or "")
        if not path:
            continue
        entry = counts.setdefault(
            path, {"path": path, "title": record.get("title") or path, "visits": 0}
        )
        entry["visits"] = int(entry["visits"]) + 1
    return sorted(counts.values(), key=lambda e: int(e["visits"]), reverse=True)[:limit]


def insights_feedback(limit: int = 200) -> list[dict[str, object]]:
    records = _read_jsonl(FEEDBACK_LOG, limit=100000)
    result = []
    for record in reversed(records[-limit:]):
        result.append(
            {
                "ts": record.get("ts"),
                "time": _day_key(float(record.get("ts") or 0))
                + " "
                + time.strftime("%H:%M", time.localtime(float(record.get("ts") or 0))),
                "kind": record.get("kind") or "other",
                "message": record.get("message") or "",
                "path": record.get("path") or "",
                "title": record.get("title") or "",
                "contact": record.get("contact") or "",
                "status": record.get("status") or "open",
                "name": record.get("name") or "",
                "host_kind": record.get("host_kind") or "lan",
                "ip": record.get("ip") or "",
                "agent": record.get("agent") or "",
            }
        )
    return result


def detect_host() -> str:
    for interface in ("en0", "en1"):
        value = os.popen(f"/sbin/ifconfig {interface} 2>/dev/null | awk '/inet / {{print $2; exit}}'").read().strip()
        if value and not value.startswith("127."):
            return value
    return "0.0.0.0"


def public_host() -> str:
    """Use an explicit public host when set; never trust a request Host header."""
    configured = os.environ.get("KNOWLEDGE_PUBLIC_HOST", "").strip()
    if configured and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", configured):
        return configured
    return detect_host()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Obsidian vault as a live knowledge site")
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT / "vault")
    parser.add_argument("--host", default=os.environ.get("KNOWLEDGE_HOST") or detect_host())
    parser.add_argument("--port", type=int, default=int(os.environ.get("KNOWLEDGE_PORT", "8787")))
    args = parser.parse_args()
    vault = Vault(args.root)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.vault = vault  # type: ignore[attr-defined]
    server.site_password = load_site_password()  # type: ignore[attr-defined]
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
