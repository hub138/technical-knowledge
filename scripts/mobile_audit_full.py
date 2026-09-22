import json
from pathlib import Path
import urllib.parse
from playwright.sync_api import sync_playwright

# 全站手机端审计：390x844 视口逐页检查横向溢出、console 错误、关键控件几何，
# 并输出整页截图，供 design-craft 标准的人工核对与修复对比。

BASE = "http://127.0.0.1:28788"
W, H = 390, 844
OUT = Path(__file__).resolve().parents[1] / "audit-shots"

DOMAIN = urllib.parse.quote("后端系统：在并发、失败与变化中维持服务")
ARTICLE = urllib.parse.quote("工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理.md")

pages = [
    ("home", "/", 6000),
    ("graph", "/?view=graph", 9000),
    ("panorama", "/?view=panorama", 7000),
    ("domain", f"/?domain={DOMAIN}", 7000),
    ("article", f"/?path={ARTICLE}", 9000),
    ("papers", "/papers", 6000),
    ("sources", "/sources", 6000),
    ("projects", "/projects", 6000),
    ("agent-eval", "/apps/agent-evaluation/index.html", 7000),
]

PROBE = """() => {
  const offenders = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.right <= window.innerWidth + 1) return;
    let n = el.parentElement, inScroller = false;
    while (n) {
      const s = getComputedStyle(n);
      if (s.overflowX === 'auto' || s.overflowX === 'scroll') { inScroller = true; break; }
      n = n.parentElement;
    }
    if (el.closest('.katex-mathml')) return;
    if (el.ownerSVGElement) return;
    if (!inScroller) offenders.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : ''));
  });
  const smallTaps = [];
  document.querySelectorAll('button, a, [role="button"], input, select, summary').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.width < 32 || r.height < 24) {
      const label = (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 14);
      smallTaps.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : '') + '[' + label + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ']');
    }
  });
  return {
    innerW: window.innerWidth,
    docScrollW: document.documentElement.scrollWidth,
    overflowOffenders: [...new Set(offenders)].slice(0, 10),
    smallTaps: [...new Set(smallTaps)].slice(0, 12),
    fontBody: (() => { const p = document.querySelector('.article-body p, main p, .prose p'); return p ? getComputedStyle(p).fontSize + '/' + getComputedStyle(p).lineHeight : null; })(),
  };
}"""

errors_all = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, path, wait in pages:
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2, is_mobile=True, has_touch=True)
        errors = []
        page.on("console", lambda m: errors.append(m.text[:160]) if m.type == "error" else None)
        try:
            page.goto(BASE + path, wait_until="domcontentloaded")
            page.wait_for_timeout(wait)
            probe = page.evaluate(PROBE)
            print(name, json.dumps(probe, ensure_ascii=False))
            if errors:
                errors_all[name] = errors[:5]
            page.screenshot(path=str(OUT / f"m2-{name}.png"), full_page=True)
        except Exception as e:
            print(name, "AUDIT_ERROR:", str(e)[:200])
        page.close()
    browser.close()
if errors_all:
    print("CONSOLE_ERRORS:", json.dumps(errors_all, ensure_ascii=False))
