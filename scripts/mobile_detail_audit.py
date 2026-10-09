#!/usr/bin/env python3
"""窄屏（390px）细节体检。

文档级横向溢出已有 layout_audit_pw 覆盖，但"整页没溢出"不等于好用：
宽度超出的代码块、表格如果没有自己的滚动容器，读者在手机上根本看不全；
正文字号在手机上小于 14px 会吃力；按钮小于 44px 不符合触控目标尺寸。
这些是文档级审计看不见、但读者天天撞上的问题。
"""
import urllib.parse
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18788"
ARTS = [
    "工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/CPU性能来自有效执行与数据供给.md",
    "工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/超时、重试与幂等共同定义调用语义.md",
    "工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/Python数据访问必须显式拥有连接与事务.md",
    "工程知识/缺陷分析：从个案到体系/并发/案例二十：关闭之后还有人在用——生命周期的时序竞态.md",
]

PROBE = """() => {
  const body = document.querySelector('.reader-body');
  if (!body) return null;
  const cs = getComputedStyle(body);
  const pres = [...body.querySelectorAll('pre')];
  const tables = [...body.querySelectorAll('table')];
  const scrollable = el => ['auto','scroll'].includes(getComputedStyle(el).overflowX);
  const widePres = pres.filter(p => p.scrollWidth > p.clientWidth + 2)
                       .filter(p => !scrollable(p) && !scrollable(p.parentElement));
  const wideTables = tables.filter(t => t.scrollWidth > t.clientWidth + 2)
                           .filter(t => !scrollable(t) && !scrollable(t.parentElement));
  const btns = [...document.querySelectorAll('button, a.reader-tool, .reader-back')]
      .filter(b => b.offsetParent !== null)
      .map(b => ({t: (b.textContent || '').trim().slice(0, 8),
                  h: Math.round(b.getBoundingClientRect().height),
                  w: Math.round(b.getBoundingClientRect().width)}))
      .filter(b => b.h > 0 && b.h < 40);
  return {
    正文字号: cs.fontSize,
    行高: cs.lineHeight,
    正文栏宽: Math.round(body.getBoundingClientRect().width),
    pre数: pres.length, 溢出的pre: widePres.length,
    表格数: tables.length, 溢出的表格: wideTables.length,
    偏小按钮: btns.slice(0, 4),
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    # 必须用触屏上下文：按钮的 44px 热区写在 @media (pointer: coarse) 里，
    # 桌面指针量到的是 32/36px，会一直误报"触控目标偏小"（实际真机已达标）。
    ctx = b.new_context(viewport={"width": 390, "height": 844},
                        device_scale_factor=2, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    for rel in ARTS:
        pg.goto(BASE + "/?path=" + urllib.parse.quote(rel), wait_until="domcontentloaded", timeout=45000)
        try:
            pg.wait_for_selector(".reader-body", timeout=25000)
        except Exception:
            print(rel[-20:], "正文未渲染"); continue
        pg.wait_for_timeout(2000)
        d = pg.evaluate(PROBE)
        if not d:
            print(rel[-20:], "no body"); continue
        flags = []
        if float(d["正文字号"].replace("px", "")) < 14:
            flags.append("正文 %s 偏小（手机建议 ≥14px）" % d["正文字号"])
        if d["溢出的pre"]:
            flags.append("%d 个代码块横向超出且不可滚动" % d["溢出的pre"])
        if d["溢出的表格"]:
            flags.append("%d 个表格横向超出且不可滚动" % d["溢出的表格"])
        if d["偏小按钮"]:
            flags.append("触控目标偏小: %s" % d["偏小按钮"])
        print("%-22s 正文%s/%s 栏%dpx | pre %d(溢出%d) 表 %d(溢出%d)" % (
            rel.split("/")[-1][:22], d["正文字号"], d["行高"], d["正文栏宽"],
            d["pre数"], d["溢出的pre"], d["表格数"], d["溢出的表格"]))
        for f in flags:
            print("        !! " + f)
    b.close()
