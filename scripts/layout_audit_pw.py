"""阅读页布局审计（playwright 版）。

为什么不用 scripts/article_layout_audit.py：那个脚本靠往 index.html 里注入
探针、再用 chrome-headless-shell --dump-dom 读 <title>@@json</title>。注入
点跟着文件结构走，结构一变就注入失败——实测所有字段返回 None（审计全空），
而它崩在 KeyError 上又掩盖了这一点。这里改成直接从真实渲染结果上量：
不注入、不改文件，读 DOM 几何。

检测项都是"读者能感觉到"的问题：
  - 横向溢出：出现横向滚动条
  - 首屏挤占：正文起点被头部区域推到第一屏之外
  - 图片溢出：图片比正文栏宽（撑破版心）
  - 顶栏脱岗：滚动后顶栏不在最上（导航丢失）
"""
import argparse
import json
import pathlib
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
WIDTHS = (1440, 768, 390)

PROBE = """() => {
  const body = document.querySelector('.reader-body');
  const bar = document.querySelector('.topbar');
  const rb = body && body.getBoundingClientRect();
  const imgs = body ? [...body.querySelectorAll('img')] : [];
  const colW = rb ? rb.width : 0;
  return {
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    bodyStartY: rb ? Math.round(rb.top + window.scrollY) : null,
    headH: bar ? Math.round(bar.getBoundingClientRect().height) : null,
    imgOverflow: imgs.filter(i => i.getBoundingClientRect().width > colW + 1)
                     .map(i => Math.round(i.getBoundingClientRect().width)),
    imgCount: imgs.length,
    viewportH: window.innerHeight,
  };
}"""


def sample(page, path, width):
    url = f"{BASE}/?path={urllib.parse.quote(path)}"
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector(".reader-body", timeout=25000)
    except Exception:
        return None
    # 正文是异步渲染的（Markdown → DOM，图片随后加载）。只等固定 1200ms 会在
    # 渲染中途测量：内容一插进来文档高度就变，滚动位置跟着漂，于是测出
    # "顶栏 top=122 / 翻页 False" 这类假问题（手动复核时两者都正常）。
    # 改成轮询到文档高度连续两次不变再测。
    prev, stable = -1, 0
    for _ in range(20):
        h = page.evaluate("document.documentElement.scrollHeight")
        stable = stable + 1 if h == prev else 0
        if stable >= 2:
            break
        prev = h
        page.wait_for_timeout(400)
    page.wait_for_timeout(300)
    data = page.evaluate(PROBE)
    # 顶栏是否常驻：滚一段之后仍应贴在视口顶部
    page.evaluate("window.scrollTo(0, 1200)")
    page.wait_for_timeout(500)
    data["barTopAfterScroll"] = page.evaluate(
        "() => {const b=document.querySelector('.topbar'); return b?Math.round(b.getBoundingClientRect().top):null;}"
    )
    data["condensed"] = page.evaluate(
        "() => document.querySelector('.topbar').classList.contains('is-condensed')"
    )
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--list")
    args = ap.parse_args()

    if args.list:
        paths = [l.strip() for l in pathlib.Path(args.list).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        payload = json.loads(urllib.request.urlopen(BASE + "/api/notes", timeout=15).read())
        notes = payload["notes"] if isinstance(payload, dict) else payload
        paths = [n["path"] for n in notes]
    paths = paths[: args.limit]

    problems = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for path in paths:
            name = pathlib.Path(path).stem[:22]
            for w in WIDTHS:
                d = sample(pg, path, w)
                if not d:
                    print(f"  ?  {name}@{w}: 正文未渲染")
                    continue
                flags = []
                if d["overflow"] > 1:
                    flags.append(f"横向溢出 {d['overflow']}px")
                if d["bodyStartY"] and d["bodyStartY"] > d["viewportH"] * 0.9:
                    flags.append(f"正文起点 {d['bodyStartY']}px，被挤出首屏（视高 {d['viewportH']}）")
                if d["imgOverflow"]:
                    flags.append(f"图片溢出正文栏：{d['imgOverflow']}")
                if d["barTopAfterScroll"] not in (0, None):
                    flags.append(f"滚动后顶栏 top={d['barTopAfterScroll']}（应为 0）")
                line = (f"  {name}@{w}  起点 {d['bodyStartY']}px | 图 {d['imgCount']} 张"
                        f" | 翻页 {d['condensed']}")
                print(line)
                for f in flags:
                    problems += 1
                    print(f"        !! {f}")
        b.close()
    print(f"\n问题项合计 {problems}")


if __name__ == "__main__":
    sys.exit(main())
