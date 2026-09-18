#!/usr/bin/env python3
"""Build per-paper analysis entries from the papers' own abstracts.

Why this exists: the papers page listed metadata and nothing else, which made it
a bibliography. A paper is only useful once something has been extracted from it
— what problem it attacked, what it did, and what number moved. That extraction
is what L1 is in the tracking methodology (知识库管理/方法/论文怎么追踪怎么解析).

Where the content comes from, and where it does not:

  L0  metadata        arXiv API. Real, already fetched.
  L1  summary fields  derived from the paper's own abstract, which is quoted
                      verbatim in the entry so a reader can check the claim.
  L2  six modules     NOT generated here. A deep read is a person's or a
                      dedicated agent's job; producing one by summarising an
                      abstract would be fabricating the parts the abstract does
                      not contain (technical detail, ablations, limitations,
                      reproduction steps). Entries without an L2 say so.

The numbers in L1 are copied out of the abstract by pattern, never invented. If
an abstract contains no number, the entry has no "key result" and that absence
is visible — a made-up metric would be indistinguishable from a real one to
every reader downstream.

Usage:
    python3 scripts/build-paper-notes.py            # write
    python3 scripts/build-paper-notes.py --check    # verify, exit 1 if stale
    python3 scripts/build-paper-notes.py --dry
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = (ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
            / "arxiv-registry.json")
# One file per paper, next to the registry: they are edited by hand when someone
# does a real deep read, so they cannot live inside the generated JSON.
NOTES = ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目" / "解析"
# 中文标题：人手翻译、脚本校验（每篇必须有），见 scripts/paper-titles.py。
TITLES = pathlib.Path(__file__).resolve().parent / "paper-titles.json"
# L1 字段的中文对照，同样是人手翻译、脚本校验，见 scripts/paper-fields-zh.py。
FIELDS_ZH = pathlib.Path(__file__).resolve().parent / "paper-fields-zh.json"

# `2-4×`, `41.8 BLEU`, `1.5x`, `28.4`, `80%`
NUMBER = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:-|–|~|to)?\s*\d*(?:[.,]\d+)?\s*"
    r"(?:×|x\b|%|percent|BLEU|ROUGE|F1|points?|times))",
    re.I,
)
# The clause around a number usually names what it measures.
#
# 数字后面留 160 个字符，实测还是不够：「…improvements in model capacity with
# only minor losses in computational」正好在 "computational cost" 中间断掉。
# 后面按子句边界收口，所以这里给得宽一点，宁可多取再裁。
CLAUSE = re.compile(r"([^.]{0,160}?" + NUMBER.pattern + r"[^.]{0,160})", re.I)

# A result sentence usually says so.
RESULT_CUES = ("improve", "outperform", "achieve", "reduce", "increase", "faster",
               "speedup", "better", "higher", "lower", "gain", "match", "exceed",
               "提升", "降低", "达到")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def key_result(summary: str) -> str:
    """The single most useful measured result, or "" if none is stated.

    Returning "" is the right answer more often than it looks. The first version
    of this took the highest-scoring sentence containing a number, which
    produced things like "1 and 1.3 BLEU, respectively" — a real number with its
    subject stripped, and a sentence about "addressing these challenges" that
    happened to contain no metric at all. Both read as results and neither is
    one. A missing result is recoverable; a wrong one is not, because nothing
    downstream can tell it from a right one.

    So a candidate must clear three bars:
      - the number must survive with its unit (`2-4×`, `28.4 BLEU`, `80%`)
      - the sentence must say something moved (not just mention a figure)
      - the number must not be a bare list of deltas with no subject
    """
    scored: list[tuple[int, int, str]] = []
    for sentence in sentences(summary):
        match = NUMBER.search(sentence)
        if not match:
            continue
        number = match.group(1)
        # The number must carry a unit that measures a result. A bare count
        # ("up to trillion parameter models"), a year, or a table reference is
        # not a measurement — one of these slipped through and read as a result.
        if not re.search(r"×|x\b|%|percent|BLEU|ROUGE|F1|point|time|fold|speedup", number, re.I):
            continue
        # "trillion parameters" has no explicit number-unit pairing, so it
        # arrives as a word; require a digit to be present in the matched value.
        if not re.search(r"\d", number):
            continue
        lowered = sentence.lower()
        cue_hits = sum(1 for cue in RESULT_CUES if cue in lowered)
        if cue_hits == 0:
            continue
        # "1 and 1.3 BLEU, respectively" — a value list whose subject lives in
        # the previous sentence. Reject: the clause has no subject of its own.
        head = sentence[: match.start()].strip(" ,;(").lower()
        if len(head) < 25 or head.endswith((",", "and")):
            continue
        scored.append((cue_hits, len(sentence), sentence))

    if not scored:
        return ""
    scored.sort(key=lambda c: (-c[0], c[1]))

    # Prefer the clause around the number, but only if it still carries both a
    # subject and the metric; otherwise keep the whole sentence.
    #
    # 从句子中间切出来的片段不能直接用。实测踩过两次：
    #   - CLAUSE 的 {0,160} 会从词中间切，「Two interactive…」变成「wo interactive…」；
    #   - strip(" ,;") 会把切剩下的首字母一起吃掉，同一个词先是掉头再掉尾。
    # 所以先按词边界对齐，再用整句兜底；片段只在不破坏词完整、且真的带主语时才要。
    for _, _, sentence in scored:
        match = CLAUSE.search(sentence)
        if match:
            start, end = match.span(1)
            while start > 0 and not sentence[start - 1].isspace():
                start -= 1
            while end < len(sentence) and not sentence[end].isspace():
                end += 1
            # 离句末只剩一小截就直接吃到底。差的是「and 4.5x when using …」这种
            # 第二个数据点，砍掉等于把结果里一半的数字扔了（实测 GPTQ 那条
            # 只剩 A100 的 3.25x，A6000 的 4.5x 丢了）。
            if len(sentence) - end <= 80:
                end = len(sentence)
            clause = sentence[start:end].strip(" ,;")
            # 只在句子还有后半段时才需要收口；句子本来就到这儿结束的，
            # 再裁就是把已经完整的话截短（实测把两条完整的英文裁成了半句）。
            if len(clause) > 200 and end < len(sentence):
                cut = max(clause.rfind(", ", 0, 200), clause.rfind(" with ", 0, 200),
                          clause.rfind(" while ", 0, 200), clause.rfind("; ", 0, 200))
                if cut >= 60:
                    clause = clause[:cut].strip(" ,;")
            if len(clause) >= 45 and re.search(r"[a-zA-Z]{3}", clause) and clause[0].isupper():
                return clause
        if len(sentence) <= 300:
            return sentence
    return scored[0][2][:297] + "…"


def overview(summary: str) -> str:
    """One plain sentence: what the paper is about."""
    if not summary:
        return ""
    first = sentences(summary)[0]
    return first if len(first) <= 320 else first[:317] + "…"


def problem(summary: str) -> str:
    """The problem statement: the sentence that says what does not work today."""
    cues = ("however", "struggle", "problem", "challenge", "limit", "difficult",
            "expensive", "cannot", "fail", "bottleneck", "issue", "suffer")
    for sentence in sentences(summary):
        lowered = sentence.lower()
        if any(cue in lowered for cue in cues):
            return sentence if len(sentence) <= 300 else sentence[:297] + "…"
    return ""


def approach(summary: str) -> str:
    """What the paper does about it."""
    cues = ("we propose", "we present", "we introduce", "we build", "we develop",
            "this paper presents", "we describe", "we show", "our method",
            "we design", "we use")
    for sentence in sentences(summary):
        lowered = sentence.lower()
        if any(cue in lowered for cue in cues):
            return sentence if len(sentence) <= 320 else sentence[:317] + "…"
    return ""


def entry(pid: str, paper: dict) -> dict:
    summary = paper.get("summary", "")
    cited = paper.get("cited_by") or []
    evidence = [c for c in cited if c.get("kind") == "evidence"]
    return {
        "id": pid,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "published": paper.get("published", ""),
        "primary": paper.get("primary", ""),
        "url": paper.get("url", f"https://arxiv.org/abs/{pid}"),
        "abstract": summary,
        # L1, each field traceable to the abstract above.
        "overview": overview(summary),
        "problem": problem(summary),
        "approach": approach(summary),
        "key_result": key_result(summary),
        "cites_evidence": evidence,
        "cites_survey": [c for c in cited if c.get("kind") != "evidence"],
        # L2 lives in the per-paper markdown file, not here. The flag says
        # whether a real deep read exists, so the page can be honest about it.
        "has_deep_read": False,
    }


def read_deep_reads() -> dict[str, str]:
    """Body text of any hand-written deep read, keyed by arXiv id."""
    found: dict[str, str] = {}
    if not NOTES.is_dir():
        return found
    for path in sorted(NOTES.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not match:
            continue
        series = re.search(r"^arxiv:\s*[\"']?([\d.]+)", match.group(1), re.M)
        if series:
            found[series.group(1)] = match.group(2).strip()
    return found


def build() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    papers = registry["papers"]
    deep = read_deep_reads()
    try:
        titles = json.loads(TITLES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        titles = {}
    try:
        fields_zh = json.loads(FIELDS_ZH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fields_zh = {}

    entries = {}
    for pid, paper in papers.items():
        record = entry(pid, paper)
        # 中文标题和英文原标题并存：页面按当前语言选一个显示。
        # 论文标题是专有名词，切到英文时显示原名才是读者在别处看到的样子。
        record["title_zh"] = titles.get(pid, "")
        record["title_en"] = paper.get("title", "")
        # 中文 rendering 与英文原文并存，页面按语言取用。
        # 英文原文始终保留：它才是论文里的那句话，也是英文界面该显示的。
        zh = fields_zh.get(pid, {})
        record["problem_zh"] = zh.get("problem", "")
        record["approach_zh"] = zh.get("approach", "")
        record["result_zh"] = zh.get("result", "")
        if pid in deep:
            record["has_deep_read"] = True
            record["deep_read"] = deep[pid]
        entries[pid] = record

    with_result = sum(1 for e in entries.values() if e["key_result"])
    with_deep = sum(1 for e in entries.values() if e["has_deep_read"])
    without_zh = sum(1 for e in entries.values() if not e["title_zh"])
    untranslated = sum(
        1 for e in entries.values()
        if (e["problem"] and not e["problem_zh"])
        or (e["approach"] and not e["approach_zh"])
        or (e["key_result"] and not e["result_zh"])
    )
    return {
        "generated": datetime.date.today().isoformat(),
        "source": "arXiv abstracts; derived by scripts/build-paper-notes.py",
        "note": ("L1 fields are extracted from each paper's own abstract, which is "
                 "kept alongside them for checking. L2 deep reads are written by "
                 "hand into 归档/来源/论文与项目/解析/ and never generated, because "
                 "an abstract does not contain the technical detail, ablations, "
                 "limitations or reproduction steps a deep read must state."),
        "stats": {
            "papers": len(entries),
            "with_key_result": with_result,
            "with_deep_read": with_deep,
            "without_chinese_title": without_zh,
            "with_untranslated_field": untranslated,
        },
        "papers": entries,
    }


OUT = (ROOT / "vault" / "知识库管理" / "归档" / "来源" / "论文与项目"
       / "paper-notes.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()

    built = build()

    if args.check:
        if not OUT.is_file():
            print("paper notes missing — run scripts/build-paper-notes.py")
            sys.exit(1)
        current = json.loads(OUT.read_text(encoding="utf-8"))
        if current["papers"] != built["papers"]:
            stale = [
                pid for pid in built["papers"]
                if current["papers"].get(pid) != built["papers"][pid]
            ]
            gone = sorted(set(current["papers"]) - set(built["papers"]))
            print(f"paper notes are out of date ({len(stale)} changed, {len(gone)} removed)")
            for pid in stale[:10]:
                print(f"  {pid}")
            print("\nrun: python3 scripts/build-paper-notes.py")
            sys.exit(1)
        print(f"paper notes match the registry ({len(built['papers'])} paper(s))")
        return

    stats = built["stats"]
    print(f"{stats['papers']} paper(s)")
    print(f"  {stats['with_key_result']} have a measured result in the abstract")
    print(f"  {stats['with_deep_read']} have a hand-written deep read")
    if stats["without_chinese_title"]:
        print(f"  {stats['without_chinese_title']} still have no Chinese title")
    if stats["with_untranslated_field"]:
        print(f"  {stats['with_untranslated_field']} have an L1 field with no Chinese rendering")

    if args.dry:
        print(f"would write {OUT.name}")
        return
    OUT.write_text(json.dumps(built, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
