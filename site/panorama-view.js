/* 知识全景：八层技术栈 · 圆堆积（Circle Packing）
 *
 * 为什么是这个图（调研过，不是拍脑袋）：
 *   需求 = 8 个分类 × 200 篇文章 × 要看出哪一层是空的。
 *   属于"两层层级 + 部分-整体 + 找缺口"。
 *   候选里 treemap 面积更精确但空白不扎眼；堆叠条形图能显示同样数据，
 *   但据 Domo 可视化指南的原话"会让 gap 没那么 visually striking"；
 *   同心环（我第二版）要绕圈找标签，读起来累。
 *   Circle packing 胜出：父圆装着子圆，缺的那层就是一个小得可怜的圆，
 *   不用读数字就看得见。
 *
 * 前几版为什么被否（记在这里，别再犯）：
 *   v1 条形图 + 卡片 —— 那不是图，是统计表。
 *   v2 同心环 / 纵向堆叠带 —— 拿用户随口举的"OSI 七层"当结论，
 *      把"层"画成叠起来的带子。用户举例只是举例，不是让我照抄形态。
 *   v3 圆堆积但只画出 120/200 —— 螺旋塞不下就丢弃，缺的圆本身也是信息。
 *
 * 编码规则（必须守）：面积 ∝ 数值，不是半径 ∝ 数值。
 *   半径按 sqrt(value) 走，否则大值会被夸大四倍。这是 circle packing 最常见的错。
 *
 * 交互：hover 看文章，点文章进原文，点父圆放大进该层，点空白退回。
 * 约束：不引 CDN（站点其它部分也没有），d3.pack 的思路手写，配色取 tokens.css。
 */
