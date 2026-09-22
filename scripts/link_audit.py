#!/usr/bin/env python3
"""Find wikilinks that point at a file which is not there.

Why this exists: the vault is edited from Obsidian, where renaming a file
silently breaks every link into it. The site renders a broken link as
`<span class="unresolved">[[target]]</span>` — it does not 404, it just stops
being clickable, so nothing surfaces the damage. Pages got moved into `归档/`
and 27 references across the vault kept pointing at the old path.

None of the other checks can see this. `tests` exercises the server,
`contrast` measures text, `layout` measures geometry, `tokens` resolves
var() names. A link to a file that does not exist passes all of them.

    python3 scripts/link_audit.py            # report
    python3 scripts/link_audit.py --json

What counts as a failure: a `[[target]]` whose target is not a file in the
vault, where a file with the same basename exists somewhere else. That is the
signature of a move, and the fix is mechanical — point at the new path.

What does not: targets that never existed as files. The vault's own
documentation writes examples inside fenced code blocks (`[[相关页面]]` as a
frontmatter template, `[[KV缓存原理]]` as an illustration of two pages linking
each other). Those are prose about links, not links. They are reported as a
separate count so a reader can see they were considered, but they do not fail
the run — failing on them would make the check noise, and a noisy check gets
disabled.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"

# Hardcoded note links in the pages themselves: `/?path=<url-encoded>`, usually
# in a hand-written href. These are a second, separate way to link to a note,
# and nothing was watching them — the learning pages and the projects page had
# nine of them pointing at notes that had moved. A wikilink check does not see
# them at all, because the path is a URL query, not wiki markup.
#
# Only literals count. A path built from a template (`${esc(x.path)}`) comes
# from the note list at runtime, so it cannot go stale the same way.
HTML_PATH_RE = re.compile(r"""["']/?(?:\?|&)path=([^"'`]+)["']""")

# Same shape the server uses (site/server.py). Group 1 is the target.
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")

# Fenced code blocks are documentation, not links. The server's render_inline
# is never called on them, so they are not clickable on the page either.
FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)


def strip_fences(text: str) -> str:
    return FENCE_RE.sub("", text)


def collect() -> dict:
    files = {p.relative_to(VAULT).as_posix(): p for p in VAULT.rglob("*.md")}
    by_name: dict[str, list[str]] = {}
    for rel in files:
        by_name.setdefault(Path(rel).name, []).append(rel)

    broken: dict[str, dict] = {}
    unresolved: dict[str, list[str]] = {}

    for rel, path in files.items():
        text = path.read_text(encoding="utf-8")
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target:
                continue
            cands = [target] if target.endswith(".md") else [target, target + ".md"]
            if any(c in files for c in cands):
                continue

            # Was it in a fenced block? Then it is an example, not a link.
            # Check the offset against the stripped text.
            in_fence = m.start() >= len(strip_fences(text[: m.start()]))

            name = Path(target).name
            if not name.endswith(".md"):
                name += ".md"
            elsewhere = [r for r in by_name.get(name, [])]
            if elsewhere:
                entry = broken.setdefault(target, {"target": target, "real": elsewhere, "sources": []})
                if rel not in entry["sources"]:
                    entry["sources"].append(rel)
            else:
                key = target
                if in_fence:
                    key = target
                if key not in unresolved:
                    unresolved[key] = []
                if rel not in unresolved[key]:
                    unresolved[key].append(rel)

    # Second pass: hand-written ?path= links inside the pages.
    html_broken: dict[str, dict] = {}
    html_total = 0
    for page in ROOT.rglob("*.html"):
        if "node_modules" in page.parts:
            continue
        text = page.read_text(encoding="utf-8")
        for m in HTML_PATH_RE.finditer(text):
            raw = m.group(1)
            if "${" in raw:  # built at runtime from the note list
                continue
            html_total += 1
            target = urllib.parse.unquote(raw)
            if target in files:
                continue
            rel_page = page.relative_to(ROOT).as_posix()
            line = text.count("\n", 0, m.start()) + 1
            entry = html_broken.setdefault(target, {"target": target, "real": by_name.get(Path(target).name, []), "where": []})
            entry["where"].append(f"{rel_page}:{line}")

    return {
        "files": len(files),
        "broken": sorted(broken.values(), key=lambda e: e["target"]),
        "unresolved": {k: sorted(v) for k, v in sorted(unresolved.items())},
        "html_total": html_total,
        "html_broken": sorted(html_broken.values(), key=lambda e: e["target"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not VAULT.is_dir():
        print(f"vault not found at {VAULT}", file=sys.stderr)
        return 2

    data = collect()

    failed = bool(data["broken"]) or bool(data["html_broken"])

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1 if failed else 0

    print("link audit")
    print()
    print(f"  notes:        {data['files']}")

    broken = data["broken"]
    refs = sum(len(e["sources"]) for e in broken)

    if broken:
        print(f"  broken:       {len(broken)} target(s), {refs} reference(s)")
        print()
        print("  These point at a file that exists under a different path:")
        print()
        for e in broken:
            print(f"    {e['target']}")
            print(f"        now at: {', '.join(e['real'])}")
            for s in e["sources"]:
                print(f"        linked from: {s}")
        print()
        print("  Fix the path, or move the file back. A link that cannot resolve")
        print("  renders as plain text on the page — no error, it just stops working.")
    else:
        print("  broken:       none — every wikilink that names a real file resolves")

    html_broken = data["html_broken"]
    if html_broken:
        print()
        print(f"  page links:   {len(html_broken)} broken of {data['html_total']} hand-written ?path= link(s)")
        print()
        for e in html_broken:
            print(f"    {e['target']}")
            if e["real"]:
                print(f"        now at: {', '.join(e['real'])}")
            else:
                print("        no file with this name anywhere")
            for w in e["where"]:
                print(f"        linked from: {w}")
    else:
        print(f"  page links:   {data['html_total']} hand-written ?path= link(s), all resolve")

    unresolved = data["unresolved"]
    if unresolved:
        print()
        print(f"  {len(unresolved)} target(s) name no file anywhere (not a failure):")
        for t in unresolved:
            print(f"    {t}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
