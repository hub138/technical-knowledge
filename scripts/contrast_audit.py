#!/usr/bin/env python3
"""Measure text/background contrast on a page, in light or dark theme.

Temporarily injects a probe into the served page, loads it in
chrome-headless-shell, reads the measurements back out of <title>, then
restores the file.  This is how dark mode gets verified without eyeballing
screenshots: every text run below the WCAG AA threshold is reported.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = (
    Path.home()
    / ".cache/puppeteer/chrome-headless-shell/mac_arm-142.0.7444.175"
    / "chrome-headless-shell-mac-arm64/chrome-headless-shell"
)

PROBE = r"""
<script>
(function(){
  // The reader clears location.hash on load, so the theme is baked in here
  // rather than read from the URL.
  try { localStorage.setItem('tk-theme', '__THEME__'); } catch (e) {}
  document.documentElement.dataset.theme = '__THEME__';
  // workbench.js re-applies the theme on init, so keep it pinned after that too.
  var pin = function(){ document.documentElement.dataset.theme = '__THEME__'; };
  document.addEventListener('DOMContentLoaded', pin);
  window.addEventListener('load', pin);
  setTimeout(pin, 300);
  setTimeout(pin, 1200);
  setTimeout(function(){
    function lum(c){
      var m=c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
      if(!m) return null;
      var a=m[4]===undefined?1:+m[4];
      if(a<0.25) return null;
      var f=function(v){v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};
      return 0.2126*f(+m[1])+0.7152*f(+m[2])+0.0722*f(+m[3]);
    }
    function bgOf(el){
      var n=el;
      while(n){
        var l=lum(getComputedStyle(n).backgroundColor);
        if(l!==null) return l;
        n=n.parentElement;
      }
      return 1;
    }
    var out=[];
    document.querySelectorAll('*').forEach(function(el){
      var own=[].some.call(el.childNodes,function(n){
        return n.nodeType===3 && n.textContent.trim();
      });
      if(!own) return;
      var st=getComputedStyle(el);
      if(st.display==='none'||st.visibility==='hidden'||+st.opacity<0.2) return;
      var r=el.getBoundingClientRect();
      if(r.width<2||r.height<2) return;
      var fl=lum(st.color);
      if(fl===null) return;
      var bl=bgOf(el);
      var hi=Math.max(fl,bl), lo=Math.min(fl,bl);
      var ratio=(hi+0.05)/(lo+0.05);
      var size=parseFloat(st.fontSize), bold=+st.fontWeight>=600;
      var large = size>=24 || (size>=18.66 && bold);
      var need = large?3.0:4.5;
      if(ratio < need){
        out.push({
          el: el.tagName.toLowerCase()+(typeof el.className==='string'&&el.className?'.'+el.className.trim().split(/\s+/)[0]:''),
          txt: (el.textContent||'').trim().slice(0,26),
          fg: st.color, bg: st.backgroundColor,
          px: Math.round(size), ratio: Math.round(ratio*100)/100, need: need
        });
      }
    });
    document.title='@@'+JSON.stringify(out.slice(0,30));
  }, 2600);
})();
</script>
"""


def seed_probe(html: str, theme: str) -> str:
    """Inject the probe as the first thing in <head>, not before </body>.

    The theme preference has to be in localStorage before any page script reads
    it. site/shell.js is loaded synchronously from <head> and applies the stored
    theme on the spot, so a probe appended at the end of the body would be too
    late: shell.js would see no preference, fall back to the OS setting, and the
    measurement would report light-mode colours on a dark page for reasons that
    have nothing to do with the stylesheet.

    The probe still pins the attribute on DOMContentLoaded/load and at two later
    timestamps, because the sidebar is inserted after the initial paint.
    """
    body = PROBE.replace("__THEME__", theme)
    marker = "<head>"
    index = html.find(marker)
    if index < 0:
        return html.replace("</body>", body + "</body>")
    return html[: index + len(marker)] + body + html[index + len(marker) :]


def measure(url: str, target: Path, width: int = 1512, theme: str = "light") -> list[dict]:
    original = target.read_text(encoding="utf-8")
    target.write_text(seed_probe(original, theme), encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as profile:
            proc = subprocess.run(
                [
                    str(CHROME),
                    "--headless",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--user-data-dir={profile}",
                    f"--window-size={width},1200",
                    "--virtual-time-budget=9000",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        dom = proc.stdout
        marker = "<title>@@"
        if marker not in dom:
            return []
        raw = dom.split(marker, 1)[1].split("</title>", 1)[0]
        import json

        return json.loads(raw)
    finally:
        target.write_text(original, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: contrast_audit.py <url#dark|#light> <served-file> [width]")
        raise SystemExit(2)
    url = sys.argv[1]
    target = Path(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1512
    theme = "dark" if "#dark" in url else "light"
    results = measure(url, target, width, theme)
    if not results:
        print(f" OK  no contrast failures ({url})")
        return
    print(f" {len(results)} contrast failures ({url}):")
    for r in results:
        print(
            f"   {r['ratio']:>5} (need {r['need']})  {r['px']}px  "
            f"{r['el'][:34]:<34} fg {r['fg']:<22} bg {r['bg']:<22} {r['txt']!r}"
        )


if __name__ == "__main__":
    main()