(function () {
  "use strict";

  /* 数据分工（与 matrix.js 同一哲学，不造第二套事实源）：
   *   R   = 归层规则（panorama-data.js：八层定义 + path→层 的人工归层表）
   *   DATA = 每次渲染时从 state.notes 现算出来的八层条目 —— 标题、字数、
   *          存在性都是实时的，文章改名/增删立即反映，快照不会再腐烂。
   * render(host, notes) 由 index.html 在进入全景页 / 数据刷新时调用。 */
  var R = window.TK_PANORAMA_RULES;
  var DATA = null;
  var NS = "http://www.w3.org/2000/svg";
  var W = 1000, H = 700;
  var RMAX = 172;
  var GOLD = 2.399963229728653;
  /* 螺旋采样的步长（相邻候选点的间距，px）与质量回退开关。
   * 八层栈一次要放 449 个小圆 + 8 个大圆，候选点数 ∝ (搜索半径/步长)²：
   * 步长写死 1.15 时合计上千万个点，每个都要开方 + 三角函数 + 碰撞检测
   * —— 2026-09-24 实测点开八层栈同步阻塞 1.6 秒（dev 上单次 render
   * 687~975ms），CPU profile 里 spiralPlace 独占 21.5%，其余函数全在
   * 0.1% 以下。圆之间本来留 16px 间隙（pad），1.15px 采样远远过密。
   *
   * 所以默认用 2.6 的粗步长（候选点降到约 1/5）。但粗步长会让个别层
   * 塞不下：这时会退化到"网格兜底"，方形网格的角点落到父圆外面
   * （实测 12 个小圆散在父圆外 19px）。所以任何一轮铺不下就切回
   * STEP_FINE（原版取值）重铺 —— 快路径负责快，慢路径保证质量与原版一致。 */
  var STEP = 1.8, STEP_FINE = 1.15, FINE = false;

  /* 八层身份色：只用于圆的 fill（面积身份），不再用于文字 fill。
   * 文字颜色由 panorama.css 的类规则驱动（见 draw() 里 pano-g-* 系注释）。
   * 深色值（#1a365d 等）曾是黑夜模式下文字不可见的直接原因。 */
  /* 层身份色。旧表有两处毛病（2026-09-24 实测发现）：
   * ① 1、3 号用 #dc2626 —— 正是 --color-danger，也是「缺口层」的标记色。
   *    于是硬件与机器、网络与通信两个层画成红圈，读者（和看图评审）会
   *    当成「这层不足 10 篇」，而它们根本不是缺口层。红色现在只留给
   *    缺口标记，身份色一律避开。
   * ② 8 层只有 6 个色（1/3 同色、2/8 同色），身份色失去区分作用。
   * 与 matrix-view.js 的 LAYER_COLOR 是一对一映射（hw/os/net/data/dist/
   * app ↔ 1~6），改这里必须同步改那边。 */
  var LAYER = {
    "1": "#a16207", "2": "#b45309", "3": "#0e7490", "4": "#0284c7",
    "5": "#059669", "6": "#7c3aed", "7": "#1a365d", "8": "#be185d"
  };
  var EN = function () { return window.TKI18N && window.TKI18N.lang === "en"; };
  var Lname = function (L) { return EN() && L.name_en ? L.name_en : L.name; };
  var Ltech = function (L) { return EN() && L.tech_en ? L.tech_en : L.tech; };
  var Lquestion = function (L) { return EN() && L.question_en ? L.question_en : L.question; };
  /* esc / el 是全站共享工具（shell.js「全站共享小工具」区），
     不再本文件各写一份。 */
  var esc = window.TKShell.esc;
  var el = window.TKShell.el;
  function svg(n, a, t) {
    var e = document.createElementNS(NS, n);
    for (var k in (a || {})) e.setAttribute(k, String(a[k]));
    if (t != null) e.textContent = String(t);
    return e;
  }
  var seed = 20240921;
  function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }

  var groups = [], leaves = [], dropped = 0;

  /* ── 组装：规则 × 实时数据 ────────────────────────────────────────
   * ASSIGN 的键先过 TKShell.migratePath()：域名改名只改 shell.js 的
   * PATH_MIGRATIONS 一处，这张表的键自动跟上（掌握进度走同一条链）。 */
  function buildLayers(notes) {
    var byPath = {};
    notes.forEach(function (n) { byPath[n.path] = n; });
    var layers = R.layers.map(function (L) {
      return { id: L.id, name: L.name, tech: L.tech, question: L.question, name_en: L.name_en, tech_en: L.tech_en, question_en: L.question_en, n: 0, items: [] };
    });
    var byId = {};
    layers.forEach(function (L) { byId[L.id] = L; });
    var total = 0;
    Object.keys(R.assign).forEach(function (path) {
      var key = (window.TKShell && TKShell.migratePath) ? TKShell.migratePath(path) : path;
      var note = byPath[key];
      if (!note) return;                     /* 文章已删除：规则留着无害 */
      var L = byId[R.assign[path]];
      if (!L) return;
      /* 面积口径用字数（words）：行数受换行风格影响，字数更稳。 */
      L.items.push({ t: note.title, l: Math.max(note.words || 1, 1), p: note.path });
      L.n++;
      total++;
    });
    return { layers: layers, total: total };
  }

  /* ── 布局缓存 ─────────────────────────────────────────────────
   * 圆堆积是纯计算：449 个小圆 × 上万候选点。数据没变时重算纯属浪费 ——
   * 切走再切回八层栈、切中英文、轮询触发重绘都会再算一遍（实测一次
   * 四百多毫秒）。这里按「数据签名 + 画布尺寸」缓存一次结果，命中直接复用。 */
  var packCache = null, cacheSig = "";
  function dataSig(notes) {
    var h = 5381, i;
    for (i = 0; i < notes.length; i++) h = ((h * 33) ^ (notes[i].path || "").length) | 0;
    return notes.length + ":" + h;
  }
  /* 父圆（8 个）与子圆（449 个）分开算：父圆同步完成、立刻可画，
   * 子圆放到下一帧补。命中缓存时两者一起恢复，跳过全部计算。 */
  function ensureParents(notes) {
    cacheSig = dataSig(notes) + ":" + W + "x" + H;
    if (packCache && packCache.sig === cacheSig) {
      groups = packCache.groups; leaves = packCache.leaves; dropped = packCache.dropped;
      return true;
    }
    leaves = []; dropped = 0;
    packParents();
    return false;
  }
  function ensureLeaves() {
    if (packCache && packCache.sig === cacheSig) return true;
    packLeaves();
    packCache = { sig: cacheSig, groups: groups, leaves: leaves, dropped: dropped };
    return false;
  }
  function legendHTML() {
    return EN()
      ? 'Big circle area = notes in the layer　·　small circle area = words per note　·　' +
        '<span style="color:#dc2626;font-weight:700">red dashed</span> = gap layer (&lt;10 notes)' +
        (dropped > 0 ? '　·　⚠ ' + dropped + ' not drawn' : '')
      : '大圆面积 = 该层篇数　·　小圆面积 = 单篇字数　·　' +
        '<span style="color:#dc2626;font-weight:700">红色虚线</span> = 缺口层（&lt;10 篇）' +
        (dropped > 0 ? '　·　⚠ ' + dropped + ' 篇未画出' : '');
  }

  /* ── 父圆：面积 ∝ 篇数 ─────────────────────────────────────────── */
  /* 整包尝试，谁放不下返回 null，由外层等比缩小后重来。
   * 等比缩放保住"面积 ∝ 篇数"（面积比不变）。此前内容涨到 449 篇后，
   * 自然半径塞不进画布，spiralPlace 返回 null 无人处理，三个大圆全
   * 塌到同一点（左上角叠罗汉），幽灵坐标还把整体居中拖偏、出画布被裁。 */
  function tryPack(scale) {
    var ls = DATA.layers.slice();
    var maxN = Math.max.apply(null, ls.map(function (l) { return l.n; }));
    ls.sort(function (a, b) { return b.n - a.n; });
    var placed = [];
    ls.forEach(function (L) {
      if (!placed) return;                  /* 前面已有圆失败：本轮作废 */
      var r = scale * Math.max(38, RMAX * Math.sqrt(L.n / maxN));
      /* 候选点绕「已放圆群的质心」螺旋，而不是绕画布固定中心：
       * 绕固定中心时，第一个圆抢走最内圈，后续圆被越推越远，最后
       * 整体居中一平移，空隙全挤到一边。绕群质心则每个新圆贴着
       * 已有圆群外缘就位，布局从第一个圆起就紧凑。群质心每放一个
       * 圆重算一次；首圆的候选点直接取画布中心。 */
      var cx = W / 2, cy = H / 2;
      if (placed.length) {
        var sx = 0, sy = 0;
        placed.forEach(function (o) { sx += o.x; sy += o.y; });
        cx = sx / placed.length; cy = sy / placed.length;
        var span = Math.max.apply(null, placed.map(function (o) {
          return Math.hypot(o.x - cx, o.y - cy) + o.r;
        }));
        cx = W / 2 + (cx - W / 2) * (40 / Math.max(span, 40));
        cy = H / 2 + (cy - H / 2) * (40 / Math.max(span, 40));
      }
      var pos = placed.length ? spiralPlace(r, placed, cx, cy, Math.max(W, H)) : { x: W / 2, y: H / 2 };
      if (pos.x == null) { placed = null; return; }
      placed.push({ layer: L, r: r, x: pos.x, y: pos.y });
    });
    return placed;
  }

  function packParents() {
    groups = [];
    FINE = false;
    var placed = null, scale = 1;
    /* 总圆面积随 scale 二次方收缩，画布不变，必然存在能放下的 scale；
     * spiralPlace 首拟合法在面积占比 ≤ 55% 左右必成功，几次内收敛。 */
    while (!placed) {
      placed = tryPack(scale);
      /* 粗步长铺不下就切回精细步长：原版取值下这轮必然成功，循环不会空转 */
      if (!placed) { scale *= 0.9; if (scale < 0.8) FINE = true; }
    }
    FINE = false;
    groups = placed.map(function (g) {
      return {
        layer: g.layer, r: g.r, x: g.x, y: g.y,
        col: LAYER[g.layer.id] || "#1a365d", thin: g.layer.n < 10
      };
    });
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    groups.forEach(function (g) {
      minX = Math.min(minX, g.x - g.r); maxX = Math.max(maxX, g.x + g.r);
      minY = Math.min(minY, g.y - g.r); maxY = Math.max(maxY, g.y + g.r);
    });
    var dx = W / 2 - (minX + maxX) / 2, dy = H / 2 - (minY + maxY) / 2;
    /* 居中偏移钳在画布内：整体平移不许把任何圆推出 8px 安全边。
     * spiralPlace 已保证每个圆在界内，包围盒宽 ≤ W-16，钳制总有解。 */
    dx = Math.max(8 - minX, Math.min(dx, W - 8 - maxX));
    dy = Math.max(8 - minY, Math.min(dy, H - 8 - maxY));
    groups.forEach(function (g) { g.x += dx; g.y += dy; });
  }

  /* ── 子圆：面积 ∝ 行数
   * 关键改动（v3 的 bug 就在这）：先用"填充率 0.7"算缩放系数铺一遍，
   * 谁放不下就把系数整体乘 0.92 重来，直到 200 个全塞进去。
   * 效果是填充率自动降到实际能装下的水平，一个都不丢。 */
  function packLeaves() {
    leaves = []; dropped = 0;
    var FILL = 0.70;
    groups.forEach(function (g) {
      var items = g.layer.items.slice().sort(function (a, b) { return b.l - a.l; });
      var sumL = items.reduce(function (s, it) { return s + Math.max(it.l, 1); }, 0);
      var inner = [], ok = false, guard = 0;
      var k = g.r * Math.sqrt(FILL / sumL);
      var RMIN = 1.9;
      FINE = false;
      while (!ok && guard++ < 40) {
        /* 前几轮用粗步长（快）；铺不下就切精细步长，保证不退化到网格兜底 */
        if (guard > 5) FINE = true;
        inner = []; ok = true;
        for (var i = 0; i < items.length; i++) {
          var r = Math.max(RMIN, Math.sqrt(Math.max(items[i].l, 1)) * k);
          var p = spiralPlace(r, inner, g.x, g.y, g.r - 2.5, true);
          if (p.x == null) { ok = false; break; }
          inner.push({ x: p.x, y: p.y, r: r, g: g, item: items[i], layer: g.layer });
        }
        if (!ok) { k *= 0.92; continue; }
      }
      if (!ok) {
        /* 极端兜底：网格铺，保证不丢（正常走不到这） */
        inner = [];
        var cols = Math.ceil(Math.sqrt(items.length)), cw = (g.r * 2 - 6) / cols;
        items.forEach(function (it, i) {
          inner.push({
            x: g.x - g.r + 3 + (i % cols + 0.5) * cw,
            y: g.y - g.r + 3 + (Math.floor(i / cols) + 0.5) * cw,
            r: Math.min(RMIN + 1, cw * 0.4), g: g, item: it, layer: g.layer
          });
        });
      }
      g.leaves = inner;
      inner.forEach(function (x) { leaves.push(x); });
    });
    dropped = DATA.total - leaves.length;
  }

  /* 黄金角螺旋找位：第一个不重叠又不越界的点就放下。
     出来的形状就是熟悉的气泡堆积感。 */
  function spiralPlace(r, placed, cx, cy, limit, insideOnly) {
    /* pad 不能小：组标签胶囊（ty-12 起，最高 51px）画在父圆上缘并向
       外冒头。间距小于冒头量时，胶囊直接压到相邻圆的气泡上（实测：
       1.1px 时「应用与架构」胶囊盖住「操作系统与运行时」圆顶）。
       16px = 画布边距 8 × 2 + 估算余量，标签冒头 ≤10px 时双主题目测干净。 */
    var pad = 16;
    var maxRad = limit - r - pad;
    if (maxRad < 0) return { x: null, y: null };
    var step = FINE ? STEP_FINE : STEP;
    var steps = Math.ceil(Math.pow(maxRad / step, 2)) + 400;
    for (var t = 0; t < steps; t++) {
      var rad = step * Math.sqrt(t);
      if (rad > maxRad) break;
      var ang = t * GOLD;
      var x = cx + Math.cos(ang) * rad, y = cy + Math.sin(ang) * rad;
      var ok = true;
      for (var i = 0; i < placed.length; i++) {
        var o = placed[i];
        var dx = x - o.x, dy = y - o.y, mr = r + o.r + pad;
        if (dx * dx + dy * dy < mr * mr) { ok = false; break; }
      }
      if (!ok) continue;
      if (!insideOnly && (x - r < 8 || x + r > W - 8 || y - r < 8 || y + r > H - 8)) continue;
      return { x: x, y: y };
    }
    return { x: null, y: null };
  }

  /* 子圆单独成函数：两阶段渲染时第二帧只补这一层，不必重建整张 SVG。 */
  function drawLeaves(lWrap) {
    leaves.forEach(function (p) {
      var g = svg("g", { class: "pano-node", "data-layer": p.layer.id });
      g.appendChild(svg("title", null, p.item.t + "（" + p.item.l + " 字）"));
      g.appendChild(svg("circle", {
        cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: p.r.toFixed(1),
        fill: p.g.col, "fill-opacity": 0.7,
        /* 描边 #fff 写死在黑夜主题是刺眼白圈；currentColor 跟文字前景，
           双主题下都是"贴色描边"的观感。缺口层描边保持警示红。 */
        stroke: p.g.thin ? "#dc2626" : "currentColor",
        "stroke-width": p.g.thin ? 0.9 : 0.55
      }));
      g.addEventListener("click", function (ev) {
        ev.stopPropagation();
        /* 八层栈是主站页内视图：派发给 index 的 SPA 路由打开文章。
           location.href 整页跳转会冲掉侧栏展开态（子主题实测过）。 */
        document.dispatchEvent(new CustomEvent("tk:pano-open", { detail: { path: p.item.p } }));
      });
      g.addEventListener("mouseenter", function () { showTip(p); });
      g.addEventListener("mouseleave", hideTip);
      lWrap.appendChild(g);
    });
  }

  /* ── 绘制 ──────────────────────────────────────────────────────── */
  var root, vb = { x: 0, y: 0, w: W, h: H };
  function draw(host) {
    root = svg("svg", {
      viewBox: "0 0 " + W + " " + H, class: "pano-map", role: "img",
      "aria-label": "八层技术栈圆堆积图，共 " + DATA.total + " 篇文章"
    });
    var bg = svg("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent", class: "pano-bg" });
    bg.addEventListener("click", function () { zoomTo(null); });
    root.appendChild(bg);

    var gWrap = svg("g", { class: "pano-groups" });
    var lWrap = svg("g", { class: "pano-leaves" });
    /* 【ui-iter·层级】gWrap 必须在 lWrap 之后挂载：SVG 靠文档序分层，
     * 组标签胶囊要盖在子圆上面才可读。原先 gWrap 在前，胶囊被子圆层
     * 整层盖住（实测 pills 有几何、截图中隐形）。 */
    root.appendChild(lWrap);
    root.appendChild(gWrap);

    groups.forEach(function (g) {
      var grp = svg("g", { class: "pano-grp", "data-layer": g.layer.id });
      /* 组圆：fill 是层身份色（面积信息），描边细圈起分割作用。
       缺口层的红色描边写死 —— 它是双主题语义色（panorama.css
       头注释同款约定），不随主题变换，红色永远代表"这层太薄"。 */
    grp.appendChild(svg("circle", {
        cx: g.x.toFixed(1), cy: g.y.toFixed(1), r: g.r.toFixed(1),
        fill: g.col, "fill-opacity": 0.09,
        stroke: g.thin ? "#dc2626" : g.col,
        "stroke-width": g.thin ? 2 : 1.4,
        "stroke-dasharray": g.thin ? "5 3" : "none"
      }));
      var big = g.r >= 60;
      var tx = g.x, ty = big ? g.y - g.r + 21 : g.y + g.r + 16;
      /* 【ui-iter·标签衬底】组名三行（名称/篇数/技术栈）直接叠在花色子圆上，
       * halo 只能救回轮廓、救不回"泡在花圆里"的糊感，与覆盖矩阵每格
       * 实底的干净观感差距明显。改为画一个半透明胶囊 rect 垫在三行
       * 文字下：文字先建（量 getBBox 用），rect 插到文字前面（SVG 无
       * z-index，靠文档序分层），整组 gWrap 又在 lWrap（子圆层）之上，
       * 胶囊自然盖住圆、不遮点击（click 落在组圆/子圆，胶囊 pointer-events
       * 关掉）。胶囊色 var(--color-panel)+0.92 不透明度：双主题自动跟随，
       * 近似实底又留一丝层次。行高 16/14 与下方文字 dy 一致。 */
      var nameTxt = svg("text", {
        x: tx.toFixed(1), y: ty.toFixed(1),
        "text-anchor": "middle", class: "pano-g-name"
      }, Lname(g.layer));
      var nTxt = svg("text", {
        x: tx.toFixed(1), y: (ty + (big ? 17 : 14)).toFixed(1),
        "text-anchor": "middle", class: "pano-g-n"
      }, EN() ? g.layer.n + (g.layer.n === 1 ? " note" : " notes") + (g.thin ? " · gap" : "") : g.layer.n + " 篇" + (g.thin ? " · 缺口" : ""));
      grp.appendChild(nameTxt);
      grp.appendChild(nTxt);
      if (big) {
        grp.appendChild(svg("text", {
          x: tx.toFixed(1), y: (ty + 34).toFixed(1),
          "text-anchor": "middle", class: "pano-g-tech"
        }, Ltech(g.layer).length > 26 ? Ltech(g.layer).slice(0, 25) + "…" : Ltech(g.layer)));
      }
      /* 量完三行包围盒后把胶囊插到最前面（第一个子元素 = 最底层）。 */
      /* 【ui-iter·v2】第一版用 getBBox() 量新建的 text —— 元素未挂到
       * 渲染树时 bbox 全 0，胶囊塌成 18×4 的小点（实测）。不依赖量测：
       * 用行数与字号估算宽高。宽度按最长行字符数 × 字宽系数（中文 1em、
       * 拉丁 0.62em、混排取中间值 0.72em 偏安全），高度 = 行数 × 行距。
       * 误差由 padding 吸收；宁宽勿窄，宽一点的胶囊更稳。 */
      var padX = 10, padY = 5, lineH = big ? 17 : 15;
      var rows = [Lname(g.layer), nTxt.textContent];
      if (big) rows.push(grp.querySelector(".pano-g-tech").textContent);
      var chars = Math.max.apply(null, rows.map(function (s) { return s.length; }));
      var estW = chars * 7.2 + padX * 2;
      var estH = rows.length * lineH + padY * 2 - (big ? 2 : 3);
      var pill = svg("rect", {
        x: (tx - estW / 2).toFixed(1),
        y: (ty - 12).toFixed(1),
        width: estW.toFixed(1), height: estH.toFixed(1),
        rx: 7, class: "pano-g-pill"
      });
      grp.insertBefore(pill, grp.firstChild);
      grp.addEventListener("click", function (ev) { ev.stopPropagation(); zoomTo(g); });
      grp.style.cursor = "zoom-in";
      gWrap.appendChild(grp);
    });

    drawLeaves(lWrap);

    host.appendChild(root);
  }

  /* ── 缩放：点父圆进去，再点同一个圆退回（toggle），点空白也出来 ── */
  var zoomed = null;
  function zoomTo(g, instant) {
    if (!root) return;
    var target;
    if (!g) {
      zoomed = null; target = { x: 0, y: 0, w: W, h: H };
      writeZoomHash(null);
    } else {
      /* toggle：已放大的层再点一次 = 退回全图。原先对同一目标重复
         zoomTo(g)，视觉上点了没反应 —— 「放大之后退不回去」即此。 */
      if (zoomed === g.layer.id) { zoomTo(null, instant); return; }
      zoomed = g.layer.id;
      var m = 26;
      target = { x: g.x - g.r - m, y: g.y - g.r - m, w: (g.r + m) * 2, h: (g.r + m) * 2 };
      writeZoomHash(g.layer.id);
    }
    var ar = W / H;   /* 保持宽高比，否则图会被拉扁 */
    if (target.w / target.h > ar) { var nh = target.w / ar; target.y -= (nh - target.h) / 2; target.h = nh; }
    else { var nw = target.h * ar; target.x -= (nw - target.w) / 2; target.w = nw; }
    /* 带深链进入（zoomFromHash）时直接落位，不放 420ms 动画；
       用户点击仍走缓动 —— 动画是给人看的反馈，不是给 URL 恢复看的。 */
    if (instant) {
      if (rafId) cancelAnimationFrame(rafId);
      vb = target;
      root.setAttribute("viewBox", vb.x.toFixed(1) + " " + vb.y.toFixed(1) + " " + vb.w.toFixed(1) + " " + vb.h.toFixed(1));
    } else lerpVB(target);
    syncFocusBar();
    syncCursors();
  }

  /* 放大态写进 hash（#zoom=层id），与矩阵格子的 #cell= 同一套深链哲学：
   * 所见即所链。退回时清 hash，不留「刷新后意外跳回放大」。
   * replaceState 只带 search 时 query（?view=panorama&domain=…）原样保留。 */
  function writeZoomHash(id) {
    try {
      if (id) history.replaceState(null, "", location.search + "#zoom=" + id);
      else if (location.hash) history.replaceState(null, "", location.search);
    } catch (e) {}
  }

  /* 带 #zoom= 深链进入时恢复该层放大态。id 对不上（文章已删/层号不存在）
   * 就当没这个 hash，别让坏链接炸渲染。 */
  function zoomFromHash() {
    var m = /#zoom=([a-z0-9]+)/.exec(location.hash || "");
    if (!m) return;
    var g = groups.filter(function (x) { return x.layer.id === m[1]; }); 
    g = g[0];
    if (g) zoomTo(g, true);
  }

  /* cursor / aria 随缩放态同步：已放大的圆是 zoom-out（再点退回），
   * 其余是 zoom-in。原先写死 zoom-in，放大后没有任何「可退回」提示。 */
  function syncCursors() {
    groups.forEach(function (g) {
      if (!g.el) return;
      var mine = zoomed === g.layer.id;
      g.el.style.cursor = mine ? "zoom-out" : "zoom-in";
      g.el.setAttribute("aria-label", Lname(g.layer) + " — " + (mine ? (EN() ? "zoom out" : "退回全图") : (EN() ? "zoom in" : "放大")));
    });
  }
  var rafId = null;
  function lerpVB(t) {
    if (rafId) cancelAnimationFrame(rafId);
    var s = { x: vb.x, y: vb.y, w: vb.w, h: vb.h }, st = performance.now(), dur = 420;
    (function step(now) {
      var k = Math.min(1, (now - st) / dur);
      k = 1 - Math.pow(1 - k, 3);
      vb = { x: s.x + (t.x - s.x) * k, y: s.y + (t.y - s.y) * k, w: s.w + (t.w - s.w) * k, h: s.h + (t.h - s.h) * k };
      root.setAttribute("viewBox", vb.x.toFixed(1) + " " + vb.y.toFixed(1) + " " + vb.w.toFixed(1) + " " + vb.h.toFixed(1));
      if (k < 1) rafId = requestAnimationFrame(step);
    })(performance.now());
  }

  function syncFocusBar() {
    var bar = document.querySelector("#pano-focus");
    if (!bar) return;
    if (!zoomed) { bar.classList.remove("on"); bar.innerHTML = ""; return; }
    var L = DATA.layers.filter(function (x) { return x.id === zoomed; })[0];
    /* 先取当前语言的词，再拼一句：两个三元挤在一行里读不出"同一句话的
       两个语言版本"这层结构。 */
    var unit = EN() ? (L.n === 1 ? " note" : " notes") : " 篇";
    var back = EN() ? "Back to full map" : "退回全图";
    bar.innerHTML = '<b>' + esc(Lname(L)) + '</b> ' + L.n + unit +
      '　<span>' + esc(Ltech(L)) + '　·　' + esc(Lquestion(L)) + '</span>' +
      '　<a href="#" class="pano-clear">' + back + '</a>';
    bar.classList.add("on");
    var a = bar.querySelector(".pano-clear");
    if (a) a.onclick = function (e) { e.preventDefault(); zoomTo(null); };
  }

  /* ── 悬浮提示 ──────────────────────────────────────────────────── */
  var tip;
  function showTip(p) {
    if (!tip) { tip = el("div", "pano-tip"); document.body.appendChild(tip); }
    var unit = EN() ? ' words' : ' 字';
    tip.innerHTML = '<b>' + esc(p.item.t) + '</b><span>' + esc(Lname(p.layer)) + '　' + p.item.l + unit + '</span>';
    tip.style.borderLeftColor = p.g.col;
    tip.classList.add("on");
    document.addEventListener("mousemove", moveTip);
  }
  function moveTip(e) {
    if (!tip) return;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + tip.offsetWidth > innerWidth - 8) x = e.clientX - tip.offsetWidth - 14;
    if (y + tip.offsetHeight > innerHeight - 8) y = e.clientY - tip.offsetHeight - 14;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() {
    if (tip) tip.classList.remove("on");
    document.removeEventListener("mousemove", moveTip);
  }

  function renderNote(host) {
    var box = el("div", "pano-note");
    box.appendChild(el("h3", "pano-sec", EN() ? "What the map shows at a glance" : "图上直接看到的"));
    var ul = el("ul", "pano-note-list");
    var sorted = DATA.layers.slice().sort(function (a, b) { return b.n - a.n; });
    /* 每层一句话。中文/英文各自成句，别在拼接里来回切换语言。 */
    DATA.layers.filter(function (l) { return l.n < 10; }).sort(function (a, b) { return a.n - b.n; })
      .forEach(function (L) {
        var line = EN()
          ? Lname(L) + " — its circle is almost invisible: " + L.n + " notes, " + Lquestion(L) + " is essentially blank"
          : L.name + "那个圆小得几乎看不见 —— " + L.n + " 篇，" + L.question + "基本是空白";
        ul.appendChild(el("li", null, line));
      });
    var ratio = (sorted[0].n / sorted[1].n).toFixed(1);
    var biggest = EN()
      ? Lname(sorted[0]) + " has the largest circle (" + sorted[0].n + " notes, " + ratio + "x the runner-up"
      : sorted[0].name + "那个圆最大（" + sorted[0].n + " 篇），是第二名的 " + ratio + " 倍";
    ul.appendChild(el("li", null, biggest));
    box.appendChild(ul);
    host.appendChild(box);
  }

  function render(host, notes) {
    if (!host) return;
    if (!R || !notes || !notes.length) { host.innerHTML = ''; host.appendChild(window.tkEmptyState ? window.tkEmptyState('等待笔记数据…') : Object.assign(document.createElement('p'), { className: 'view-empty', textContent: '等待笔记数据…' })); return; }
    DATA = buildLayers(notes);
    /* 未归层 = 正式文章里不在 ASSIGN 的那些。八层栈只收已归层的文章
       （归层是人工语义判断，不假装能自动归类），缺多少如实说出来。 */
    var formal = notes.filter(function (n) {
      return n.category !== "总览" && n.category !== "Clippings" && !n.exclude_from_graph;
    }).length;
    var unassigned = Math.max(formal - DATA.total, 0);
    host.innerHTML = "";
    vb = { x: 0, y: 0, w: W, h: H }; zoomed = null;

    var top = el("div", "pano-intro");
    /* 双语导语：先选定语言再拼整段，两个版本各自是完整的一句话链。
     * 2026-09-22 拆段：原来四句拼成一个 <p>（70ch 行宽下必然在句子中间
     * 怪折行，用户抓到「换行好奇怪」）。按语义拆成四段——总览（这页是
     * 什么）、编码规则（圆怎么读）、警示（红虚线含义）、操作句（点哪里
     * 发生什么），每段 ≤24 字保证单行收住（70ch ≈ 38 个汉字）。
     * 操作句独立成段并加粗，与图谱页 .graph-focus-hint 的「主句/操作句」
     * 分行是同一决策链：断点落在语义处而非宽度处。矩阵 tab 的导语
     * （index.html renderMatrixView）同日改成了五段式，两边同构。 */
    top.innerHTML = EN()
      ? "<p>" + DATA.total + " notes of engineering knowledge = " + DATA.total + " circles, grouped into eight big ones by the <b>8-layer stack</b>.</p>" +
        "<p><b>Area ∝ note count</b> (not radius); inner circle area ∝ word count.</p>" +
        "<p><b>Red dashed rings</b> mark layers under 10 notes — their circles are strikingly small.</p>" +
        "<p class=\"pano-focus-hint\">Click a small circle to open the note, <span class=\"pano-hint-seg\">a big one to zoom into the layer, </span><span class=\"pano-hint-seg\">empty space to zoom out</span>" +
        (unassigned > 0 ? " <span class=\"pano-unassigned\">Another " + unassigned + " notes are not assigned to a layer (add a line to ASSIGN in panorama-data.js to put them on the map).</span>" : "") +
        "</p>"
      : "<p>" + DATA.total + " 篇工程知识 = " + DATA.total + " 个圆，按<b>八层技术栈</b>分成八个大圆。</p>" +
        "<p><b>圆面积 ∝ 篇数</b>（不是半径），小圆面积 ∝ 文章字数。</p>" +
        "<p><b>红色虚线</b>是不足 10 篇的缺口层 —— 它的圆小得扎眼。</p>" +
        "<p class=\"pano-focus-hint\">点小圆进原文，<span class=\"pano-hint-seg\">点大圆放大看该层，</span><span class=\"pano-hint-seg\">点空白处退回</span>" +
        (unassigned > 0 ? " <span class=\"pano-unassigned\">另有 " + unassigned + " 篇未归层（在 panorama-data.js 的 ASSIGN 补一行即可上图）</span>" : "") +
        "</p>";
    host.appendChild(top);

    var bar = el("div", "pano-focusbar");
    bar.id = "pano-focus";
    host.appendChild(bar);

    var stage = el("div", "pano-stage");
    host.appendChild(stage);

    /* 两阶段渲染：父圆只有 8 个，几毫秒算完；449 个子圆要算几百毫秒。
     * 先让浏览器把父圆 + 导语画出来（点开就有图，不是一片空白干等），
     * 下一帧再算子圆补进去 —— 感知的「打开」快了，总计算量不变。 */
    var full = ensureParents(notes);
    draw(stage);

    var lg = el("p", "pano-legend");
    lg.innerHTML = legendHTML();
    host.appendChild(lg);

    if (!full) {
      requestAnimationFrame(function () {
        ensureLeaves();
        var lWrap = stage.querySelector(".pano-leaves");
        if (lWrap) drawLeaves(lWrap);
        lg.innerHTML = legendHTML();   /* 「N 篇未画出」要等子圆算完才知道 */
      });
    }

    renderNote(host);
    hideTip();
  }

  /* 预热：只算布局写进缓存，不碰 DOM。由 index.html 在停在别的 tab 时
   * 于空闲时段调用 —— 用户再切到八层栈就直接命中缓存，不用等一次布局
   * 计算（实测约 600ms）。 */
  function prewarm(notes) {
    if (!R || !notes || !notes.length) return;
    DATA = buildLayers(notes);
    ensureParents(notes);
    ensureLeaves();
  }

  window.TKPanorama = { render: render, prewarm: prewarm };
})();
