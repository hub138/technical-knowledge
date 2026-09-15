#!/bin/sh
# Full-page screenshot via chrome-headless-shell.
#
# Usage: shot.sh <url> <output.png> [width] [height]
#
# Always captures the entire page (--screenshot ignores the window height and
# expands to the full scroll height), so the result can be reviewed as a whole
# instead of a cropped viewport.
set -eu

url="$1"
out="$2"
width="${3:-1440}"
height="${4:-1000}"

chrome="${HOME}/.cache/puppeteer/chrome-headless-shell/mac_arm-142.0.7444.175/chrome-headless-shell-mac-arm64/chrome-headless-shell"
if [ ! -x "${chrome}" ]; then
  echo "chrome-headless-shell not found at ${chrome}" >&2
  exit 1
fi

profile="$(mktemp -d)"
trap 'rm -rf "${profile}"' EXIT

exec "${chrome}" \
  --headless \
  --disable-gpu \
  --hide-scrollbars \
  --no-first-run \
  --no-default-browser-check \
  --disable-extensions \
  --user-data-dir="${profile}" \
  --window-size="${width},${height}" \
  --virtual-time-budget=6000 \
  --screenshot="${out}" \
  "${url}"
