#!/usr/bin/env python3
"""Build the arXiv registry from the sources the notes actually cite.

Why this exists: every knowledge page lists `sources:` in its frontmatter, and
44 of those are arXiv papers cited 72 times across the library. Until now the
site rendered them as bare URLs — a reader saw `https://arxiv.org/abs/1706.03762`
with no title, no authors, no year, and no indication that six different notes
depend on it. The citations were data the library already had and threw away.

This walks the vault, extracts every arXiv id, fetches the real metadata from
the arXiv API, and records which notes cite each paper. The output is versioned
because it is an asset: it lets the site show what a paper is and which
conclusions rest on it, and it can be diffed when a citation changes.

Two rules, both learned the hard way:

  - Never invent metadata. A paper whose id does not resolve is recorded with
    `metadata_missing` and no title. A plausible-looking wrong title is worse
    than an absent one, because nothing downstream can detect it.
  - Never write the registry from anything but a real request. The ids come
    from the vault; the titles come from arXiv; nothing comes from this script.

Usage:
    python3 scripts/fetch-papers.py              # refresh and write
    python3 scripts/fetch-papers.py --check      # verify, exit 1 if stale
    python3 scripts/fetch-papers.py --dry        # report without writing
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
REGISTRY = VAULT / "知识库管理" / "归档" / "来源" / "论文与项目" / "arxiv-registry.json"

ARXIV_ID = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.S)
SOURCE_LINE = re.compile(r'^\s*-\s*"?([^"\n]+)"?\s*$', re.M)

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
# arXiv asks for one request every three seconds and rejects long id lists.
BATCH = 20
THROTTLE_SECONDS = 3
USER_AGENT = "knowledge-site/1.0 (metadata registry; +https://arxiv.org/help/api)"


# A paper's own analysis page cites the paper it is about. That is not the
# library depending on it, so these are skipped — otherwise every deep read
# would appear as a citation and inflate its own evidence count.
ANALYSIS_DIR = "知识库管理/归档/来源/论文与项目/解析"


def cited_papers() -> dict[str, list[dict[str, str]]]:
    """Every arXiv id in the vault, with the notes that cite it."""
    found: dict[str, list[dict[str, str]]] = {}
    for path in sorted(VAULT.rglob("*.md")):
        if ANALYSIS_DIR in str(path.relative_to(VAULT)):
            continue
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            continue
        block = match.group(1)
        # Only the sources list, not the whole frontmatter: a body that happens
        # to mention an arXiv link is a reference in prose, not a citation this
        # note is built on.
        src = re.search(r"^sources:\s*\n((?:\s+-.*\n?)+)", block, re.M)
        if not src:
            continue
        rel = str(path.relative_to(VAULT))
        title = ""
        tm = re.search(r"^title:\s*(.+)$", block, re.M)
        if tm:
            title = tm.group(1).strip().strip('"').strip("'")
        parts = rel.split("/")
        domain = ""
        topic = ""
        if parts[0] == "工程知识" and len(parts) > 3:
            domain, topic = parts[1], parts[2]
        # Two kinds of citation, and they mean different things to a reader.
        #
        #   evidence  a durable knowledge page rests on this paper. The paper is
        #             the argument behind a claim, so losing it changes what the
        #             page is entitled to assert.
        #   survey    a research or maintenance page lists it among material it
        #             looked at. Nothing is asserted on the strength of it.
        #
        # They must not be counted together: "this paper supports six
        # conclusions" and "this paper appears in a reading list" are different
        # statements, and mixing them overstates the first.
        kind = "evidence" if parts[0] == "工程知识" else "survey"
        for line in SOURCE_LINE.findall(src.group(1)):
            am = ARXIV_ID.search(line)
            if not am:
                continue
            pid = am.group(1)
            found.setdefault(pid, []).append(
                {"path": rel, "title": title, "domain": domain, "topic": topic, "kind": kind}
            )
    for pid in found:
        found[pid].sort(key=lambda r: r["title"])
    return found


def fetch(ids: list[str]) -> tuple[dict[str, dict], list[str]]:
    """Fetch metadata for `ids`. Returns (papers, ids that did not resolve)."""
    papers: dict[str, dict] = {}
    unresolved: list[str] = []

    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        url = ("https://export.arxiv.org/api/query?id_list="
               + ",".join(chunk) + f"&max_results={len(chunk)}")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            # The whole batch failed. Record the ids as unresolved rather than
            # dropping them: a silent gap in the registry looks like a paper
            # that does not exist.
            print(f"  batch {start // BATCH + 1}: request failed ({error})", file=sys.stderr)
            unresolved.extend(chunk)
            continue

        try:
            root = ET.fromstring(payload)
        except ET.ParseError as error:
            print(f"  batch {start // BATCH + 1}: unparseable response ({error})", file=sys.stderr)
            unresolved.extend(chunk)
            continue

        seen = set()
        for entry in root.findall("a:entry", NS):
            raw = entry.findtext("a:id", "", NS)
            match = re.search(r"abs/(\d{4}\.\d{4,5})", raw)
            if not match:
                continue
            pid = match.group(1)
            seen.add(pid)
            primary = entry.find("arxiv:primary_category", NS)
            papers[pid] = {
                "id": pid,
                "title": " ".join(entry.findtext("a:title", "", NS).split()),
                "authors": [a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)],
                "published": entry.findtext("a:published", "", NS)[:10],
                "updated": entry.findtext("a:updated", "", NS)[:10],
                "summary": " ".join(entry.findtext("a:summary", "", NS).split()),
                "categories": [c.get("term") for c in entry.findall("a:category", NS)],
                "primary": primary.get("term") if primary is not None else "",
                "comment": " ".join((entry.findtext("arxiv:comment", "", NS) or "").split()),
                "url": f"https://arxiv.org/abs/{pid}",
            }
        unresolved.extend(cid for cid in chunk if cid not in seen)
        if start + BATCH < len(ids):
            time.sleep(THROTTLE_SECONDS)

    return papers, unresolved


def build() -> dict:
    citations = cited_papers()
    if not citations:
        raise SystemExit("no arXiv citations found in vault/ — is the vault present?")

    ids = sorted(citations)
    print(f"{len(ids)} paper(s) cited across the vault")
    papers, unresolved = fetch(ids)
    print(f"  resolved {len(papers)}/{len(ids)}"
          + (f", unresolved: {', '.join(unresolved)}" if unresolved else ""))

    merged: dict[str, dict] = {}
    for pid in ids:
        record = dict(papers.get(pid, {"id": pid, "url": f"https://arxiv.org/abs/{pid}"}))
        record["cited_by"] = citations[pid]
        if pid not in papers:
            # Kept, with the id and the citing notes, so the gap is visible on
            # the site instead of quietly disappearing.
            record["metadata_missing"] = True
        merged[pid] = record

    return {
        "generated": datetime.date.today().isoformat(),
        "source": "arXiv API (export.arxiv.org/api/query)",
        "note": ("Generated by scripts/fetch-papers.py — do not edit by hand. "
                 "Metadata comes from arXiv; what a paper is worth to this library "
                 "is recorded in its own entry under 知识库管理/归档/来源/论文与项目/."),
        "papers": merged,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="verify the registry matches the vault, write nothing")
    parser.add_argument("--dry", action="store_true", help="report without writing")
    args = parser.parse_args()

    if args.check:
        if not REGISTRY.is_file():
            print("registry missing — run scripts/fetch-papers.py")
            sys.exit(1)
        existing = json.loads(REGISTRY.read_text(encoding="utf-8"))["papers"]
        cited = cited_papers()
        problems = []
        for pid, refs in cited.items():
            if pid not in existing:
                problems.append(f"cited but not in the registry: {pid} ({refs[0]['title']})")
                continue
            recorded = {r["path"] for r in existing[pid].get("cited_by", [])}
            actual = {r["path"] for r in refs}
            for path in sorted(actual - recorded):
                problems.append(f"{pid}: cited by {path}, missing from the registry")
            for path in sorted(recorded - actual):
                problems.append(f"{pid}: registry says {path} cites it, but it does not")
        for pid in sorted(set(existing) - set(cited)):
            problems.append(f"in the registry but no longer cited: {pid}")
        if problems:
            print(f"paper registry is out of date ({len(problems)} problem(s)):")
            for problem in problems:
                print(f"  {problem}")
            print("\nrun: python3 scripts/fetch-papers.py")
            sys.exit(1)
        print(f"paper registry matches the vault ({len(cited)} paper(s))")
        return

    registry = build()
    if args.dry:
        print(f"would write {len(registry['papers'])} paper(s) to {REGISTRY.name}")
        return
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    citations = sum(len(p["cited_by"]) for p in registry["papers"].values())
    print(f"wrote {REGISTRY.relative_to(ROOT)} — "
          f"{len(registry['papers'])} paper(s), {citations} citation(s)")


if __name__ == "__main__":
    main()
