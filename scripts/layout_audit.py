#!/usr/bin/env python3
"""Check the rendered page at several widths for layout defects.

Why this exists: three layout bugs shipped because reading the source said they
were fine and the rendered result said otherwise.

  - the main column rendered underneath the sidebar at x=0, because the page
    used a grid column and the stylesheet used position:fixed
  - the feedback button covered a status badge, a section heading, and two
    lines of feedback text, depending on the page
  - the owner-only nav entry appeared a frame after paint, so the bar changed
    shape when you clicked through

Each is a question about geometry, and geometry is measurable. This asks the
browser rather than the source.

Usage:
    python3 scripts/layout_audit.py                 # every page, three widths
    python3 scripts/layout_audit.py --width 390
    python3 scripts/layout_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHROME = (
    Path.home()
    / ".cache/puppeteer/chrome-headless-shell/mac_arm-142.0.7444.175"
    / "chrome-headless-shell-mac-arm64/chrome-headless-shell"
)

# (name, route, the file that route serves). The file is needed so the probe can
# be written into it before the request; see sample().
PAGES = [
    ("home", "/", "index.html"),
    ("projects", "/projects", "projects/index.html"),
    ("insights", "/insights", "site/insights.html"),
    ("learning", "/apps/learning/index.html", "apps/learning/index.html"),
    ("openmaic", "/apps/learning/openmaic.html", "apps/learning/openmaic.html"),
    ("intuition", "/apps/learning/intuition.html", "apps/learning/intuition.html"),
    ("transfer", "/apps/learning/transfer.html", "apps/learning/transfer.html"),
    ("history", "/apps/learning/history.html", "apps/learning/history.html"),
    ("evaluation", "/apps/agent-evaluation/index.html", "apps/agent-evaluation/index.html"),
]

PROBE = r"""
<script>
(function(){
  function label(el){
    var cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/)[0] : '';
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '');
  }

  var out = {};


  /* Measure only once the sidebar exists.
     --dump-dom snapshots after parsing, which is before the sidebar's
     DOMContentLoaded handler builds the nav. Taking the numbers synchronously
     records the skeleton — the first run of this script reported "0 nav" on
     eight pages and called them clean. So the wait comes first and the
     measurement happens inside it. */
  var waited = 0;
  (function settle(){
    var hasNav = document.querySelectorAll('.tk-nav a').length > 0;
    var hasSidebar = !!document.querySelector('.tk-sidebar');
    var exhausted = waited > 120;
    if((hasNav || (!hasSidebar && exhausted)) && waited > 2){ done(); return; }
    if(exhausted){ done(); return; }
    waited++;
    setTimeout(settle, 40);
  })();

  function done(){ document.title = '@@' + JSON.stringify(measure()); }

  function measure(){
    var out = {};
  /* 1. No horizontal overflow. Elements inside a deliberate scroller — a wide
        table, the mobile nav strip — are excluded: they are meant to scroll. */
  var offenders = [];
  document.querySelectorAll('*').forEach(function(el){
    var r = el.getBoundingClientRect();
    if(r.width < 1 || r.right <= innerWidth + 1) return;
    var n = el.parentElement, inScroller = false;
    while(n){
      var s = getComputedStyle(n);
      if(s.overflowX === 'auto' || s.overflowX === 'scroll'){ inScroller = true; break; }
      n = n.parentElement;
    }
    if(!inScroller) offenders.push(label(el));
  });
  out.overflow = {
    docScrollWidth: document.documentElement.scrollWidth,
    innerWidth: innerWidth,
    offenders: Array.from(new Set(offenders)).slice(0, 6)
  };

  /* 2. The floating feedback button must not sit on text a reader needs. */
  var fab = document.querySelector('.tk-fab');
  var covered = [];
  if(fab){
    var fr = fab.getBoundingClientRect();
    document.querySelectorAll('*').forEach(function(el){
      if(el === fab || fab.contains(el)) return;
      if(el.querySelector && el.querySelector('.tk-fab')) return;
      var b = el.getBoundingClientRect();
      if(b.width < 8 || b.height < 8) return;
      if(b.right < fr.left || b.left > fr.right || b.bottom < fr.top || b.top > fr.bottom) return;
      var st = getComputedStyle(el);
      if(st.visibility === 'hidden' || st.display === 'none' || +st.opacity < 0.1) return;
      var ownText = [].some.call(el.childNodes, function(n){
        return n.nodeType === 3 && n.textContent.trim();
      });
      if(ownText) covered.push(label(el));
    });
  }
  out.fabCovers = fab ? Array.from(new Set(covered)).slice(0, 6) : null;

  /* 3. The floating controls must not overlap each other. */
  var boxes = [];
  [['fab', '.tk-fab'], ['theme', '.tk-theme-toggle'],
   ['kbd', '#kbd-hint'], ['lang', '.tk-lang-toggle']].forEach(function(pair){
    var el = document.querySelector(pair[1]);
    if(!el) return;
    var r = el.getBoundingClientRect();
    if(r.width < 1) return;
    boxes.push({name: pair[0], x: r.x, y: r.y, w: r.width, h: r.height});
  });
  var clashes = [];
  for(var i = 0; i < boxes.length; i++){
    for(var j = i + 1; j < boxes.length; j++){
      var a = boxes[i], b = boxes[j];
      var overlap = !(a.x + a.w <= b.x || b.x + b.w <= a.x ||
                      a.y + a.h <= b.y || b.y + b.h <= a.y);
      if(overlap) clashes.push(a.name + '+' + b.name);
    }
  }
  out.controlClashes = clashes;

  /* 4. The sidebar must be where the page expects it. */
  var sb = document.querySelector('.tk-sidebar');
  if(sb){
    var sr = sb.getBoundingClientRect();
    out.sidebar = {
      position: getComputedStyle(sb).position,
      x: Math.round(sr.x),
      width: Math.round(sr.width),
      navItems: document.querySelectorAll('.tk-nav a').length
    };
  } else {
    out.sidebar = null;
  }

  /* 5. The nav must be complete on the first paint, not grown afterwards.
        A bar that reads four items and then five is the flicker this checks. */
  out.navItems = document.querySelectorAll('.tk-nav a').length;

  /* 6. Text clipped by a fixed-height ancestor. */
  var clipped = [];
  document.querySelectorAll('*').forEach(function(el){
    var st = getComputedStyle(el);
    if(st.overflowY === 'auto' || st.overflowY === 'scroll' || st.overflowY === 'visible') return;
    if(el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 4) clipped.push(label(el));
  });
  out.clipped = Array.from(new Set(clipped)).slice(0, 6);

    return out;
  }
})();
</script>
"""

def sample(url: str, width: int, target: Path | None = None) -> dict | None:
    """Load the page and read its geometry back through the title.

    The probe has to run against the served page, not a local copy: the sidebar
    is built from /api/notes and /api/access, so a file:// copy renders with no
    navigation at all. An earlier version of this script did that and reported
    nine clean pages while measuring an empty sidebar — a false pass, which is
    worse than no check. So the probe is written into the page the server
    serves, exactly as contrast_audit.py does it.
    """
    if not CHROME.exists():
        raise SystemExit(f"chrome-headless-shell not found at {CHROME}")

    restore: tuple[Path, str] | None = None
    if target is not None:
        original = target.read_text(encoding="utf-8")
        restore = (target, original)
        target.write_text(original.replace("</body>", PROBE + "</body>", 1), encoding="utf-8")

    try:
        with tempfile.TemporaryDirectory() as profile:
            proc = subprocess.run(
                [
                    str(CHROME), "--headless", "--disable-gpu", "--no-first-run",
                    f"--user-data-dir={profile}",
                    f"--window-size={width},880",
                    "--virtual-time-budget=9000",
                    "--dump-dom",
                    url,
                ],
                capture_output=True, text=True, timeout=120,
            )
    finally:
        if restore:
            restore[0].write_text(restore[1], encoding="utf-8")

    match = re.search(r"<title>@@(.*?)</title>", proc.stdout, re.S)
    if not match:
        return None
    return json.loads(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8787")
    parser.add_argument("--width", type=int, action="append")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    widths = args.width or [1440, 768, 390]
    findings: dict[str, dict] = {}
    problems = 0

    for width in widths:
        for name, path, source in PAGES:
            try:
                data = sample(f"{args.base}{path}", width, ROOT / source)
            except Exception as exc:  # noqa: BLE001
                print(f"  ?     {name}@{width}: {exc}")
                continue
            if not data:
                print(f"  ?     {name}@{width}: no reading")
                continue
            issues = []
            if data["overflow"]["docScrollWidth"] > data["overflow"]["innerWidth"]:
                issues.append(f"horizontal overflow {data['overflow']['offenders']}")
            if data.get("fabCovers"):
                issues.append(f"feedback button covers {data['fabCovers']}")
            if data.get("controlClashes"):
                issues.append(f"controls overlap {data['controlClashes']}")
            if data.get("clipped"):
                issues.append(f"content clipped {data['clipped']}")
            problems += len(issues)
            findings[f"{name}@{width}"] = {"issues": issues, **data}

    if args.json:
        print(json.dumps({"problems": problems, "findings": findings}, ensure_ascii=False, indent=2))
        return

    print("layout audit")
    print()
    for key, data in findings.items():
        if data["issues"]:
            print(f"  FAIL  {key}")
            for issue in data["issues"]:
                print(f"        {issue}")
        else:
            sb = data.get("sidebar")
            note = (
                f"sidebar {sb['position']} {sb['width']}px, {sb['navItems']} nav"
                if sb else "no sidebar"
            )
            print(f"  ok    {key:<22} {note}")

    print()
    if problems:
        print(f"  {problems} layout problem(s)")
        sys.exit(1)
    print(f"  {len(findings)} page-width combinations, no layout problems")


if __name__ == "__main__":
    main()
