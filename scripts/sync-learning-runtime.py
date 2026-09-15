#!/usr/bin/env python3
"""Keep the local learning products aligned with the knowledge-site identity.

The plaintext password stays in macOS Keychain. DeepTutor receives only a
bcrypt hash in its private runtime directory.
"""

from __future__ import annotations

import json
import os
import pwd
import subprocess
import tempfile
from pathlib import Path

import bcrypt


AUTH_SERVICE = "knowledge-site-access"
DEEPTUTOR_HOME = Path(
    os.environ.get("DEEPTUTOR_HOME") or Path.home() / "Developer" / "knowledge-tools" / "DeepTutor"
)
SETTINGS = DEEPTUTOR_HOME / "data" / "user" / "settings"


def keychain_password() -> str:
    account = pwd.getpwuid(os.getuid()).pw_name
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            account,
            "-s",
            AUTH_SERVICE,
            "-w",
        ],
        capture_output=True,
        text=True,
        timeout=4,
        check=False,
    )
    password = result.stdout.strip() if result.returncode == 0 else ""
    if not password:
        raise SystemExit("Knowledge-site password is missing from macOS Keychain")
    return password


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def sync_auth(password: str) -> None:
    path = SETTINGS / "auth.json"
    value = read_json(path)
    current = str(value.get("password_hash") or "")
    try:
        matches = bool(current) and bcrypt.checkpw(password.encode(), current.encode())
    except ValueError:
        matches = False
    if not matches:
        value["password_hash"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    value.update(
        {
            "version": 1,
            "enabled": True,
            "username": "admin",
            "token_expire_hours": 24,
            "cookie_secure": False,
        }
    )
    atomic_json(path, value)


def sync_interface() -> None:
    path = SETTINGS / "interface.json"
    value = read_json(path)
    value.update(
        {
            "theme": value.get("theme") or "snow",
            "language": "zh",
            "response_language": "zh",
            "sidebar_description": "工程知识学习工作区",
            "setup_intro_shown": True,
        }
    )
    atomic_json(path, value)


def main() -> None:
    password = keychain_password()
    sync_auth(password)
    sync_interface()
    print("DeepTutor access and Chinese learning interface synchronized")


if __name__ == "__main__":
    main()
