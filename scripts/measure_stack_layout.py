# 量测八层气泡图（带控制台错误捕获与等待大圆出现）。
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
OUT = os.path.join(os.path.dirname(__file__), "..", "audit-shots")

JS = """
() => {
  const circles = [...document.querySelectorAll('.pano-grp > circle')].map(c => ({
    layer: c.parentNode.getAttribute('data-layer'),
    cx: +c.getAttribute('cx'), cy: +c.getAttribute('cy'), r: +c.getAttribute('r'),
  }));
  const pairs = [];
  for (let i = 0; i < circles.length; i++) {
    for (let j = i + 1; j < circles.length; j++) {
      const a = circles[i], b = circles[j];
      const dist = Math.hypot(a.cx - b.cx, a.cy - b.cy);
      pairs.push({ a: a.layer, b: b.layer, dist: +dist.toFixed(1),
                   sumR: +(a.r + b.r).toFixed(1), overlap: dist < a.r + b.r });
    }
  }
  const bbox = circles.length ? {
    minX: Math.min(...circles.map(c => c.cx - c.r)),
    maxX: Math.max(...circles.map(c => c.cx + c.r)),
    minY: Math.min(...circles.map(c => c.cy - c.r)),
    maxY: Math.max(...circles.map(c => c.cy + c.r)),
  } : null;
  return { count: circles.length, circles, overlapPairs: pairs.filter(p => p.overlap), bbox };
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path="/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
    )
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/?view=panorama&tab=stack", wait_until="load", timeout=30000)
    page.wait_for_selector(".pano-grp circle", timeout=15000)
    page.wait_for_timeout(800)
    data = page.evaluate(JS)
    with open(os.path.join(OUT, "stack-layout-measure.json"), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("console errors:", errors if errors else "none")
    print("overlap pairs:", json.dumps(data["overlapPairs"], ensure_ascii=False))
    print("bbox:", json.dumps({k: round(v, 1) for k, v in data["bbox"].items()}))
    for c in sorted(data["circles"], key=lambda x: -x["r"]):
        print(f"  layer {c['layer']}: cx={c['cx']:.1f} cy={c['cy']:.1f} r={c['r']:.1f}")
    browser.close()
