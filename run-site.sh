#!/bin/sh
set -eu

repo="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python_bin="/opt/homebrew/bin/python3"
if [ ! -x "$python_bin" ]; then python_bin="/usr/bin/python3"; fi

exec "$python_bin" "$repo/site/server.py" \
  --root "$repo/vault" \
  --host "${KNOWLEDGE_HOST:-0.0.0.0}" \
  --port "${KNOWLEDGE_PORT:-8787}"
