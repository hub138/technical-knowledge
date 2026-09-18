#!/bin/sh
# Vendor KaTeX into site/ so the paper pages can render formulas.
#
# Usage: scripts/vendor-katex.sh
#
# Why vendored and not a CDN: nothing on this site loads from a third-party
# host at read time. mermaid.min.js works the same way — a browser library
# that is downloaded once by a script and gitignored, because it is not ours
# to version and it would sit in history forever. A fresh clone therefore has
# to run this once (and scripts/vendor-mermaid.sh, if it does not already).
#
# What the paper pages need it for: the L2 standard asks for "at least one
# formula or algorithm and the key hyperparameters", and until this existed
# there was no way to write that down — a formula in a deep read came out as
# literal backslashes.
set -eu

VERSION="0.16.11"
BASE="https://cdn.jsdelivr.net/npm/katex@${VERSION}/dist"

site="$(cd "$(dirname "$0")/.." && pwd)/site"
fonts="${site}/fonts"

mkdir -p "${fonts}"

echo "KaTeX ${VERSION} → ${site}"

fetch() {
  url="$1"
  out="$2"
  # -f turns an HTTP error into a non-zero exit, so a 404 cannot leave a
  # zero-byte file behind that looks like a successful download.
  if ! curl -fsSL --retry 3 --max-time 120 "${url}" -o "${out}"; then
    echo "failed to download ${url}" >&2
    rm -f "${out}"
    exit 1
  fi
  printf '  %-42s %8s bytes\n' "$(basename "${out}")" "$(wc -c < "${out}" | tr -d ' ')"
}

fetch "${BASE}/katex.min.js" "${site}/katex.min.js"
fetch "${BASE}/katex.min.css" "${site}/katex.min.css"

# The stylesheet references these by name. Read the list out of the CSS rather
# than hardcoding it: a version bump that adds or drops a font would otherwise
# silently produce 404s for missing faces, which shows up as garbled math
# rather than as an error.
#
# Use grep -o, not sed. The minified CSS is a single line and sed's s///g
# still only prints one match per line — the first attempt here downloaded
# 1 font out of 20 and reported success.
list="$(grep -o 'fonts/[A-Za-z_0-9-]*\.woff2' "${site}/katex.min.css" | sort -u)"
if [ -z "${list}" ]; then
  echo "no font urls found in katex.min.css — did the archive layout change?" >&2
  exit 1
fi

count=0
for font in ${list}; do
  fetch "${BASE}/${font}" "${site}/${font}"
  count=$((count + 1))
done

echo "done: 2 files + ${count} font(s)"
echo
echo "Add these to .gitignore if they are not already there:"
echo "  /site/katex.min.js"
echo "  /site/katex.min.css"
echo "  /site/fonts/"
