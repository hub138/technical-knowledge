# Knowledge Editing

When adding, moving, merging, or deleting knowledge under `vault/工程知识/`, read `CONTEXT.md` and `vault/知识库管理/归档/知识点写作与教学输出规范.md` first. Knowledge is published to a public site, so also read `vault/知识库管理/归档/面向发布的知识写作文风规范.md` before writing any prose: no self-disclosure, no disclaimer-shaped boundary statements, and the opening paragraph must stand on its own because it becomes the public summary.

Before creating a page, search titles, headings, key terms, and wikilinks across `vault/工程知识/`. Inspect the site's domain graph and the direct relation graph of the nearest pages. Choose exactly one action: merge into the canonical page, extend an existing page with a genuinely different subproblem, or create a new page for a different engineering question.

A completed knowledge change has one stable domain/topic owner, explains problem, mechanism, effects, trade-offs, boundaries, and validation in beginner-readable language, and leaves no stale links or duplicate page answering the same question.

Validate knowledge changes with:

```bash
python3 -m unittest tests/test_site.py
python3 scripts/audit-knowledge-quality.py
python3 scripts/audit-writing-style.py
python3 scripts/review-knowledge-quality.py --as-of YYYY-MM-DD --json
git diff --check
```

For navigation, layout, graph, or interaction changes, also verify the live site with `chrome-headless-shell` at desktop and mobile sizes. The rendered website is the acceptance surface.
