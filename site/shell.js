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

  /* Default page metadata. A page can override any of these by passing them to
     sidebar(); the companion pages get their title/description from TK_NAV
     because those strings are already maintained there. */
  const PAGE_META = {
    knowledge: { title: "知识库", description: "阅读、搜索，并用图谱看知识之间的关系。" },
    graph: { title: "知识图谱", description: "领域、主题与笔记之间的关联，以及知识流通路径。" },
    projects: { title: "项目与教学", description: "已经安装的工具、学习入口和源码索引。" },
    evaluation: { title: "Agent 评估", description: "自研评估项目的设计与后续实现入口。" },
    insights: { title: "访问与反馈", description: "本机访问记录与读者反馈，只在这台机器上可见。" },
    learning: { title: "学习中心", description: "用课堂、追问、练习和迁移检验是否真的会用。" },
    classrooms: { title: "我的课堂", description: "列出本机生成过的互动课堂，点开即学。" },
  };

  /* Which nav entry the current URL belongs to.
   *
   * Most pages are reachable at exactly the href in nav.js. The learning pages
   * are the exception: /learn and /learn/history are the canonical links, but
   * the same pages are also served from /apps/learning/*, so both forms have to
   * map to the same key or the active entry goes unmarked.
   */
  const PATH_OWNER = [
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

  const items = () => window.TK_NAV?.items || [];

  const keyForPath = (path) =>
    PATH_OWNER.find((entry) => entry.match(path))?.key || "knowledge";

  const metaFor = (key) => {
    const item = items().find((i) => i.key === key);
    return {
      key,
      label: item?.label || PAGE_META[key]?.title || key,
      title: PAGE_META[key]?.title || item?.label || key,
      description: PAGE_META[key]?.description || "",
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

  const storedTheme = () => {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  };

  const applyTheme = (theme) => {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark";
    document.querySelectorAll("[data-tk-theme-label]").forEach((node) => {
      node.textContent = dark ? "白天模式" : "夜晚模式";
    });
    document.querySelectorAll("[data-tk-theme-icon]").forEach((node) => {
      node.textContent = dark ? "☀" : "☾";
    });
    document.querySelectorAll("[data-tk-theme-toggle]").forEach((node) => {
      node.setAttribute("aria-pressed", String(dark));
    });
  };

  applyTheme(storedTheme() || (media.matches ? "dark" : "light"));

  media.addEventListener("change", (event) => {
    if (!storedTheme()) applyTheme(event.matches ? "dark" : "light");
  });

  const toggleTheme = () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
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
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tk-theme-toggle tk-theme-toggle--fixed";
    btn.dataset.tkThemeToggle = "";
    btn.setAttribute("aria-live", "polite");
    btn.innerHTML =
      '<span data-tk-theme-icon aria-hidden="true"></span>' +
      '<span data-tk-theme-label></span>';
    document.body.appendChild(btn);
    applyTheme(document.documentElement.dataset.theme || "light");
    wireThemeToggles(document);
    return btn;
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
    const page = opts.page || keyForPath(location.pathname);
    const meta = metaFor(page);

    const brand = `
      <a class="tk-brand" href="/" aria-label="返回工程知识库">
        <span class="tk-brand-mark" aria-hidden="true">K</span>
        <span class="tk-brand-text"><strong>工程知识库</strong><small>技术知识图谱</small></span>
      </a>`;

    /* Public entries come straight from nav.js. Items with a parent belong to
       a sub-nav, not the primary list; the localOnly ones are held back here
       and appended below only once /api/access confirms this is the owner's
       machine. */
    const link = (item, current, extraClass = "") => `
      <a href="${item.href}"${item.key === current ? ' aria-current="page"' : ""}
         title="${item.title || item.label}">${
           `<span class="tk-nav-icon${extraClass}" aria-hidden="true">${item.icon}</span>`
         }<span>${item.label}</span></a>`;

    const publicItems = items().filter((i) => !i.localOnly && !i.parent);
    const subnavKeys = opts.subnav || [];

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
        ${publicItems.map((item) => link(item, page)).join("")}
      </nav>
      ${
        subnavKeys.length
          ? `<nav class="tk-subnav" aria-label="学习入口">
        <p class="tk-subnav-label">学习</p>
        ${subnavKeys
          .map((key) => {
            const item = items().find((i) => i.key === key);
            return item ? link(item, page, " tk-nav-icon--sub") : "";
          })
          .join("")}
      </nav>`
          : ""
      }
      ${
        opts.context
          ? `<div class="tk-context">
        <p class="tk-context-label">当前位置</p>
        <h2>${meta.title}</h2>
        <p>${meta.description}</p>
      </div>`
          : ""
      }
      ${
        opts.auth
          ? `<div class="tk-sidebar-footer">
        <div class="tk-sidebar-links"><a href="/auth/logout">退出</a></div>
      </div>`
          : ""
      }
    `;

    if (opts.onNavClick) {
      mount.querySelectorAll(".tk-nav a, .tk-subnav a").forEach((anchor) => {
        anchor.addEventListener("click", (event) => {
          const item = items().find((i) => i.href === anchor.getAttribute("href"));
          if (item) opts.onNavClick(event, item);
        });
      });
    }

    /* Re-assert the theme now that the nodes are in the document. See the note
       above applyTheme() earlier in this function for why the freshly inserted
       subtree needs it. */
    applyTheme(document.documentElement.dataset.theme || "light");

    /* The owner-only entry. /api/access answers by source address, so a
       visitor's browser gets local_client:false and the link never appears;
       on this machine it is always there. */
    fetch("/api/access", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : {}))
      .then((access) => {
        if (!access || !access.local_client) return;
        const nav = mount.querySelector(".tk-nav");
        if (!nav) return;
        const local = items().filter((i) => i.localOnly);
        if (!local.length) return;
        nav.insertAdjacentHTML("beforeend", local.map((item) => link(item, page)).join(""));
      })
      .catch(() => {
        /* No answer means no entry. Better to omit a link than to hand a
           visitor the operations page. */
      });

    /* Pages with no top bar of their own still need a way to switch theme. */
    ensureThemeToggle();

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
    const where = opts.where || (() => "当前在首页，没有具体文章");
    const title = opts.title || (() => document.title);

    const fab = document.createElement("button");
    fab.type = "button";
    fab.className = "tk-fab";
    fab.title = "提意见 / 报告问题";
    fab.setAttribute("aria-label", "提意见或报告问题");
    fab.innerHTML = '<span aria-hidden="true">?</span><span class="tk-fab-label">提意见</span>';
    document.body.appendChild(fab);

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
        <p class="tk-fb-sub">这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机。</p>
        <p class="tk-fb-where" id="tk-fb-where"></p>
        <div class="tk-fb-kinds" role="radiogroup" aria-label="反馈类型">
          <label><input type="radio" name="tk-kind" value="bug" checked><span>内容有错</span></label>
          <label><input type="radio" name="tk-kind" value="confusing"><span>看不懂</span></label>
          <label><input type="radio" name="tk-kind" value="suggestion"><span>想加点什么</span></label>
          <label><input type="radio" name="tk-kind" value="praise"><span>这页有用</span></label>
        </div>
        <label class="tk-fb-field"><span>具体说说</span><textarea id="tk-fb-message" maxlength="${FEEDBACK_MAX}" required placeholder="例如：这一页的链接点不开；或者：希望补一张流程图。"></textarea><small id="tk-fb-count">0 / ${FEEDBACK_MAX}</small></label>
        <label class="tk-fb-field"><span>怎么称呼你（可不填）</span><input id="tk-fb-name" maxlength="60" placeholder="企微中文名或英文名" autocomplete="nickname"></label>
        <div class="tk-fb-actions">
          <button type="button" id="tk-fb-cancel">取消</button>
          <button type="submit" id="tk-fb-submit">发送</button>
        </div>
        <p class="tk-fb-note" id="tk-fb-note"></p>
      </form>`;
    document.body.appendChild(overlay);

    const $ = (id) => overlay.querySelector(id);
    const message = $("#tk-fb-message");
    const name = $("#tk-fb-name");
    const note = $("#tk-fb-note");

    try {
      const saved = localStorage.getItem(FB_NAME_KEY);
      if (saved) name.value = saved;
    } catch {
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
            kind: overlay.querySelector('input[name="tk-kind"]:checked')?.value || "other",
            message: text,
            title: title(),
            name: name.value.trim(),
            page: location.pathname + location.search,
            screen: `${screen.width}x${screen.height}`,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "发送失败");
        try {
          localStorage.setItem(FB_NAME_KEY, name.value.trim());
        } catch {
          /* ignore */
        }
        message.value = "";
        count();
        note.textContent = data.message || "收到，谢谢反馈！";
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

  window.TKShell = {
    sidebar,
    feedback,
    visit,
    applyTheme,
    wireThemeToggles,
    ensureThemeToggle,
    keyForPath,
    metaFor,
    THEME_KEY,
  };

  /* The theme button in the main site's top bar is static markup, already in
     the document when this script runs. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => wireThemeToggles());
  } else {
    wireThemeToggles();
  }
})();
