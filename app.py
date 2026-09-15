#!/usr/bin/env python3
"""Run the bundled technical-knowledge site from the repository root."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the technical knowledge vault")
    parser.add_argument("--host", default=os.environ.get("KNOWLEDGE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("KNOWLEDGE_PORT", "8787")))
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        str(REPOSITORY / "site" / "server.py"),
        "--root",
        str(REPOSITORY / "vault"),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.no_browser:
        command.append("--no-browser")
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
