<div align="center">

# technical-knowledge

**A knowledge base that explains mechanisms, not conclusions — with the site that serves it.**

[![tests](https://img.shields.io/badge/tests-50%2F50-brightgreen?style=flat-square)](#validation)
[![a11y](https://img.shields.io/badge/contrast-18%2F18%20WCAG%20AA-brightgreen?style=flat-square)](#validation)
[![dependencies](https://img.shields.io/badge/runtime%20deps-none-blue?style=flat-square)](#design-notes)
[![python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square)](https://www.python.org/)
[![build](https://img.shields.io/badge/build%20step-none-lightgrey?style=flat-square)](#design-notes)
[![notes](https://img.shields.io/badge/notes-184-informational?style=flat-square)](#what-is-in-here)
[![license](https://img.shields.io/badge/license-see%20below-lightgrey?style=flat-square)](#license)

[简体中文](README.zh.md) · **English**

[Quick start](#quick-start) · [The site](#the-site) · [Design notes](#design-notes) · [Validation](#validation) · [Updating](#updating-the-knowledge) · [Deployment](#deployment)

</div>

---

184 engineering notes on AI systems, backend and distributed systems, data
systems, computer systems, and software construction — written to a fixed
structure so a reader can tell what a technology is *for*, not just what it is.

Every note answers four questions:

| | |
|---|---|
| **Context** | Why does this exist? What was stuck before it? |
| **Approach** | How does it work? What is the mechanism? |
| **Effect** | Which number moved, measured under what conditions? |
| **Trade-offs** | What does it cost? When is it the wrong choice? |

A performance claim without the data size, version and hardware it was measured
on is not a fact. Anything read online is a lead, not a source — it goes in only
after checking the official documentation, a paper, or a local run.

> **On language.** The notes are written in Chinese, because that is the
> language they were written in, and machine-translating an explanation of a
> mechanism produces something that reads fluently and is wrong. This README and
> the site interface are available in both languages.

---

## What is in here

```
vault/                         open directly in Obsidian
  工程知识/                     five domains, one note per engineering question
  知识库管理/                   sourcing, updating, quality and maintenance rules
  Clippings/                   raw clippings, kept verbatim
site/                          the site: one HTTP server, no runtime dependencies
apps/agent-evaluation/         in-house Agent evaluation: contract and prototype
packages/agent-foundation/     sessions, context, memory, recovery, evidence
projects/                      full upstream source snapshots, each with its licence
  archify/                     architecture, workflow and relation diagrams
  OpenMAIC/                    the interactive classroom runtime
  DeepTutor/                   retrieval, memory and study workspace
  mattpocock-skills/           engineering-collaboration Agent skills
```

## Quick start

```bash
./run-site.sh                  # serves http://localhost:8787
```

Open `vault/` in Obsidian to edit. The site reads the Markdown files directly —
save and refresh. No build step, no export.

## The site

| | |
|---|---|
| **Reading** | search, domain index, backlinks and sources on each note |
| **Graph** | relations between notes, plus system layers and a selection quadrant |
| **Learning** | guided paths into the classroom and tutor tools, topic pre-filled |
| **Evaluation** | the in-house Agent evaluation, kept apart from the upstream tools |
| **Visits & feedback** | an operator view visible only on this machine |

The interface is available in **Chinese (default) and English**; switch it from
the sidebar. The notes themselves stay in the language they were written in —
a note with no English version says so rather than pretending otherwise.

## Design notes

Three decisions shaped everything else.

**No build step, no runtime dependencies.** `site/server.py` is a single-file
Python standard-library HTTP server; `site/base.css` is one stylesheet driven by
design tokens; the only third-party asset is a vendored Mermaid. There is no
`npm install`, no bundler, and nothing to keep in sync.

**One source for one thing.** Navigation is defined once in `site/nav.js` and
rendered once by `site/shell.js`, shared by every page. That was not always
true: the site used to carry two parallel page systems, each with its own
navigation and its own sidebar renderer, and they drifted — an entry existed on
one side and not the other, and following it changed the layout. Merging them
removed 63 override rules that existed only to accommodate the duplicate.

**Evidence over assertion.** Claims in the notes carry their test conditions;
claims about the site carry a script:

| What | How |
|---|---|
| behaviour | `python3 -m unittest tests/test_site.py` — 50 tests |
| layout | `python3 scripts/layout_audit.py` — 27 page × width combinations |
| tokens | `python3 scripts/token_audit.py` — no unresolved `var()` |
| readability | `python3 scripts/contrast_audit.py` — WCAG AA, per page and theme |
| copy | `python3 scripts/copy_audit.py` — countable rules |
| translation | `python3 scripts/i18n_audit.py` — untranslated interface strings |

All of them at once:

```bash
python3 scripts/check_all.py          # five checks, one verdict
python3 scripts/check_all.py --fast   # skip the two that need a browser
```

## Validation

```bash
python3 -m unittest tests/test_site.py        # 50/50
python3 scripts/contrast_audit.py <url>#dark  # 18/18 page-theme combinations
python3 scripts/layout_audit.py              # 27/27 page-width combinations
python3 scripts/token_audit.py               # 0 undefined custom properties
python3 scripts/copy_audit.py                 # score 2 (lower is better)
python3 scripts/i18n_audit.py                 # untranslated interface strings
```

For anything visual the rendered page is the acceptance surface: confirm it with
full-page screenshots at desktop and mobile widths, not by reading the diff.

## Updating the knowledge

Stable principles and fast-moving product facts are kept apart. A new model, a
new protocol or a new paper is registered as a source first, then judged on
which notes it affects. Facts that change — version numbers, deprecation dates,
pricing, security posture — are checked against the official documentation, not
a second-hand summary.

A paper can show that a mechanism is worth trying. Only a local run with a
before-and-after shows that it works here.

One engineering question gets one note. When two notes answer the same question,
merge the cases, mechanism, costs and validation into the one that stays, then
delete the old entry — do not leave half an answer in each.

See `vault/知识库管理/方法/一篇知识怎么写.md` and `CONTEXT.md`.

## Deployment

Container deployment is covered by `DEPLOYMENT.md` and `docker-compose.yml`.

On a LAN, prefer `http://<host>.local:8787/`. The knowledge is publicly
readable; only launching a tool that mints a model session needs the site
password. The full trust boundary — which routes are open, which need the
password, and why — is written down in `DEPLOYMENT.md` and enforced by
`site/server.py`.

## Upstream projects

`projects/` holds full git-tracked source snapshots of four upstream projects,
each with its own licence, documentation and tests. Dependency directories,
build output, virtual environments, user data, logs and secrets are excluded;
follow each project's own README to rebuild.

## Contributing

Read `AGENTS.md` before adding or removing knowledge — it defines the checks
that must pass first (search for an existing note on the same question before
writing a new one). Run the validation commands above before proposing a change.

## License

The knowledge text and integration code in this repository are managed through
its commit history. Third-party projects under `projects/` remain governed by
their own LICENSE and THIRD_PARTY_NOTICES.

Do not put credentials, internal addresses, user data or material you are not
authorised to redistribute into the knowledge base, the graph, or a commit.
