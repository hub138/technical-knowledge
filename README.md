# technical-knowledge

**A knowledge base that explains mechanisms, not conclusions — with the site that serves it.**

[![tests](https://img.shields.io/badge/tests-50%2F50-brightgreen)](#validation)
[![a11y](https://img.shields.io/badge/contrast-18%2F18%20WCAG%20AA-brightgreen)](#validation)
[![dependencies](https://img.shields.io/badge/runtime%20deps-none-blue)](#design-notes)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-see%20below-lightgrey)](#license)

<sup>English · [中文](README.zh.md)</sup>

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
projects/                      full upstream source snapshots, licences included
  archify/                     architecture and flow diagrams
  OpenMAIC/                    interactive classroom runtime
  DeepTutor/                   retrieval, memory and study workspace
  mattpocock-skills/           engineering Agent skills
```

## Quick start

```bash
./run-site.sh                  # serves http://localhost:8787
```

Open `vault/` as an Obsidian vault to edit. The site reads the Markdown directly
— save a note and reload, there is no build step and no export.

## The site

| | |
|---|---|
| **Reader** | search, per-domain index, article view with backlinks and a source list |
| **Graph** | relations between notes, plus diagram views of system layers and trade-off quadrants |
| **Learning** | guided paths into the classroom and tutor tools, with the topic pre-filled |
| **Evaluation** | the in-house Agent evaluation project, tracked separately from upstream tools |
| **Visits & feedback** | a local-only operations view: who read what, and what they said |

The interface is available in **English (default) and Chinese**; switch from the
sidebar. Knowledge notes stay in the language they were written in — a
machine-translated explanation of a mechanism reads fluently and is wrong, so a
note without an English version says so rather than pretending.

## Design notes

Three decisions shape everything else.

**No build step, no runtime dependencies.** `site/server.py` is a single-file
Python standard-library HTTP server. `site/base.css` is one stylesheet driven by
93 design tokens. The only third-party asset is Mermaid, vendored. There is no
npm install, no bundler, and nothing to keep in sync.

**One source per fact.** The navigation is defined once, in `site/nav.js`, and
rendered once, in `site/shell.js`, for every page. This is deliberate: the site
previously had two page systems that each rendered their own sidebar from their
own copy of the navigation, and they drifted — one entry existed on one side and
not the other, and clicking between them changed the layout. Collapsing them
removed 63 override rules that existed only to reconcile the two.

**Evidence over assertion.** Claims in the notes carry their measurement
conditions. Claims about the site carry a script:

| What | How it is checked |
|---|---|
| Behaviour | `python3 -m unittest tests/test_site.py` — 50 tests |
| Layout | `python3 scripts/layout_audit.py` — 27 page-width combinations |
| Readability | `python3 scripts/contrast_audit.py` — WCAG AA per page × theme |
| Copy quality | `python3 scripts/copy_audit.py` — mechanical rubric |
| Translation coverage | `python3 scripts/i18n_audit.py` — untranslated UI strings |

## Validation

```bash
python3 -m unittest tests/test_site.py        # 50/50
python3 scripts/contrast_audit.py <url>#dark  # 18/18 page-theme combinations
python3 scripts/layout_audit.py              # 27/27 page-width combinations
python3 scripts/copy_audit.py                 # score 2 (lower is better)
python3 scripts/i18n_audit.py                 # untranslated UI strings
```

The rendered page is the acceptance surface for anything visual — changes are
verified with full-page screenshots at desktop and mobile widths, not by reading
the diff.

## Updating the knowledge

Stable principles and fast-moving product facts are stored separately. A new
model, protocol or paper is registered as a source first, then its impact on
existing notes is assessed. Version numbers, deprecation dates, prices and
security guidance are re-checked against official documentation rather than
second-hand summaries.

A paper can show that a mechanism is worth trying; only a task run locally with a
before-and-after comparison shows that it works here.

One engineering question gets one page. When two notes answer the same question,
the case, mechanism, cost and validation are merged into the survivor and the
duplicate is removed — not left half-written in both places.

See `vault/知识库管理/方法/一篇知识怎么写.md` and `CONTEXT.md`.

## Deployment

`DEPLOYMENT.md` and `docker-compose.yml` cover container deployment.

On a LAN, prefer `http://<host>.local:8787/`. Knowledge content is publicly
readable; only launching a tool that mints a model-backed session requires the
site password. The exact trust boundary — which routes are open, which are
gated, and why — is documented in `DEPLOYMENT.md` and enforced in
`site/server.py`.

## Upstream projects

`projects/` holds complete Git-tracked source snapshots of four upstream
projects, each with its own licence, documentation and tests. Dependency
directories, build output, virtual environments, user data, logs and secrets are
not tracked; install per each project's own README.

## Contributing

Read `AGENTS.md` before adding or moving knowledge — it defines the check that
must pass first (search for an existing page on the same question before writing
a new one). Run the validation commands above before proposing a change.

## License

Knowledge text and integration code in this repository are governed by the
commit history. Third-party projects under `projects/` remain under their own
LICENSE and THIRD_PARTY_NOTICES.

Do not commit credentials, internal addresses, user data or material you are not
licensed to redistribute into the vault, the graph or a commit.
