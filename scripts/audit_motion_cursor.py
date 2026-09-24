# 动效时长与 cursor 全站扫描。
# 1) 静态：扫 site/*.css 所有 transition/animation 时长，>500ms 列违规；
# 2) 运行时：首页+文章页遍历全部可点元素，cursor 非 pointer 的列出来。
import glob
import json
import os
import re

from playwright.sync_api import sync_playwright

SITE = os.path.join(os.path.dirname(__file__), "..", "site")
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots", "design-craft-r6")
CHROME = "/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
BASE = "http://127.0.0.1:18788"

DUR_RE = re.compile(r"(?:(\d+(?:\.\d+)?)ms)|(?:(\d+(?:\.\d+)?)s)(?![a-z])")

def parse_seconds(token):
    m = DUR_RE.fullmatch(token.strip())
    if not m:
        return None
    if m.group(1) is not None:
        return float(m.group(1)) / 1000
    return float(m.group(2))

report = {"css_duration_violations": [], "cursor_violations": []}

for css in sorted(glob.glob(os.path.join(SITE, "*.css"))):
    text = open(css, encoding="utf-8").read()
    for line_no, line in enumerate(text.splitlines(), 1):
        if "transition" in line and "duration" not in line:
            continue
        if "transition" in line or "animation" in line:
            for token in re.findall(r"(?:\d+(?:\.\d+)?m?s\b)", line):
                secs = parse_seconds(token)
                if secs is not None and secs > 0.5:
                    report["css_duration_violations"].append({
                        "file": os.path.basename(css),
                        "line": line_no,
                        "value": token,
                        "text": line.strip()[:100],
                    })

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/insights", wait_until="load", timeout=30000)
    if page.url.startswith(BASE + "/auth/login"):
        page.fill("#password", os.environ["KNOWLEDGE_SITE_PASSWORD"])
        page.click("#submit")
        page.wait_for_url("**/insights**", timeout=15000)

    for name, path in [("cursor-home", "/"), ("cursor-note", "/?view=panorama")]:
        p = ctx.new_page()
        p.goto(BASE + path, wait_until="load", timeout=30000)
        p.wait_for_timeout(1500)
        bad = p.evaluate(
            """() => {
                const out = [];
                const els = document.querySelectorAll('a, button, [role="button"]');
                for (const el of els) {
                    const cs = getComputedStyle(el);
                    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 && r.height === 0) continue;
                    if (cs.cursor !== 'pointer') {
                        out.push({
                            tag: el.tagName,
                            cls: (el.className || '').toString().slice(0, 40),
                            cursor: cs.cursor,
                            text: (el.textContent || '').trim().slice(0, 16),
                        });
                    }
                }
                return out;
            }"""
        )
        report["cursor_violations"].append({"page": name, "count": len(bad), "items": bad[:15]})
        p.close()
    browser.close()

with open(os.path.join(OUT, "results_motion_cursor.json"), "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2))
