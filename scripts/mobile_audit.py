import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

# 手机端布局审计：390x844 视口（iPhone 14/15），截首页/文章/论文三页，
# 每页输出横向溢出元素与 console 错误，供修复前后对比。

BASE = "http://127.0.0.1:18788"
W, H = 390, 844
OUT = str(Path(__file__).resolve().parents[1] / "audit-shots")

pages = [
    ("home", "/"),
    ("pano", "/?view=panorama"),
    ("papers", "/papers"),
    ("article", sys.argv[1] if len(sys.argv) > 1 else "/"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, path in pages:
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2, is_mobile=True, has_touch=True)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(BASE + path, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        page.screenshot(path=f"{OUT}/mobile-{name}.png", full_page=True)
        page.screenshot(path=f"{OUT}/mobile-{name}-viewport.png", full_page=False)
        probe = page.evaluate(
            """() => {
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
              /* KaTeX 的 MathML 副本是给屏幕阅读器的隐藏辅助内容，
                 KaTeX 自身 CSS 把它 clip 成 1x1 并绝对定位，矩形必然
                 超出视口，不是布局缺陷（layout_audit.py 同一先例）。 */
              if (el.closest('.katex-mathml')) return;
              /* SVG 子元素被 svg 视口默认裁切（overflow:hidden 是 SVG
                 的初始值），path/mi 等矩形超出不代表屏幕上有内容。 */
              if (el.ownerSVGElement) return;
              if (!inScroller) offenders.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0] : ''));
            });
            const sidebar = document.querySelector('.tk-sidebar');
            const sr = sidebar ? sidebar.getBoundingClientRect() : null;
            return {
              innerW: window.innerWidth,
              docScrollW: document.documentElement.scrollWidth,
              overflowOffenders: [...new Set(offenders)].slice(0, 8),
              sidebar: sr ? {x: Math.round(sr.x), y: Math.round(sr.y), w: Math.round(sr.width), h: Math.round(sr.height), pos: getComputedStyle(sidebar).position} : null,
              navCount: document.querySelectorAll('.tk-nav a').length,
            };
            }"""
        )
        print(name, json.dumps(probe, ensure_ascii=False))
        if errors:
            print(name, "CONSOLE_ERRORS:", errors[:5])
        page.close()
    browser.close()
