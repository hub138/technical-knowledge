/* 知识覆盖矩阵：X = 系统层次，Y = 知识类型。
 *
 * 为什么是网格不是圆圈：一维只能回答"哪一类少"，回答不了"哪个方向漏"。
 * 两个正交轴张成的面上，空格子才是洞 —— 技能矩阵方法里叫"零覆盖缺口"。
 *
 * 和知识图谱的分工（别做成同一个东西）：
 *   图谱是自底向上的，看文章连文章（谁引用了谁）；
 *   本图是自顶向下的，看知识在框架里的位置（哪个格子还空着）。
 *   一个看连接，一个看空缺。所以这里不画连线，只画格子。
 *
 * 只依赖 site/matrix.js 的分类结果，自己不做任何打分。
 */
(function () {
  "use strict";

  var M = window.TKMatrix;
  var KINDS = M.KINDS, LAYERS = M.LAYERS;
  var EN = function () { return window.TKI18N && window.TKI18N.lang === "en"; };
  var kName = function (k) { return EN() && k.name_en ? k.name_en : k.name; };
  var kHint = function (k) { return EN() && k.hint_en ? k.hint_en : k.hint; };
  var lName = function (L) { return EN() && L.name_en ? L.name_en : L.name; };
  var lHint = function (L) { return EN() && L.hint_en ? L.hint_en : L.hint; };

  /* el 是全站共享工具（shell.js「全站共享小工具」区）。
     语言判断本文件统一走 EN()：原先顶部定义了 EN() 却又在内联处写了
     十几处 window.TKI18N.lang==="en" 内联判断，同一个问题两种答案来源，
     词典键或加载顺序一变就会出现半中半英的格子。 */
  var el = window.TKShell.el;

  /* 层身份色：与 panorama-view.js 的 LAYER 色表同源 —— 行头竖条的颜色
   * 必须和圆堆积图的层色一致，两张图才读得出「同一层」。色表在这里
   * 复制一份而不是 import，因为 panorama-view 是懒加载视图脚本，
   * matrix-view 先执行时它可能还没就位。（两处色表改动要同步，这是
   * 已知的一对一映射，panorama-view.js 头部有反向注释。） */
  /* 与 panorama-view.js 的 LAYER 同步改（2026-09-24）：hw/net 原用
   * #dc2626（--color-danger），与八层栈「缺口层」的红色标记撞语义，
   * 且 hw/net 同色。新的 1~6 号色见 panorama-view.js 的 LAYER。 */
  var LAYER_COLOR = {
    hw: "#a16207", os: "#b45309", net: "#0e7490", data: "#0284c7",
    dist: "#059669", app: "#7c3aed"
  };

  /* 格子深浅：按篇数分档。
   * 不用连续色阶 —— 177 篇里大多数格子是 1~10 篇，连续色阶在这个区间
   * 肉眼看不出差别，分档才能一眼分出"有/薄/厚"。 */
  function level(n) {
    if (n === 0) return "lv0";
    if (n <= 2) return "lv1";
    if (n <= 7) return "lv2";
    if (n <= 15) return "lv3";
    return "lv4";
  }

  /* 当前渲染进矩阵的文章集：行头/列头的"整行/整列清单"从这里过滤。
   * renderMatrix 每次重建时刷新，域切换后清单口径跟着变。 */
  var currentItems = [];

  function renderMatrix(host, items) {
    currentItems = items;
    var cells = M.matrix(items);
    var inMatrix = items.filter(function (i) { return !i.excluded; });

    var wrap = el("div", "mx-wrap");
    var grid = el("div", "mx-grid");
    /* 手机上矩阵比屏幕宽，靠左右滑动看完整表格。没有提示的话，
       滑动入口不可发现（截图确认）。提示只在确实放不下时出现。 */
    var hint = el("p", "mx-swipe-hint", EN() ? "Swipe left / right to see all columns" : "← 左右滑动查看全部列 →");
    wrap.appendChild(hint);

    /* 表头：左上角是轴指示——每列是一种知识类型，每行是一个系统层次。
     * 旧版「知识类型 → / ↓ 系统层次」箭头式写法被用户反馈"不好看"：
     * 箭头方向和真实轴向还要读者再翻译一次。直接用"列/行"语言。 */
    var corner = el("div", "mx-corner");
    corner.appendChild(el("span", "mx-corner-col", EN() ? "Columns: kinds" : "列 · 知识类型"));
    corner.appendChild(el("span", "mx-corner-row", EN() ? "Rows: layers" : "行 · 系统层次"));
    grid.appendChild(corner);
    KINDS.forEach(function (k) {
      var h = el("div", "mx-col-head mx-clickable");
      h.appendChild(el("div", "mx-kind-name", kName(k)));
      h.appendChild(el("div", "mx-kind-hint", kHint(k)));
      /* 列头是入口：点列头看这一类知识的全部文章（跨所有层）。
       * 词元这类"整列只有几篇"的类型，之前只能从格子进、格子被
       * 分散在各行——现在类型级入口补上，每类知识都有自己的门。 */
      h.setAttribute("role", "button");
      h.setAttribute("tabindex", "0");
      h.title = EN() ? "All " + kName(k) + " notes" : "看全部" + kName(k) + "文章";
      var openCol = function () { showAxisList(host, null, k); };
      h.addEventListener("click", openCol);
      h.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openCol(); }
      });
      grid.appendChild(h);
    });
    grid.appendChild(el("div", "mx-row-total-head", EN() ? "Total" : "合计"));

    LAYERS.forEach(function (L) {
      var rh = el("div", "mx-row-head mx-clickable");
      /* 行头竖条用层身份色：--mx-layer-color 是 matrix.css ::before 的取色口 */
      rh.style.setProperty("--mx-layer-color", LAYER_COLOR[L.id] || "var(--mx-border-strong)");
      rh.appendChild(el("div", "mx-layer-name", lName(L)));
      rh.appendChild(el("div", "mx-layer-hint", lHint(L)));
      /* 行头也是入口：点行头看这一层的全部文章（跨所有类型）。 */
      rh.setAttribute("role", "button");
      rh.setAttribute("tabindex", "0");
      rh.title = EN() ? "All " + lName(L) + " notes" : "看全部" + lName(L) + "文章";
      var openRow = function () { showAxisList(host, L, null); };
      rh.addEventListener("click", openRow);
      rh.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openRow(); }
      });
      grid.appendChild(rh);

      var rowTotal = 0;
      KINDS.forEach(function (k) {
        var c = cells[L.id + "|" + k.id];
        rowTotal += c.n;
        var cell = el("div", "mx-cell " + level(c.n));
        cell.setAttribute("data-layer", L.id);
        cell.setAttribute("data-kind", k.id);
        if (c.n === 0) {
          cell.classList.add("mx-empty");
          cell.appendChild(el("div", "mx-zero", EN() ? "·" : "空"));
          /* 空格子也给回应：页面承诺「点格子看文章」，点空的没反应等于
             承诺落空。说清这个方向是真空，比沉默好。 */
          cell.classList.add("mx-clickable");
          cell.addEventListener("click", function () { showEmptyCell(host, L, k); });
          cell.addEventListener("mouseenter", function (ev) { showTip(ev, L, k, c); });
          cell.addEventListener("mouseleave", hideTip);
        } else {
          /* 字数呈现：中文按万缩写、英文按 0k 缩写，先选定再进节点。 */
          // 字数格式化走 TKShell.fmtWords（site/shell.js 全站单一来源）：
          // ≥1万显示 x.x万，反之人头字；中英文案由 TKI18N.lang 驱动。
          var wordsText = TKShell.fmtWords(c.words);
          cell.appendChild(el("div", "mx-n", String(c.n)));
          cell.appendChild(el("div", "mx-words", wordsText));
          cell.addEventListener("mouseenter", function (ev) { showTip(ev, L, k, c); });
          cell.addEventListener("mouseleave", hideTip);
        }
        if (c.n > 0) {
          cell.classList.add("mx-clickable");
          cell.addEventListener("click", function () { showCell(host, L, k, c); });
        }
        grid.appendChild(cell);
      });

      var rt = el("div", "mx-row-total");
      rt.appendChild(el("div", "mx-n", String(rowTotal)));
      grid.appendChild(rt);
    });

    /* 列合计 */
    grid.appendChild(el("div", "mx-col-total-head", EN() ? "Total" : "合计"));
    KINDS.forEach(function (k) {
      var n = LAYERS.reduce(function (s, l) { return s + cells[l.id + "|" + k.id].n; }, 0);
      var t = el("div", "mx-col-total");
      t.appendChild(el("div", "mx-n", String(n)));
      grid.appendChild(t);
    });
    var grand = el("div", "mx-grand-total");
    /* 合计 = 两轴都归位的文章数，与导语、胶囊行同口径。原先用「未排除」
     * 总数，比六列合计多出分不出层次的那部分，同屏数字对不上。 */
    var gridTotal = inMatrix.filter(function (i) { return i.layer && i.kind; }).length;
    grand.appendChild(el("div", "mx-n", String(gridTotal)));
    grid.appendChild(grand);

    wrap.appendChild(grid);
    /* 色阶图例：业界共识「color without a legend is decoration」。
     * 四档蓝阶的断点与 level() 分档一致（改分档要同步改这里）。 */
    var legend = el("div", "mx-legend");
    legend.appendChild(el("span", "mx-leg-label", EN() ? "Scale: " : "色阶："));
    [["lv1", "1–2"], ["lv2", "3–7"], ["lv3", "8–15"], ["lv4", "16+"]].forEach(function (pair) {
      var chip = el("span", "mx-leg-chip");
      chip.style.background = "var(--mx-" + pair[0] + "-bg)";
      legend.appendChild(chip);
      legend.appendChild(el("span", "mx-leg-sep", pair[1]));
    });
    var gapChip = el("span", "mx-leg-chip mx-leg-gap");
    gapChip.style.background = "var(--mx-empty-hatch)";
    gapChip.style.border = "1px dashed rgba(214,69,69,.4)";
    legend.appendChild(gapChip);
    legend.appendChild(el("span", null, EN() ? "empty" : "空"));
    wrap.appendChild(legend);
    host.appendChild(wrap);
    return cells;
  }

  /* ── 悬浮提示：hover 格子先看精确值，点开才展开全部 ──────────────
   * tooltip 是「读数」，不是「操作」：只展示数字与方向名，点击行为
   * 留给 click。跟随鼠标，出界自动翻到左侧。 */
  var tipEl = null;
  function showTip(ev, L, k, c) {
    if (!tipEl) { tipEl = el("div", "mx-tip"); document.body.appendChild(tipEl); }
    var wordsText = TKShell.fmtWords(c.words);
    var head = lName(L) + " × " + kName(k);
    var body;
    if (c.n === 0) {
      body = EN()
        ? "0 notes — this direction is a gap"
        : "0 篇 —— 这个方向是缺口";
    } else {
      body = c.n + (EN() ? " notes · " : " 篇 · ") + wordsText;
    }
    tipEl.innerHTML = "<b>" + head + "</b><span class='mx-tip-sub'>" + body + "</span>";
    tipEl.classList.add("on");
    document.addEventListener("mousemove", moveTip);
    moveTip(ev);
  }
  function moveTip(e) {
    if (!tipEl) return;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + tipEl.offsetWidth > innerWidth - 8) x = e.clientX - tipEl.offsetWidth - 14;
    if (y + tipEl.offsetHeight > innerHeight - 8) y = e.clientY - tipEl.offsetHeight - 14;
    tipEl.style.left = x + "px"; tipEl.style.top = y + "px";
    tipEl.style.opacity = "1";
  }
  function hideTip() {
    if (tipEl) { tipEl.style.opacity = "0"; }
    document.removeEventListener("mousemove", moveTip);
  }

  /* 点开格子的公共骨架：关掉旧详情、建盒、装头部（标题 × 类型 | 摘要 | 关闭）、
     返回盒子。showCell 和 showEmptyCell 的开场六步原来各写一份，
     改一处漏一处的经典位置，收敛成一个函数。 */
  function detailBox(host, L, k, subText, empty) {
    var old = host.querySelector(".mx-detail");
    if (old) old.remove();
    var box = el("div", "mx-detail" + (empty ? " mx-detail--empty" : ""));
    var head = el("div", "mx-detail-head");
    /* 整行/整列清单时另一轴是 null：标题只显示有的那一轴。 */
    var title = L && k ? lName(L) + " × " + kName(k) : (L ? lName(L) : kName(k));
    head.appendChild(el("span", "mx-detail-title", title));
    head.appendChild(el("span", "mx-detail-sub", subText));
    var close = el("button", "mx-close", EN() ? "Close" : "关闭");
    close.addEventListener("click", closeDetail);
    head.appendChild(close);
    box.appendChild(head);
    return box;
  }

  /* 装载后统一收尾：入 DOM、滚到可见、写可分享的 hash。格子详情写
   * #cell=层|型；整行/整列清单另一轴是 null，写 #row=层 / #col=型。 */
  function mountDetail(host, box, L, k) {
    host.appendChild(box);
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      if (L && k) history.replaceState(null, "", "#cell=" + L.id + "|" + k.id);
      else if (L) history.replaceState(null, "", "#row=" + L.id);
      else if (k) history.replaceState(null, "", "#col=" + k.id);
    } catch (e) {}
  }

  /* 关闭详情 = 所见不再包含该格子/行列，hash 同步清掉（保留 search query，
     只动 fragment）。detailBox 里的关闭按钮挂这个收尾。 */
  function closeDetail() {
    var box = document.querySelector(".mx-detail");
    if (box) box.remove();
    try { if (/^#(cell|row|col)=/.test(location.hash)) history.replaceState(null, "", location.search); } catch (e) {}
  }

  /* 点开行头/列头：这一层（或这类知识）的全部文章，跨格子汇总。
   * 与 showCell 共用 detailBox 骨架；anchor 描述"这次列的是哪个方向"，
   * 让读者知道清单口径是整行/整列，比格子清单宽。 */
  function showAxisList(host, L, k) {
    var axis = L ? "layer" : "kind";
    var need = function (it) {
      return !it.excluded && it.layer && it.kind &&
        (L ? it.layer === L.id : it.kind === k.id);
    };
    var items = currentItems.filter(need);
    var head = L ? lName(L) : kName(k);
    var sub = EN()
      ? items.length + (items.length === 1 ? " note · " : " notes · ") +
        (L ? "all kinds at this layer" : "every layer holding this kind")
      : items.length + " 篇 · " +
        (L ? "这一层上全部类型的文章" : "所有层里这一类知识的文章");
    var box = detailBox(host, L, k, sub, false);
    /* 标题里补轴信息：只写层次名或类型名，读者不知道清单口径，
       anchor 行把"整行/整列"说清楚。 */
    var anchor = el("div", "mx-axis-anchor");
    anchor.textContent = EN()
      ? (L ? "Whole row: " : "Whole column: ") + head
      : (L ? "整行 · " : "整列 · ") + head;
    box.insertBefore(anchor, box.firstChild.nextSibling);
    var list = el("div", "mx-detail-list");
    items.slice().sort(function (a, b) { return b.words - a.words; })
      .forEach(function (it) {
        var row = el("div", "mx-detail-row");
        var a = el("a", "mx-detail-link", it.title);
        a.href = "/?path=" + encodeURIComponent(it.path);
        row.appendChild(a);
        row.appendChild(el("span", "mx-detail-words", it.words + (EN() ? " words" : "字")));
        if (it.guessed) row.appendChild(el("span", "mx-guess", EN() ? "layer inferred by keyword" : "层次靠关键词推断"));
        list.appendChild(row);
      });
    box.appendChild(list);
    mountDetail(host, box, L, k);
  }

  /* 点开格子：列出这个方向上的文章 */
  function showCell(host, L, k, c) {
    var sub = EN()
      ? c.n + (c.n === 1 ? " note · " : " notes · ") + c.words + " words · " + kHint(k)
      : c.n + " 篇 · " + c.words + " 字 · " + k.hint;
    var box = detailBox(host, L, k, sub, false);

    var list = el("div", "mx-detail-list");
    c.items.slice().sort(function (a, b) { return b.words - a.words; })
      .forEach(function (it) {
        var row = el("div", "mx-detail-row");
        var a = el("a", "mx-detail-link", it.title);
        /* /?path= 是 SPA 路由唯一认的文章参数（selectFromUrl），
           之前写 /?note= 点了直接落回首页 —— 深链成了死链。 */
        a.href = "/?path=" + encodeURIComponent(it.path);
        row.appendChild(a);
        row.appendChild(el("span", "mx-detail-words", it.words + (EN() ? " words" : "字")));
        if (it.guessed) row.appendChild(el("span", "mx-guess", EN() ? "layer inferred by keyword" : "层次靠关键词推断"));
        list.appendChild(row);
      });
    box.appendChild(list);
    mountDetail(host, box, L, k);
  }

  /* 点开空格子：没有文章可列，说清这个方向是真空、值不值得补 */
  function showEmptyCell(host, L, k) {
    var box = detailBox(host, L, k, EN() ? "0 notes · " + kHint(k) : "0 篇 · " + k.hint, true);
    var body = el("div", "mx-detail-empty-body");
    body.appendChild(el("p", null,
      EN()
        ? "This direction is still empty: not a single note on " + lName(L) + " × " + kName(k) + "."
        : "这个方向还是空的：一篇「" + L.name + " × " + k.name + "」的文章都没有。"));
    body.appendChild(el("p", "mx-detail-empty-hint",
      EN()
        ? kHint(k) + " knowledge is a vacuum at the " + lName(L) + " layer — the first note to fill this gap starts here."
        : k.hint + "的知识在「" + L.name + "」层是真空 —— 要补文，从这一格开始写第一篇。"));
    box.appendChild(body);
    mountDetail(host, box, L, k);
  }

  /* ── 类型速览胶囊：全景页顶部的“按知识类型通读”入口 ──────────────
   * 词元这类整列只有几篇的类型，藏在矩阵列头里仍不够显眼（列头是
   * 分析视图的一部分，读者第一眼在读导语与色阶）。胶囊行放在 tabs
   * 之下、导语之上——进页面第一屏就能看到 6 个类型各自的门。
   * 数据与列合计同口径（classifyAll 后非 excluded 的 kind 计数），
   * 点击走 showAxisList（与列头同一入口、同一 #col= 深链），
   * 不造第二套交互。 */
  function renderKindPills(host, items) {
    var old = host.querySelector(".mx-kind-pills");
    if (old) old.remove();
    var box = el("div", "mx-kind-pills");
    box.appendChild(el("span", "mx-kind-pills-label",
      EN() ? "Read by kind: " : "按知识类型通读："));
    KINDS.forEach(function (k) {
      var n = items.filter(function (it) {
        /* 口径与 showAxisList 完全一致（layer && kind 都有才算）：
         * 有 kind 没 layer 的文章不进矩阵格子，也就不该被胶囊计入，
         * 否则胶囊数字 ≠ 列合计 ≠ 点开清单的条数，三处对不上。 */
        return !it.excluded && it.layer && it.kind === k.id;
      }).length;
      var pill = el("button", "mx-kind-pill");
      pill.type = "button";
      pill.appendChild(el("span", "mx-kind-pill-name", kName(k)));
      pill.appendChild(el("span", "mx-kind-pill-n", String(n)));
      pill.title = EN()
        ? "All " + kName(k) + " notes (" + kHint(k) + ")"
        : "看全部" + kName(k) + "文章（" + kHint(k) + "）";
      var open = function () { showAxisList(host, null, k); };
      pill.addEventListener("click", open);
      box.appendChild(pill);
    });
    host.appendChild(box);
  }

  /* 打开带 hash 的链接时自动展开：#cell=层|型 开格子，#row=层 / #col=型
   * 开整行/整列清单。深链和页面状态对得上，分享出去才不打折扣。 */
  function openFromHash(cells) {
    var m = /#cell=([a-z]+)\|([a-z]+)/.exec(location.hash || "");
    if (m) {
      var L = LAYERS.filter(function (x) { return x.id === m[1]; })[0];
      var k = KINDS.filter(function (x) { return x.id === m[2]; })[0];
      var c = cells[m[1] + "|" + m[2]];
      if (!L || !k || !c || !c.n) return false;
      var host = document.getElementById("panorama-body");
      if (host) showCell(host, L, k, c);
      return true;
    }
    var r = /#row=([a-z]+)/.exec(location.hash || "");
    if (r) {
      var RL = LAYERS.filter(function (x) { return x.id === r[1]; })[0];
      if (!RL) return false;
      var hostR = document.getElementById("panorama-body");
      if (hostR) showAxisList(hostR, RL, null);
      return true;
    }
    var c2 = /#col=([a-z]+)/.exec(location.hash || "");
    if (c2) {
      var CK = KINDS.filter(function (x) { return x.id === c2[1]; })[0];
      if (!CK) return false;
      var hostC = document.getElementById("panorama-body");
      if (hostC) showAxisList(hostC, null, CK);
      return true;
    }
    return false;
  }

/* 缺口清单：把空格子念出来，别让读者自己在图上找。
   * 原先一条缺口一行、14 行常驻在矩阵下方，其中四行「×× × 词汇与词源」
   * 讲的是同一件事，页尾比矩阵本身还长。现在折成一行汇总（数字照旧摆在
   * 眼前），展开后按类型归组：一条类型一行，成员收成标签。 */
  function renderGaps(host, cells, items) {
    var empties = Object.keys(cells).map(function (k) { return cells[k]; })
      .filter(function (c) { return c.n === 0; });
    var thin = Object.keys(cells).map(function (k) { return cells[k]; })
      .filter(function (c) { return c.n > 0 && c.n <= 2; });

    var box = el("div", "mx-gaps");
    var head = el("button", "mx-gaps-head");
    head.type = "button";
    head.setAttribute("aria-expanded", "false");
    head.setAttribute("aria-label", EN() ? "Toggle the missing-direction list" : "展开或收起漏掉的方向");
    head.appendChild(el("span", "mx-gaps-caret", "▸"));
    head.appendChild(el("span", "mx-gaps-title", EN() ? "Missing directions" : "漏掉的方向"));
    var stat = el("span", "mx-gaps-stat");
    if (empties.length) {
      stat.appendChild(el("span", "mx-gaps-count mx-count-empty",
        (EN() ? "empty " : "空格 ") + empties.length));
    }
    if (thin.length) {
      stat.appendChild(el("span", "mx-gaps-count mx-count-thin",
        (EN() ? "thin " : "单薄 ") + thin.length));
    }
    head.appendChild(stat);
    box.appendChild(head);

    var body = el("div", "mx-gaps-body");
    body.hidden = true;

    if (empties.length === 0 && thin.length === 0) {
      body.appendChild(el("div", "mx-gaps-none", EN() ? "No empty cells" : "没有空格子"));
    }

    /* 空格按类型归组：一个类型一条，层次收成标签。 */
    if (empties.length) {
      var byKind = {};
      empties.forEach(function (c) { (byKind[c.kind] = byKind[c.kind] || []).push(c); });
      Object.keys(byKind).forEach(function (kid) {
        var k = KINDS.filter(function (x) { return x.id === kid; })[0];
        var group = el("div", "mx-gaps-group");
        var gh = el("div", "mx-gaps-group-head");
        gh.appendChild(el("span", "mx-gaps-mark mx-mark-empty", "✗"));
        gh.appendChild(el("span", "mx-gaps-group-name", kName(k)));
        gh.appendChild(el("span", "mx-gaps-group-note", EN()
          ? byKind[kid].length + (byKind[kid].length === 1 ? " layer empty" : " layers empty")
          : byKind[kid].length + " 层全空"));
        group.appendChild(gh);
        var chips = el("div", "mx-gaps-chips");
        byKind[kid].forEach(function (c) {
          var L = LAYERS.filter(function (x) { return x.id === c.layer; })[0];
          var chip = el("button", "mx-gap-chip mx-gap-chip--empty", lName(L));
          chip.type = "button";
          chip.title = lName(L) + " × " + kName(k) + (EN() ? " — nothing here" : " —— 一篇都没有");
          /* 点标签进 showEmptyCell 详情盒，与网格里点空格的行为完全一致
           * （含 hash 深链）。 */
          chip.addEventListener("click", function () { showEmptyCell(host, L, k); });
          chips.appendChild(chip);
        });
        group.appendChild(chips);
        body.appendChild(group);
      });
    }

    /* 单薄按篇数归组：1 篇一组、2 篇一组，成员需要带上层次名才认得出方向。 */
    if (thin.length) {
      var byN = {};
      thin.forEach(function (c) { (byN[c.n] = byN[c.n] || []).push(c); });
      Object.keys(byN).sort(function (a, b) { return a - b; }).forEach(function (key) {
        var num = Number(key);
        var group = el("div", "mx-gaps-group");
        var gh = el("div", "mx-gaps-group-head");
        gh.appendChild(el("span", "mx-gaps-mark mx-mark-thin", "!"));
        gh.appendChild(el("span", "mx-gaps-group-name", num + (EN() ? (num === 1 ? " note" : " notes") : " 篇")));
        gh.appendChild(el("span", "mx-gaps-group-note", EN() ? "can't carry a direction" : "撑不起一个方向"));
        group.appendChild(gh);
        var chips2 = el("div", "mx-gaps-chips");
        byN[key].forEach(function (c) {
          var L = LAYERS.filter(function (x) { return x.id === c.layer; })[0];
          var k = KINDS.filter(function (x) { return x.id === c.kind; })[0];
          var chip = el("button", "mx-gap-chip mx-gap-chip--thin", lName(L) + " × " + kName(k));
          chip.type = "button";
          chip.title = EN()
            ? kHint(k) + " at " + lName(L) + " — " + num + (num === 1 ? " note" : " notes") + ", too thin to carry the direction"
            : k.hint + "在「" + L.name + "」只有 " + num + " 篇，撑不起这个方向";
          chip.addEventListener("click", function () { showCell(host, L, k, c); });
          chips2.appendChild(chip);
        });
        group.appendChild(chips2);
        body.appendChild(group);
      });
    }

    head.addEventListener("click", function () {
      var opening = body.hidden;
      body.hidden = !opening;
      head.setAttribute("aria-expanded", String(opening));
    });
    box.appendChild(body);
    host.appendChild(box);
  }

  window.TKMatrixView = { render: renderMatrix, renderGaps: renderGaps, openFromHash: openFromHash, renderKindPills: renderKindPills };
})();
