# 全量文章页程序化体检：横向溢出 / 占位符 / 空正文 / 破图 / 控制台错误 / KaTeX 失败
# 输出 audit-shots/vault-sweep.json，异常页单独列出供截图复核
import json
import os
import urllib.parse

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "audit-shots")
CACHE = "/data/code/AIagent/.cache-notes.json"

notes = json.load(open(CACHE))
notes = notes.get("notes") if isinstance(notes, dict) else notes
print("total notes:", len(notes))

results = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    for idx, note in enumerate(notes):
        rel = note["path"]
        path_param = urllib.parse.quote(rel, safe="/")
        row = {"path": rel, "problems": {}}
        for width in (375, 1440):
            ctx = browser.new_context(viewport={"width": width, "height": 900})
            page = ctx.new_page()
            errors = []
            page.on(
                "console",
                lambda m, e=errors: e.append("console: " + m.text[:200])
                if m.type == "error"
                else None,
            )
            page.on(
                "pageerror",
                lambda exc, e=errors: e.append("pageerror: " + str(exc)[:200]),
            )
            try:
                page.goto(f"{BASE}/?path={path_param}", wait_until="load", timeout=30000)
                page.wait_for_selector("#reader-body > *", timeout=15000)
                page.wait_for_timeout(400)
                overflow = page.evaluate(
                    "document.scrollingElement.scrollWidth - document.documentElement.clientWidth"
                )
                if overflow > 1:
                    row["problems"][f"overflow-{width}"] = f"{overflow}px"
                body_text = page.evaluate(
                    "(document.querySelector('.reader-body')||document.body).innerText"
                )
                if len(body_text.strip()) < 10:
                    row["problems"][f"empty-body-{width}"] = f"{len(body_text)}chars"
                if "{{" in body_text:
                    row["problems"]["placeholder"] = "found"
                bad_imgs = page.evaluate(
                    """() => [...document.querySelectorAll('.reader-body img')]
                          .filter(i => i.complete && i.naturalWidth === 0)
                          .map(i => (i.getAttribute('src')||'').slice(0,120))"""
                )
                if bad_imgs:
                    row["problems"][f"broken-img-{width}"] = bad_imgs
                katex_err = page.evaluate(
                    "document.querySelectorAll('.katex-error').length"
                )
                if katex_err:
                    row["problems"][f"katex-error-{width}"] = katex_err
                if errors:
                    row["problems"][f"js-error-{width}"] = errors[:3]
            except Exception as exc:
                row["problems"][f"load-fail-{width}"] = str(exc)[:200]
            ctx.close()
        if row["problems"]:
            results.append(row)
        if (idx + 1) % 50 == 0:
            print(f"progress {idx + 1}/{len(notes)}, flagged so far: {len(results)}")
    browser.close()

with open(os.path.join(OUT_DIR, "vault-sweep.json"), "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("flagged:", len(results))
for row in results[:40]:
    print(row["path"], "->", row["problems"])
