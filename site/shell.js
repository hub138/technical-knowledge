/* The one page shell: sidebar, theme, feedback.
 *
 * Why this file exists. There used to be two implementations of the same three
 * things. The main site built its sidebar from static HTML in index.html and
 * filled it in with renderSharedNav(); workbench.js built an equivalent sidebar
 * in JS and inserted it. Both read the same navigation data (site/nav.js) but
 * wrote different class names, so the sidebar changed shape when you clicked
 * through to 项目与教学 — and because each side appended the /insights entry
 * with its own separate fetch, a fix on one side never reached the other.
 *
 * Now there is one renderer. Both page kinds call it and get the same markup.
 *
 * Load this synchronously, after nav.js. The sidebar has to exist before the
 * first paint, or the nav visibly pops in.
 */
(() => {
  "use strict";

  const THEME_KEY = "tk-theme";
  const FB_NAME_KEY = "tk-feedback-name";
  const FEEDBACK_MAX = 4000;

  /* ── 全站共享小工具 ──────────────────────────────────────────────────────
   * tr / esc / el 以前散落在各视图文件里各写一份（panorama-view 一份 esc+el，
   * matrix-view 一份 el，本文件三处 tr、index.html 四处 tr），同一件事
   * 五种写法，改 HTML 逃逸规则要改五处。收敛到这里一份，视图文件改为
   * 引用 TKShell.tr / TKShell.esc / TKShell.el。
   *
   * tr：i18n 词典查询。TKI18N 永远先于本文件加载（见各页 script 顺序），
   *      但仍留空值回退，脚本顺序调整时不会炸。
   * esc：HTML 逃逸，用于 innerHTML 拼接前的动态文本。
   * el：createElement 快捷方式，(标签, class, 文本) 三参。 */
  const tr = (x) => (window.TKI18N ? window.TKI18N.t(x) : x);
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (m) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
    ));
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  /* Default page metadata. A page can override any of these by passing them to
     sidebar().
     description 从 TK_NAV 派生：菜单 tooltip 和子页面页头说的是同一句话，
     文案唯一真源在 site/nav.js——之前这里内嵌了一份带句号的旧副本，
     两处各存一份迟早说两样话（实际发生过：nav 去了尾句号、这里没有）。
     title 留在这里不派生：浏览器标签页用正式名（外部资源），菜单用口语名
     （优质好文），是有意的差异。 */
  const NAV_DESC = {};
  (window.TK_NAV.items || []).forEach(function (it) { NAV_DESC[it.key] = it.description; });
  const PAGE_META = {
    knowledge: { title: "知识库", description: NAV_DESC.knowledge },
    graph: { title: "知识图谱", description: NAV_DESC.graph },
    papers: { title: "论文追踪", description: NAV_DESC.papers },
    sources: { title: "外部资源", description: NAV_DESC.sources },
    projects: { title: "项目与教学", description: NAV_DESC.projects },
    evaluation: { title: "Agent 评估", description: NAV_DESC.evaluation },
    insights: { title: "访问与反馈", description: NAV_DESC.insights },
    learning: { title: "学习中心", description: NAV_DESC.learning },
    classrooms: { title: "我的课堂", description: NAV_DESC.classrooms },
  };

  /* Which nav entry the current URL belongs to.
   *
   * Most pages are reachable at exactly the href in nav.js. The learning pages
   * are the exception: /learn and /learn/history are the canonical links, but
   * the same pages are also served from /apps/learning/*, so both forms have to
   * map to the same key or the active entry goes unmarked.
   */
  const PATH_OWNER = [
    { key: "papers", match: (p) => p === "/papers" || p.startsWith("/papers/") },
    { key: "sources", match: (p) => p === "/sources" || p.startsWith("/sources/") },
    { key: "insights", match: (p) => p === "/insights" },
    { key: "evaluation", match: (p) => p.startsWith("/apps/agent-evaluation") },
    { key: "projects", match: (p) => p === "/projects" || p.startsWith("/projects/") },
    {
      key: "classrooms",
      match: (p) => p.startsWith("/learn/history") || p.startsWith("/apps/learning/history"),
    },
    {
      key: "learning",
      match: (p) =>
        p.startsWith("/learn") || /^\/apps\/learning\/(index|openmaic|intuition|transfer)/.test(p),
    },
  ];

  const items = () => (window.TK_NAV && window.TK_NAV.items) || [];

  const keyForPath = (path) => {
    const owner = PATH_OWNER.find((entry) => entry.match(path));
    return (owner && owner.key) || "knowledge";
  };

  const metaFor = (key) => {
    const item = items().find((i) => i.key === key);
    const pageMeta = PAGE_META[key] || {};
    return {
      key,
      label: (item && item.label) || pageMeta.title || key,
      title: pageMeta.title || (item && item.label) || key,
      description: pageMeta.description || "",
    };
  };

  /* ── Theme ────────────────────────────────────────────────────────────────
   * An explicit choice is remembered; until the visitor makes one, follow the
   * OS and keep following it. Runs as the first statement below so the correct
   * theme is on <html> before the first paint — this is what the companion
   * pages used to get from a per-page inline script, and what the main site
   * was missing (it flashed light in dark mode).
   */
  const media = window.matchMedia("(prefers-color-scheme: dark)");

  /* ?theme=dark|light 深链：只影响本次视图，不写入 localStorage。
   * 用途：截图验证两种主题不必手动点开关。显式选择仍以 localStorage 为准。 */
  const urlTheme = (() => {
    try {
      const t = new URLSearchParams(location.search).get("theme");
      return t === "dark" || t === "light" ? t : null;
    } catch (err) {
      return null;
    }
  })();

  const storedTheme = () => {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (err) {
      return null;
    }
  };

  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark";
    document.querySelectorAll("[data-tk-theme-label]").forEach((node) => {
      node.textContent = tr(dark ? "白天模式" : "夜晚模式");
    });
    document.querySelectorAll("[data-tk-theme-icon]").forEach((node) => {
      /* lucide 线条图标，与 BestBlogs 右上角同源同风格。
       * 显示的是"当前状态"而不是"将要切到什么"：白天显示太阳、夜晚显示
       * 月亮 —— 字符 ☀/☾ 在不同字体里基线漂移、粗细不一，观感廉价；
       * SVG 描边图标颜色跟 currentColor，两种主题下都干净。 */
      const SUN =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>';
      const MOON =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg>';
      node.innerHTML = dark ? MOON : SUN;
    });
    document.querySelectorAll("[data-tk-theme-toggle]").forEach((node) => {
      node.setAttribute("aria-pressed", String(dark));
    });
  };

  applyTheme(urlTheme || storedTheme() || (media.matches ? "dark" : "light"));

  media.addEventListener("change", (event) => {
    if (!storedTheme()) applyTheme(event.matches ? "dark" : "light");
  });

  const toggleTheme = () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (err) {
      /* private mode — the choice just will not persist */
    }
    applyTheme(next);
  };

  /* Any element carrying data-tk-theme-toggle becomes a toggle. The main site
     has one in its top bar; the companion pages have none in their markup, so
     ensureThemeToggle() creates the fixed one for them. */
  const wireThemeToggles = (root = document) => {
    root.querySelectorAll("[data-tk-theme-toggle]").forEach((node) => {
      node.addEventListener("click", toggleTheme);
    });
  };

  /* Companion pages have no top bar of their own, so they get the toggle pinned
     to the viewport's top-right. Called by the shell once the DOM is ready.
     Does nothing when the page already provides a toggle. */
  const ensureThemeToggle = () => {
    if (document.querySelector("[data-tk-theme-toggle]")) return null;
    /* 右上角的控件组：语言 + 日夜模式。
     *
     * 原来语言切换在侧栏底部、日夜模式浮在右上角，两个都是全局开关却分在两处。
     * 放一起的道理是：它们回答同一类问题（"我看到的这个站，怎么呈现给我"），
     * 和"我在哪一页"无关，所以不该混在导航里。
     *
     * 尺寸从 34px 提到 38px —— 原来偏小，和 13px 的图标挤在一起像贴纸。
     */
    const group = document.createElement("div");
    group.className = "tk-controls";
    group.setAttribute("aria-label", "显示设置");

    const lang = document.createElement("button");
    lang.type = "button";
    lang.className = "tk-control";
    lang.dataset.tkLangToggle = "";
    lang.title = "切换语言";
    /* 地球图标（lucide）+ 语言文字：图标按钮先认形状再认字，
     * 纯文字按钮在这排小控件里显得空。 */
    lang.innerHTML =
      '<svg class="tk-control-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>' +
      '<span class="tk-control-text" data-tk-lang-label>中文</span>';

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tk-control";
    btn.dataset.tkThemeToggle = "";
    btn.setAttribute("aria-live", "polite");
    btn.title = "切换日夜模式";
    btn.innerHTML =
      '<span data-tk-theme-icon aria-hidden="true"></span>' +
      '<span data-tk-theme-label></span>';

    group.append(lang, btn);
    document.body.appendChild(group);
    applyTheme(document.documentElement.dataset.theme || "light");
    wireThemeToggles(document);
    /* 【rt23】控件组挂在 body 尾部，而 sidebar() 的重译传的是 mount（侧栏），
       root 范围盖不到这里——站点导航页之外的所有页面（evaluation 等
       companion 页）右上角"显示设置/切换日夜模式"三属性从未被翻译过。
       这里补一次以 group 为 root 的重译。语言按钮自己的 label 由
       paintLangButtons 接管（wireLangToggles 会在切换时重绘），不受影响。 */
    if (window.TKI18N) window.TKI18N.translateDOM(group);
    // 语言按钮走的是全局代理，i18n.js 会接管带这个属性的按钮。
    if (window.TKI18N && window.TKI18N.wireLangToggles) window.TKI18N.wireLangToggles(group);
    return group;
  };

  /* ── Owner-only access, resolved before the first paint ──────────────────
   * The request is kicked off the moment this script parses, and the answer is
   * cached. sidebar() consults the cache synchronously, so on a warm load the
   * nav renders with all five entries at once instead of growing a fifth a
   * frame later. On a cold load the promise path still appends it, which is
   * the old behaviour and the right fallback.
   */
  const stamped = document.querySelector('meta[name="tk-local-client"]');
  const operatorStamped = document.querySelector('meta[name="tk-operator"]');
  const accessState = {
    /* The server stamps this into the HTML, so it is readable before any
       fetch — which is what removes the 4-then-5 flicker. The fetch below
       remains as the fallback for a page served without the stamp (an old
       cached copy, or a file opened off disk). local 在这里的意思是
       "能看到运营者条目"：真本机，或持运营者 cookie（反代架构下运营者
       从任何域名访问都算，服务端已验证签名）。 */
    known: stamped !== null,
    local: stamped
      ? stamped.getAttribute("content") === "1" ||
        Boolean(operatorStamped && operatorStamped.getAttribute("content") === "1")
      : false,
  };
  const accessReady = fetch("/api/access", { cache: "no-store" })
    .then((response) => (response.ok ? response.json() : {}))
    .then((access) => {
      accessState.known = true;
      accessState.local = Boolean(access && (access.local_client || access.operator));
      return accessState.local;
    })
    .catch(() => {
      /* No answer means no entry. Better to omit a link than to hand a
         visitor the operations page. */
      accessState.known = true;
      return false;
    });

  const appendLocalEntries = (mount, page, link) => {
    const nav = mount.querySelector(".tk-nav");
    if (!nav) return;
    const local = items().filter((i) => i.localOnly);
    if (!local.length) return;
    if (nav.querySelector('[data-tk-local="1"]')) return; // idempotent
    nav.insertAdjacentHTML(
      "beforeend",
      local
        .map((item) => link(item, page).replace("<a ", '<a data-tk-local="1" '))
        .join(""),
    );
  };

  /* ── Sidebar ──────────────────────────────────────────────────────────────
   * opts:
   *   page        nav key that owns this page; inferred from the URL if absent
   *   context     show the "当前位置" block (companion pages)
   *   subnav      array of nav keys to render nested under 项目与教学
   *   auth        show the 退出 link (companion pages have a session)
   *   onNavClick  handler receiving (event, item) so a page can intercept a
   *               link — the main site uses this for the in-page graph view
   */
  const sidebar = (opts = {}) => {
    const page = opts.page || (() => {
      /* 三个视图（graph / panorama / progress）的 pathname 全是 `/`，
         keyForPath 只会把它们都归到 knowledge，侧栏高亮就落在「知识库」上。
         这里先按 ?view= 认出它们，其余路径才交给 keyForPath。 */
      const q = new URLSearchParams(location.search);
      if (location.pathname === "/") {
        const view = q.get("view");
        if (view === "graph" || view === "panorama" || view === "progress") return view;
      }
      return keyForPath(location.pathname);
    })();
    const meta = metaFor(page);

    /* 站点标记。
     *
     * 换过两版。第一版是一个字母 K 装在方块里（"没有 logo 时先放个占位"的做法）；
     * 第二版是三个圆点连成一条线 —— 想表达"知识图谱"，但在 24px 里三个小圆
     * 加三根细线全糊在一起，显得碎。参考站的做法相反：都在用一个**单一、
     * 完整的形状**。
     *
     * 这一版用层叠：三层圆角矩形错开，前面一层是实心的，后面两层是描边。
     * 表达的是这个库的核心 —— 一层层堆起来的工程知识，以及它们之间
     * 相互支撑的关系。形状完整、有纵深，缩到 24px 也认得出来。
     */
    const brand = `
      <a class="tk-brand" href="/" aria-label="返回工程知识库">
        <span class="tk-brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <rect x="7.4" y="3.6" width="13" height="13" rx="3"
                  stroke="currentColor" stroke-width="1.5" opacity="0.38"/>
            <rect x="5.2" y="5.8" width="13" height="13" rx="3"
                  stroke="currentColor" stroke-width="1.5" opacity="0.66"/>
            <rect x="3" y="8" width="13" height="13" rx="3" fill="currentColor"/>
          </svg>
        </span>
        <span class="tk-brand-text"><strong>工程知识库</strong><small>技术知识图谱</small></span>
      </a>`;

    /* Public entries come straight from nav.js. Items with a parent belong to
       a sub-nav, not the primary list; the localOnly ones are held back here
       and appended below only once /api/access confirms this is the owner's
       machine. */
    /* pinned 项（站长钉选，当前为知识全景）常驻高亮：与当前态同一套
       视觉语言但永远亮着——它回答"从哪开始看"，不是"你在哪"。
       暖橙底色即推荐标记，与当前位置（实底框）两套语义互不混淆。 */
    const link = (item, current, extraClass = "") => `
      <a href="${item.href}" class="${item.pinned ? "tk-nav-pinned" : ""}"${item.key === current ? ' aria-current="page"' : ""}
         title="${item.title || item.label}">${
           `<span class="tk-nav-icon${extraClass}" aria-hidden="true">${item.icon}</span>`
         }<span>${item.label}</span></a>`;

    /* 带 group 的项归到同名分组里，用一条小标题隔开。
     *
     * 为什么分组而不是平铺：知识图谱 / 知识全景 / 掌握进度 都是 `/` 的子视图，
     * 回答的是同一个问题——"这个库从哪个角度看"。它们和论文追踪、优质好文
     * 这类外部来源不是一类东西，平铺在一起读不出这层关系，九个项看着像
     * 九个互不相干的页面。
     *
     * 为什么不折叠成二级：这三个是高频入口，藏进折叠菜单等于让它们消失。
     * 分组只是加一条小标题，点击成本不变。
     *
     * 组顺序按 items 里第一次出现的顺序，所以改顺序改 nav.js 就行。 */
    const grouped = [];
    items().forEach((item) => {
      if (item.localOnly || item.parent) return;
      const g = item.group;
      /* 【2026-09-22 修 TDZ 后遗留的渲染崩溃】无分组项也必须压成 items 数组：
       * 原来压 { group: null, item }（单数字段），而下方 navHtml 对每个
       * entry 统一走 entry.items.map —— 无分组项的 items 是 undefined，
       * 第一个导航项（知识库）就抛 TypeError，侧栏整体渲染中断，页面只剩
       * 空壳（浏览器实测报错：shell.js:379 Cannot read properties of
       * undefined (reading 'map')）。统一形状：每个 entry 都是
       * { group, items: [...] }，navHtml 不再需要区分两种字段名。 */
      if (!g) { grouped.push({ group: null, items: [item] }); return; }
      const last = grouped[grouped.length - 1];
      if (last && last.group === g) last.items.push(item);
      else grouped.push({ group: g, items: [item] });
    });

    /* 【2026-09-22 学习子项重排】子项直接内联挂在父项链接之后：
     *
     * 原来的做法是渲染成一个独立的 .tk-subnav <nav> 块，插在主导航后面 ——
     * 视觉上"学习"浮在导航最底部，和它的父项「项目与教学」隔着整列导航，
     * 读不出从属关系（用户明令：侧边栏就放在项目与教学下面，固定可展开的
     * 这种格式）。
     *
     * 现在的规则：遍历分组结果时，凡是 key 命中 subnavKeys 的项，在它自己
     * 的链接后面直接续上子项链接。子项样式沿用 .tk-subnav a 的缩进+左线
     * 语言（CSS 里 .tk-nav a.has-children + .tk-subnav-inline 接管），
     * 不再需要独立容器，「项目与教学」点开下面就是学习中心/我的课堂，
     * 全站每一页都这么渲染（不再由 opts.subnav 决定哪些页显示）。
     */
    const GROUP_LABEL = { views: "视角" };

    /* 子项集合从调用方参数改为全局常驻：nav.js 的 subitems 是唯一真源。
     * 保留 opts.subnav 作为覆盖入口（旧调用传了也不破坏），但默认全站渲染。
     * 定义必须在 navHtml 之前 —— const 有暂时性死区，放后面 navHtml 里
     * 引用会直接 ReferenceError。 */
    const subnavKeys = opts.subnav || (window.TK_NAV.subitems || []);

    /* 按父项 key 取子项列表。必须用 nav.js 的 parent 字段过滤 ——
     * parent 是子项归属的唯一真源。第一版只 map 出 subnavKeys 对应的
     * 子项、没有按 parentKey 匹配，导致每个主导航项后面都挂上全部
     * 子项（实测「学习中心/我的课堂」错挂在知识库/论文追踪/优质好文/
     * Agent 评估下面，用户截图指出）。 */
    const childrenOf = (parentKey) =>
      subnavKeys
        .map((key) => items().find((i) => i.key === key))
        .filter((child) => child && child.parent === parentKey);

    const navHtml = grouped
      .map((entry) => {
        if (!entry.group) {
          /* 无分组项：父项链接后接折叠子项组（学习中心/我的课堂挂在
           * 「项目与教学」下）。默认折叠（hidden），点父项展开；
           * 当前页正是某个子项时由下方 JS 移除 hidden 自动展开。
           * data-subgroup 值 = 父项 key，JS 据此找容器。
           * 箭头用 aria-expanded 驱动 CSS 旋转（▸ 收起 / ▾ 展开，
           * 语义分工见 tokens.css 箭头图注）。 */
          return entry.items
            .map((item) => {
              const kids = childrenOf(item.key);
              if (!kids.length) return link(item, page);
              return (
                /* tk-nav-row：箭头按钮的定位锚。toggle 是 a 的兄弟节点，
                   之前 absolute 相对了整个 nav，箭头飞到「知识库」行右侧
                   （实测截图）；包一层 relative 行，箭头贴回本行行尾。 */
                `<span class="tk-nav-row">`
                + link(item, page, " has-children")
                + `<button type="button" class="tk-subnav-toggle" data-subgroup="${item.key}" aria-expanded="false" aria-label="展开 ${item.label} 的子项"></button>`
                + `</span>`
                + `<span class="tk-subnav-group" id="subgroup-${item.key}" data-subgroup="${item.key}" hidden>${kids
                    .map(
                      (child) =>
                        `<a class="tk-subnav-inline" href="${child.href}"${
                          child.key === page ? ' aria-current="page"' : ""
                        } title="${child.title || child.label}"><span class="tk-nav-icon tk-nav-icon--sub" aria-hidden="true">${child.icon}</span><span>${child.label}</span></a>`,
                    )
                    .join("")}</span>`
              );
            })
            .join("");
        }
        const label = GROUP_LABEL[entry.group] || entry.group;
        return (
          `<p class="tk-nav-group-label" aria-hidden="true">${label}</p>` +
          entry.items.map((item) => link(item, page)).join("")
        );
      })
      .join("");



    const mount = opts.mount || document.getElementById("tk-sidebar");
    if (!mount) return null;

    /* Put the theme on <html> before the sidebar markup exists.
     *
     * Why this ordering matters: base.css styles the dark sidebar through
     * `:root[data-theme="dark"] .tk-nav a`. That selector depends on an
     * ancestor attribute, and if the nodes are built while <html> carries no
     * data-theme, Chrome resolves their colour once against the light tokens
     * and does not re-resolve when the attribute lands a moment later. The
     * nav then keeps light-theme colours on the dark sidebar — measured as
     * 1.36:1 with scripts/contrast_audit.py, which is what caught this. */
    applyTheme(document.documentElement.dataset.theme || storedTheme() || (media.matches ? "dark" : "light"));

    mount.className = "tk-sidebar";
    mount.setAttribute("aria-label", "站点导航");
    mount.innerHTML = `
      ${opts.mobileMenu ? `<div class="tk-brand-row">${brand}<button type="button" class="tk-mobile-menu" id="mobile-menu" aria-label="打开目录">目录</button></div>` : brand}
      <nav class="tk-nav" id="tk-nav">
        ${navHtml}
      </nav>
      <!-- 知识树槽位。
           首页把领域/主题两级导航渲染在 #domains 里；其余页面原来没有这个
           容器，于是侧栏在换页时凭空少掉一半 —— 读者会以为坏了，而不是
           理解成「这一页不显示知识树」。现在容器始终存在，有数据的页面填，
           没数据的页面自然为空，形状不变。

           顺序：知识树在「当前位置」块**上面**。
           这一块是导航，读者点它的频率远高于读说明；而被推到下面的
           说明块会把域树挤出视口（实测学习页要滚动才看得到 AI系统 那几项）。 -->
      <div class="tk-domains" id="domains"></div>
      ${
        opts.context
          ? `<div class="tk-context">
        <p class="tk-context-label">当前位置</p>
        <h2>${meta.title}</h2>
        <p>${meta.description}</p>
      </div>`
          : ""
      }
      <div class="tk-sidebar-footer">
        <div class="tk-utility">
          ${opts.auth ? '<a class="tk-utility-btn" href="/auth/logout">退出</a>' : ""}
          <!-- 语言切换已经移到右上角的控件组（见 TKShell.ensureThemeToggle）。
               侧栏底部只留退出这类和身份相关的操作，
               显示设置不再混在导航里。 -->
        </div>
      </div>
    `;

    if (opts.onNavClick) {
      mount.querySelectorAll(".tk-nav a, .tk-subnav a").forEach((anchor) => {
        anchor.addEventListener("click", (event) => {
          const item = items().find((i) => i.href === anchor.getAttribute("href"));
          if (item) opts.onNavClick(event, item);
        });
      });
    }

    /* 【2026-09-22 子项折叠】「项目与教学」的子项默认收起，点父项行展开。
     *
     * 为什么不让子项常驻展开（第一版的做法）：用户原话「为啥默认展开」，
     * 期望就是普通的折叠组 —— 平时收起不占地方，要用时点一下。
     *
     * 交互细节：
     * - toggle 按钮和父项链接都能切换（点链接去 /projects 的同时也展开，
     *   不拦默认跳转 —— 展开状态靠下面 localStorage 记住，跳回来还在）；
     * - 当前页正是子项（/learn、/learn/history）时自动展开，否则用户落进
     *   一个看不到当前位置的导航；
     * - 展开状态存 localStorage（key 按父项 key），全站一致，换页不闪。 */
    mount.querySelectorAll(".tk-subnav-toggle").forEach((toggle) => {
      const parentKey = toggle.dataset.subgroup;
      const group = mount.querySelector(`.tk-subnav-group[data-subgroup="${parentKey}"]`);
      if (!group) return;

      const setOpen = (open) => {
        group.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
      };

      /* 初始态：只在当前页正是本组子项时展开，其余一律收起。
       *
       * 之前把展开状态记进 localStorage，结果点开过一次就永久展开——
       * 每次进站「项目与教学」都是张开的，侧边栏越来越长（2026-09-23 反馈）。
       * 折叠子项的价值就是默认不占地方，要展开就这一次点一下。 */
      const childKeys = (window.TK_NAV.subitems || []);
      const onChildPage = childKeys.some((key) => {
        const child = items().find((i) => i.key === key);
        return child && child.parent === parentKey && child.key === page;
      });
      setOpen(onChildPage);

      toggle.addEventListener("click", () => setOpen(group.hidden));
      /* 父项链接也负责展开（不拦跳转）：点「项目与教学」过去时顺手展开，
         符合"这个分类下面有什么"的预期。 */
      const parentLink = mount.querySelector(`.tk-nav a[href="${(items().find((i) => i.key === parentKey) || {}).href}"]`);
      if (parentLink) parentLink.addEventListener("click", (event) => {
        /* 父项行点击 = 双向 toggle：组已展开且当前就在本组 → 折叠并拦下
           跳转（不然用户点「项目与教学」永远只能展开、找不到关闭方式——
           实测反馈）；组收起 → 展开并正常跳转过去。行尾的小箭头按钮保留，
           作为纯折叠控件。 */
        const onGroupPage = page === parentKey || childKeys.some((key) => {
          const child = items().find((i) => i.key === key);
          return child && child.parent === parentKey && child.key === page;
        });
        if (!group.hidden) {
          event.preventDefault();
          setOpen(false);
        } else {
          setOpen(true);
          if (onGroupPage) event.preventDefault();
        }
      });
    });

    /* Re-assert the theme now that the nodes are in the document. See the note
       above applyTheme() earlier in this function for why the freshly inserted
       subtree needs it. */
    applyTheme(document.documentElement.dataset.theme || "light");

    /* 知识树，给非首页的页面用。
     *
     * 首页自己渲染完整的领域树（带展开状态和即时筛选），因为它手里有
     * 全部笔记。其余页面拿不到那些状态，但至少要显示「这个库有哪些领域、
     * 各多少篇」—— 侧栏是全局导航，换页时少掉一半会让人以为坏了。
     *
     * 这里渲染的是链接版：点一下回首页并筛到那个领域。不做本地展开，
     * 因为子页面没有笔记数据，展开也没东西可显示。
     */
    if (opts.knowledgeTree !== false) {
      fetch("/api/domains", { cache: "no-store" })
        .then((response) => (response.ok ? response.json() : null))
        .then((payload) => {
          const rows = (payload && payload.domains) || [];
          const slot = mount.querySelector("#domains");
          if (!slot || !rows.length) return;
          /* data-domain：域名作为数据属性挂在这里，主站 enhanceDomains/
             expandActiveDomain 直接读 dataset，不再从 href 反解。
             （注意注释必须在模板字符串外——写在反引号内会被当文本渲染上页。） */
          slot.innerHTML = rows.map((row) => `
            <a class="tk-domain" href="/?domain=${encodeURIComponent(row.name)}" data-domain="${esc(row.name)}">
              <span>${esc(row.name)}</span>
              <span class="count">${row.count}</span>
            </a>`).join("");
          /* 广播给主站：有笔记数据的页面在此之上加「点域展开主题」能力。 */
          document.dispatchEvent(new CustomEvent("tk:domains-rendered"));
          /* 【rt24】域列表是 fetch 回调里 innerHTML 的，晚于页面加载时的
             translateDOM 首跑。此处对 slot 单独重译，让域名的英文态生效
             （词条在 i18n.js rt24 块）。主站的 enhanceDomains 展开主题
             另有自己的重译。 */
          if (window.TKI18N) window.TKI18N.translateDOM(slot);
        })
        .catch(() => {
          /* 拿不到就不显示。空着好过显示一个转圈的壳。 */
        });
    }

    /* The owner-only entry.
     *
     * /api/access answers by source address, so a visitor's browser gets
     * local_client:false and the link never appears; on this machine it is
     * always there.
     *
     * This used to be a fetch whose .then() appended the link. The result was
     * a nav that rendered with four entries and then grew a fifth a frame or
     * two later — measured at 4 items by t=23ms and 5 by t=55ms, which is
     * exactly the flicker a reader notices when they click through from a page
     * that already showed five. The request is started as early as possible
     * (see the kickoff near the bottom of this file) and cached, so by the time
     * the sidebar is built the answer is normally already in hand and the nav
     * renders complete on the first paint. */
    if (accessState.known) {
      if (accessState.local) appendLocalEntries(mount, page, link);
    } else {
      accessReady.then((local) => {
        if (local) appendLocalEntries(mount, page, link);
      });
    }

    /* Pages with no top bar of their own still need a way to switch theme. */
    ensureThemeToggle();

    /* The sidebar is rebuilt on every render, so the new nodes need the
       current language applied and the switch re-wired. */
    if (window.TKI18N) {
      window.TKI18N.translateDOM(mount);
      window.TKI18N.wireLangToggles(mount);
    }

    return mount;
  };

  /* ── Feedback ─────────────────────────────────────────────────────────────
   * One panel for every page. Rendered into the document, then wired here, so
   * the markup lives in one place instead of once per page kind.
   *
   * opts:
   *   where   () => html string naming what the reader is looking at
   *   title   () => string recorded with the submission
   */
  const feedback = (opts = {}) => {
    /* The default context line is injected as HTML by the panel, so the i18n
       DOM walk never sees it — it has to go through the shared tr() above. */
    const where = opts.where || (() => tr("当前在首页，没有具体文章"));
    const title = opts.title || (() => document.title);

    const fab = document.createElement("button");
    fab.type = "button";
    fab.className = "tk-fab";
    fab.title = tr("提意见 / 报告问题");
    fab.setAttribute("aria-label", tr("提意见或报告问题"));
    fab.innerHTML = `<span aria-hidden="true">?</span><span class="tk-fab-label">${tr("提意见")}</span>`;
    document.body.appendChild(fab);

    /* 触屏端待机态：390px 实测按钮盖住 learning 的「开始」按钮和
     * projects 的首屏正文。触屏没有 hover，悬浮块静止时对首屏是持续
     * 干扰。页面未滚动时按钮降为半透明且不拦截点击（rest 态）；一旦
     * 滚动，读者进入浏览状态，按钮完全显形并可点。全站页面都可滚
     * （审计实测），不存在永远停在 rest 态的死页。 */
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
      const syncFabRest = () => fab.classList.toggle("tk-fab--rest", window.scrollY < 24);
      syncFabRest();
      window.addEventListener("scroll", syncFabRest, { passive: true });
    }

    const overlay = document.createElement("div");
    overlay.className = "tk-fb-overlay";
    overlay.id = "tk-fb-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "tk-fb-title");
    overlay.hidden = true;
    overlay.innerHTML = `
      <form class="tk-fb-panel" id="tk-fb-form">
        <h2 id="tk-fb-title">提个意见</h2>
        <p class="tk-fb-sub">这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机</p>
        <p class="tk-fb-where" id="tk-fb-where"></p>
        <div class="tk-fb-kinds" role="radiogroup" aria-label="反馈类型">
          <label><input type="radio" name="tk-kind" value="bug" checked><span>内容有错</span></label>
          <label><input type="radio" name="tk-kind" value="confusing"><span>看不懂</span></label>
          <label><input type="radio" name="tk-kind" value="suggestion"><span>想加点什么</span></label>
          <label><input type="radio" name="tk-kind" value="praise"><span>这页有用</span></label>
        </div>
        <label class="tk-fb-field"><span>具体说说</span><textarea id="tk-fb-message" maxlength="${FEEDBACK_MAX}" required placeholder="例如：这一页的链接点不开；或者：希望补一张流程图"></textarea><small id="tk-fb-count">0 / ${FEEDBACK_MAX}</small></label>
        <label class="tk-fb-field"><span>怎么称呼你（可不填）</span><input id="tk-fb-name" maxlength="60" placeholder="企微中文名或英文名" autocomplete="nickname"></label>
        <div class="tk-fb-actions">
          <button type="button" id="tk-fb-cancel">取消</button>
          <button type="submit" id="tk-fb-submit">发送</button>
        </div>
        <p class="tk-fb-note" id="tk-fb-note"></p>
      </form>`;
    document.body.appendChild(overlay);

    /* The overlay is appended after shell.js's own translateDOM(mount) call, so
       nothing had translated it: every page showed a Chinese feedback dialog
       inside an English interface. Translate it here, and again on every
       language switch, since the panel stays in the DOM for the session. */
    if (window.TKI18N) {
      window.TKI18N.translateDOM(overlay);
      document.addEventListener("tk:lang", () => window.TKI18N.translateDOM(overlay));
    }

    const $ = (id) => overlay.querySelector(id);
    const message = $("#tk-fb-message");
    const name = $("#tk-fb-name");
    const note = $("#tk-fb-note");

    try {
      const saved = localStorage.getItem(FB_NAME_KEY);
      if (saved) name.value = saved;
    } catch (err) {
      /* private mode — the name just will not persist */
    }

    const count = () => {
      $("#tk-fb-count").textContent = `${message.value.length} / ${FEEDBACK_MAX}`;
    };
    message.addEventListener("input", count);
    count();

    const show = (open) => {
      overlay.hidden = !open;
      overlay.classList.toggle("open", open);
      if (open) {
        $("#tk-fb-where").innerHTML = where();
        message.focus();
      } else if (document.activeElement && overlay.contains(document.activeElement)) {
        fab.focus();
      }
    };

    fab.onclick = () => show(true);
    $("#tk-fb-cancel").onclick = () => show(false);
    overlay.onclick = (event) => {
      if (event.target === overlay) show(false);
    };
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && overlay.classList.contains("open")) {
        show(false);
        event.preventDefault();
      }
    });

    $("#tk-fb-form").onsubmit = async (event) => {
      event.preventDefault();
      const submit = $("#tk-fb-submit");
      const text = message.value.trim();
      if (!text) {
        note.textContent = "请先写点内容。";
        note.classList.add("err");
        message.focus();
        return;
      }
      submit.disabled = true;
      note.classList.remove("err");
      note.textContent = "正在发送…";
      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            kind: (overlay.querySelector('input[name="tk-kind"]:checked') || {}).value || "other",
            message: text,
            title: title(),
            name: name.value.trim(),
            page: location.pathname + location.search,
            screen: `${screen.width}x${screen.height}`,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || tr("发送失败"));
        try {
          localStorage.setItem(FB_NAME_KEY, name.value.trim());
        } catch (err) {
          /* ignore */
        }
        message.value = "";
        count();
        note.textContent = data.message || tr("收到，谢谢反馈！");
        setTimeout(() => show(false), 900);
      } catch (error) {
        note.textContent = String(error.message || error);
        note.classList.add("err");
      } finally {
        submit.disabled = false;
      }
    };

    return { open: () => show(true), name: () => name.value.trim() };
  };

  /* Records a visit. The main site only reports actual articles, so a homepage
     refresh does not write a row; companion pages report once per load. */
  const visit = (payload) =>
    fetch("/api/visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});

  /* JS-owned labels are not text nodes in the original markup, so the i18n
     DOM walk cannot reach them. Recompute them on every language change. */
  document.addEventListener("tk:lang", () => {
    applyTheme(document.documentElement.dataset.theme || "light");
  });

  /* ── 收藏 ──────────────────────────────────────────────────────────────
   *
   * 全站共享的收藏夹：站点没有账号体系，任何访客都能收藏或取消——与反馈
   * 同一信任模型。收藏的是整条文章快照，文章滑出早报窗口后依然能完整渲染，
   * 这是"收藏的文章永久显示"的前提。
   *
   * 页面的接入方式：
   *   1. 渲染卡片时调用 register(id, item) 登记文章快照；
   *   2. 卡片里放 <button class="tk-fav-btn" data-fav-id="…">；
   *   3. 渲染完调用 bind(容器)，按钮的点击行为（含取消收藏弹窗）由这里接管；
   *   4. 收藏状态变化后这里会派发 tk:fav-changed 事件，页面据此重排。
   */
  /* tr/esc/el 走文件顶部的全站共享定义（见「全站共享小工具」）。 */
  const favMap = new Map(); // id -> { favorited_at, item }
  const favRegistry = new Map(); // id -> 页面登记的文章快照
  let favModal = null;

  /* id 必须全站统一：同一篇文章在首页早报里带 resource id、在来源页
   * 数据里没有 id——曾因此同一篇存出两条（RAW_xxx 与 u:xxx）。
   * 所以一律用 URL 哈希，djb2 只需要稳定，不追求密码学强度。 */
  const favId = (item) => "u:" + (() => {
    let h = 5381;
    const url = String(item.url || item.title || "");
    for (let i = 0; i < url.length; i++) h = ((h << 5) + h + url.charCodeAt(i)) >>> 0;
    return h.toString(16);
  })();

  async function favLoad() {
    const response = await fetch("/api/favorites", { cache: "no-store" });
    if (!response.ok) throw new Error("favorites unavailable");
    const data = await response.json();
    favMap.clear();
    (data.items || []).forEach((entry) => favMap.set(entry.id, entry));
    return data;
  }

  async function favAdd(item) {
    const id = favId(item);
    const response = await fetch("/api/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, item }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "add failed");
    favMap.set(id, { id, favorited_at: Date.now() / 1000, item });
    return id;
  }

  async function favRemove(id) {
    const response = await fetch("/api/favorites/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!response.ok) throw new Error("remove failed");
    favMap.delete(id);
  }

  /* 取消收藏确认弹窗。骨架复用反馈弹窗的 tk-fb-* 样式——同一套视觉，
     读者不用重新学习一个新弹窗长什么样。 */
  function favOpenModal(title, confirmText) {
    return new Promise((resolve) => {
      if (!favModal) {
        favModal = document.createElement("div");
        favModal.className = "tk-fb-overlay tk-fav-overlay";
        favModal.setAttribute("role", "dialog");
        favModal.setAttribute("aria-modal", "true");
        favModal.hidden = true;
        document.body.appendChild(favModal);
      }
      favModal.innerHTML = `
        <div class="tk-fb-panel tk-fav-panel" role="document">
          <h2>${confirmText || tr("取消收藏")}</h2>
          <p class="tk-fav-text">${title}</p>
          <div class="tk-fb-actions">
            <button type="button" data-act="keep">${tr("先留着")}</button>
            <button type="button" data-act="remove" class="tk-fav-confirm">${tr("确认取消")}</button>
          </div>
        </div>`;
      favModal.hidden = false;
      favModal.classList.add("open");
      const done = (answer) => {
        favModal.hidden = true;
        favModal.classList.remove("open");
        favModal.onclick = null;
        resolve(answer);
      };
      favModal.onclick = (event) => {
        const act = event.target.closest("[data-act]");
        if (act) done(act.dataset.act === "remove");
        else if (event.target === favModal) done(false);
      };
    });
  }

  /* 满员等错误也走弹窗——它已经是一个现成的"打断并告知"容器。
   * title 可选：默认"收藏夹满了"；复用到别的告知场景（如更新提示）
   * 时传入自己的标题，调用方已按语言选好文案，不走 tr。 */
  function favNotice(text, title) {
    return new Promise((resolve) => {
      if (!favModal) {
        favModal = document.createElement("div");
        favModal.className = "tk-fb-overlay tk-fav-overlay";
        favModal.setAttribute("role", "alertdialog");
        favModal.setAttribute("aria-modal", "true");
        favModal.hidden = true;
        document.body.appendChild(favModal);
      }
      favModal.innerHTML = `
        <div class="tk-fb-panel tk-fav-panel" role="document">
          <h2>${title || tr("收藏夹满了")}</h2>
          <p class="tk-fav-text">${text}</p>
          <div class="tk-fb-actions">
            <button type="button" data-act="ok">${tr("好的")}</button>
          </div>
        </div>`;
      favModal.hidden = false;
      favModal.classList.add("open");
      favModal.onclick = (event) => {
        if (event.target.closest("[data-act]") || event.target === favModal) {
          favModal.hidden = true;
          favModal.classList.remove("open");
          favModal.onclick = null;
          resolve();
        }
      };
    });
  }

  function favSyncButton(btn) {
    const id = btn.dataset.favId;
    const on = favMap.has(id);
    btn.classList.toggle("is-fav", on);
    btn.textContent = on ? "★" : "☆";
    btn.setAttribute("aria-pressed", String(on));
    btn.title = on ? tr("取消收藏") : tr("收藏");
  }

  function favBind(root) {
    root.querySelectorAll("[data-fav-id]").forEach(favSyncButton);
    /* 委托监听只挂一次：页面会反复重渲 innerHTML，但容器元素本身不变，
       不加标记的话每次渲染都会叠一层监听，点一次星触发 N 次。 */
    if (root.dataset.favBound) return;
    root.dataset.favBound = "1";
    root.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-fav-id]");
      if (!btn) return;
      /* 卡片整体是外链 <a>，点星标不能触发跳转。 */
      event.preventDefault();
      event.stopPropagation();
      const id = btn.dataset.favId;
      try {
        if (favMap.has(id)) {
          const entry = favMap.get(id);
          const title = String((entry.item || {}).title || tr("这篇文章")).replace(/</g, "&lt;");
          const ok = await favOpenModal(title, "取消收藏");
          if (!ok) return;
          await favRemove(id);
        } else {
          const item = favRegistry.get(id);
          if (!item) return;
          await favAdd(item);
        }
        favSyncButton(btn);
        document.dispatchEvent(new CustomEvent("tk:fav-changed", { detail: { id } }));
      } catch (error) {
        if (String(error.message) === "favorites_full") {
          await favNotice("收藏上限是 100 篇。它是一座精选的书架，不是仓库——先取消一些不常读的，再把它放进来");
        } else {
          await favNotice("收藏没有保存成功，请稍后再试。");
        }
      }
    });
  }

  /* 刷新早报数据后，把收藏快照对齐到最新：同 URL 的文章用新条目
   * 覆盖（评分、摘要、封面都可能变），favMap 与服务端一起更新。
   * 不匹配的收藏不动——它们可能还没重新出现在早报里，保留旧快照
   * 依然完整可读。返回更新了多少条，调用方据此提示。 */
  async function favRefreshItem(freshItems) {
    if (!Array.isArray(freshItems) || !freshItems.length) return 0;
    const byUrl = new Map();
    freshItems.forEach((it) => {
      const u = String((it || {}).url || "");
      if (u) byUrl.set(u, it);
    });
    let updated = 0;
    const idList = [...favMap.keys()];
    for (const id of idList) {
      const entry = favMap.get(id);
      const old = entry && entry.item;
      const url = String((old || {}).url || "");
      if (!url) continue;
      const fresh = byUrl.get(url);
      if (!fresh) continue;
      const merged = { ...old, ...fresh };
      favMap.set(id, { ...entry, item: merged });
      updated++;
      fetch("/api/favorites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, item: merged }),
      }).catch(() => {});
    }
    return updated;
  }

  const favorites = {
    load: favLoad,
    register(id, item) { favRegistry.set(id, item); },
    bind: favBind,
    isFav: (id) => favMap.has(id),
    get map() { return favMap; },
    notice: favNotice,
    favId,
    refreshItem: favRefreshItem,
  };

  /* ── 路径改名迁移（全站唯一真源） ────────────────────────────────────
   * vault 里的域/文章一改名，所有「按路径记账」的客户端状态都会失配。
   * 消费方：阅读标注（localStorage 里的 learned/planned 键）、知识全景的
   * 八层归层表（panorama-data.js 的 ASSIGN 键）。每次改名在这里追加一条
   * [旧前缀, 新前缀]，两处状态在读取时自动跟上，不用手动修数据。
   * 链条允许跨代：性能域改过两次名，两代旧前缀都直达终名。 */
  const PATH_MIGRATIONS = [
    ["工程知识/缺陷分析入门到精通/", "工程知识/缺陷分析：从个案到体系/"],
    ["工程知识/计算机系统与性能/", "工程知识/性能工程：从用户等待到资源瓶颈/"],
    ["工程知识/系统、性能与观测/", "工程知识/性能工程：从用户等待到资源瓶颈/"],
    ["工程知识/AI系统/", "工程知识/AI 系统工程：从模型能力到生产能力/"],
    ["工程知识/后端与分布式系统/", "工程知识/后端系统：在并发、失败与变化中维持服务/"],
    ["工程知识/软件构建与质量/", "工程知识/软件构建：让变化可以理解、验证与交付/"],
    ["工程知识/数据系统/", "工程知识/数据系统：在并发与故障中保存事实/"],
  ];
  function migratePath(path) {
    for (const [oldPrefix, newPrefix] of PATH_MIGRATIONS) {
      if (path.startsWith(oldPrefix)) return newPrefix + path.slice(oldPrefix.length);
    }
    return path;
  }

  /* ── 学习进度（全本地） ─────────────────────────────────────────────
   * 只存 localStorage，绝不上服务器——进度是个人的，站点是公开的。
   * 两个状态：learned（已学）/ planned（想学），值为标注时间戳。
   * 状态变化广播 tk:progress-changed，进度页与阅读页按钮自行同步。 */
  const progress = {
    KEY: "tk-progress-v1",
    data: null,
    load() {
      try {
        const raw = JSON.parse(localStorage.getItem(this.KEY) || "{}");
        this.data = {
          learned: raw.learned && typeof raw.learned === "object" ? raw.learned : {},
          planned: raw.planned && typeof raw.planned === "object" ? raw.planned : {},
        };
        /* 改名迁移：标注记在文章路径上，域名一改路径就失配。迁移表是全站
           唯一真源（文件顶部 PATH_MIGRATIONS），读到这里顺手迁并写回。 */
        let moved = false;
        for (const bucket of ["learned", "planned"]) {
          for (const path of Object.keys(this.data[bucket])) {
            const next = migratePath(path);
            if (next !== path) {
              this.data[bucket][next] = this.data[bucket][path];
              delete this.data[bucket][path];
              moved = true;
            }
          }
        }
        if (moved) this.save();
      } catch (err) {
        this.data = { learned: {}, planned: {} };
      }
      return this.data;
    },
    save() {
      try { localStorage.setItem(this.KEY, JSON.stringify(this.data)); }
      catch (err) { /* 存储满/隐私模式：进度丢就丢，不影响阅读 */ }
      document.dispatchEvent(new CustomEvent("tk:progress-changed"));
    },
    ensure() { return this.data || this.load(); },
    statusOf(path) {
      const d = this.ensure();
      if (d.learned[path]) return "learned";
      if (d.planned[path]) return "planned";
      return null;
    },
    at(path) {
      const d = this.ensure();
      return d.learned[path] || d.planned[path] || 0;
    },
    clearStatus(path) {
      const d = this.ensure();
      delete d.learned[path]; delete d.planned[path];
      this.save();
    },
    set(path, status) {
      const d = this.ensure();
      delete d.learned[path]; delete d.planned[path];
      if (status) d[status][path] = Date.now();
      this.save();
    },
    toggle(path, status) {
      this.set(path, this.statusOf(path) === status ? null : status);
    },
    counts() {
      const d = this.ensure();
      return { learned: Object.keys(d.learned).length, planned: Object.keys(d.planned).length };
    },
  };

  /* 字数格式化（全站单一来源）：≥1万显示 x.x万，反之人头字。
     曾经 index.html 与 matrix-view.js 各写一份，口径漂移过
     （矩阵没有空值保护），收敛到这里。定义必须在上方 TK 导出之前，
     避免 const 暂时性死区（TDZ）让整个 TK 初始化崩溃。 */
  const fmtWords = (w) => {
    if (!w && w !== 0) return "";
    const en = window.TKI18N && window.TKI18N.lang === "en";
    return w >= 10000
      ? (w / 10000).toFixed(1) + (en ? "0k words" : "万字")
      : w + (en ? " words" : " 字");
  };

  window.TKShell = {
    sidebar,
    feedback,
    migratePath,
    progress,
    favorites,
    visit,
    applyTheme,
    wireThemeToggles,
    ensureThemeToggle,
    keyForPath,
    metaFor,
    THEME_KEY,
    /* 全站共享小工具：视图文件（panorama-view / matrix-view / index 内联）
       统一从这里取，不再各写一份。 */
    tr,
    esc,
    el,
    /* 字数格式化：列表行、阅读页头部、矩阵视图共用一个口径。
       ≥1万显示 x.x万，反之人头字；中英文案由 TKI18N.lang 驱动。
       数据源是服务端 words 字段（中文逐字+英文按词），这里只做展示。 */
    fmtWords,
  };

  /* ── 全站统一空态/加载态组件 ─────────────────────────────────────────
   * 曾经各视图自己写空态：全景三处 pano-empty、目录一处 skeleton、
   * 图谱和进度什么都没有 —— 同一个"数据没到"四种长相（用户抓到的
   * "缓冲页面为啥其他页没有"）。收敛为一个帮助函数：
   *   tkEmptyState('等待笔记数据…') → <p class="view-empty">…</p>
   * 样式真源 base.css .view-empty，文案走 i18n 词典。 */
  window.tkEmptyState = function (msg) {
    const p = document.createElement("p");
    p.className = "view-empty";
    p.textContent = msg;
    return p;
  };

  /* The theme button in the main site's top bar is static markup, already in
     the document when this script runs. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => wireThemeToggles());
  } else {
    wireThemeToggles();
  }
})();
