#!/usr/bin/env python3
"""站点级页面体检：非阅读页 + 若干阅读页，看读者真正会撞上的问题。

阅读页布局已有 .work/layout_audit_pw.py 覆盖；这里补的是另一类：
  - 站点的其它页面（首页、图谱、全景、学习中心、论文追踪、优质好文）
  - 图片有没有真的加载出来（naturalWidth=0 就是空图框，读者只看到占位）
  - 顶栏搜索框是不是都在右上角（位置一致性）
  - 横向溢出（手机上出现左右拖动）
"""
import urllib.parse
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
PAGES = [
    ("首页", "/"),
    ("知识图谱", "/?view=graph"),
    ("知识全景", "/?view=panorama"),
    ("论文追踪", "/papers/"),
    ("优质好文", "/sources/"),
]
READERS = [
    "工程知识/缺陷分析：从个案到体系/并发/案例三十一：回收之后还在飞——跨线程复用可回收对象.md",
    "工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/CPU性能来自有效执行与数据供给.md",
]

PROBE = """() => {
  const imgs = [...document.images];
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0)
                     .map(i => (i.getAttribute('src') || '').split('/').pop().slice(0, 30));
  const bar = document.querySelector('.topbar');
  const s = bar && bar.querySelector('input[type=search]');
  const sb = s && s.closest('.search');
  return {
    图总数: imgs.length,
    加载失败: broken,
    顶栏: !!bar,
    搜索框距右: sb ? Math.round(window.innerWidth - sb.getBoundingClientRect().right) : null,
    横向溢出: document.documentElement.scrollWidth - window.innerWidth,
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    for width in (1440, 390):
        pg = b.new_page(viewport={"width": width, "height": 900})
        for label, path in PAGES:
            try:
                pg.goto(BASE + path, wait_until="domcontentloaded", timeout=40000)
                pg.wait_for_timeout(1800)
                d = pg.evaluate(PROBE)
                flag = []
                if d["加载失败"]:
                    flag.append("空图 %d 张: %s" % (len(d["加载失败"]), d["加载失败"][:2]))
                if d["横向溢出"] > 1:
                    flag.append("横向溢出 %dpx" % d["横向溢出"])
                if not d["顶栏"]:
                    flag.append("无顶栏")
                elif d["搜索框距右"] is None:
                    flag.append("顶栏无搜索框")
                elif width == 1440 and d["搜索框距右"] > 60:
                    flag.append("搜索框未贴右（距右 %dpx）" % d["搜索框距右"])
                print(f"{label}@{width}  图{d['图总数']} 距右{d['搜索框距右']}")
                for f in flag:
                    print("        !! " + f)
            except Exception as e:
                print(f"{label}@{width} 访问失败: {str(e)[:60]}")
        for rel in READERS:
            url = BASE + "/?path=" + urllib.parse.quote(rel)
            pg.goto(url, wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_selector(".reader-body", timeout=25000)
            pg.wait_for_timeout(2500)
            d = pg.evaluate(PROBE)
            print(f"阅读页 {rel.split('/')[-1][:16]}@{width}  图{d['图总数']} 失败{d['加载失败']}")
        pg.close()
    b.close()
