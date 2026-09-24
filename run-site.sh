#!/bin/sh
set -eu

repo="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python_bin="${KNOWLEDGE_PYTHON:-python3}"

exec "$python_bin" "$repo/site/server.py" \
  --root "$repo/vault" \
  --host "${KNOWLEDGE_HOST:-0.0.0.0}" \
  --port "${KNOWLEDGE_PORT:-8787}"
