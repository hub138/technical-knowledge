(() => {
  const script = document.currentScript;
  const page = script?.dataset.page || "workspace";
  const pages = {
    knowledge: {
      label: "知识库",
      href: "/",
      icon: "⌂",
      title: "按技术对象阅读知识",
      description: "阅读、搜索，并用图谱看知识之间的关系。",
    },
    projects: {
      label: "项目与教学",
      href: "/projects",
      icon: "▣",
      title: "进入学习与工程工具",
      description: "已经安装的工具、学习入口和源码索引。",
    },
    evaluation: {
      label: "Agent 评估",
      href: "/apps/agent-evaluation/index.html",
      icon: "◎",
      title: "把判断绑定到证据",
      description: "自研评估项目的设计与后续实现入口。",
    },
    /* Learning lives under 项目与教学 rather than in the main nav: a classroom
       is a tool you reach for, not a second way to browse knowledge. The
       sub-links keep both pages reachable once you are inside that section. */
    learning: {
      label: "学习中心",
      href: "/learn",
      icon: "▷",
      title: "把主题练成能力",
      description: "用课堂、追问、练习和迁移检验是否真的会用。",
      parent: "projects",
    },
    classrooms: {
      label: "我的课堂",
      href: "/learn/history",
      icon: "☰",
      title: "回到生成过的课堂",
      description: "列出本机生成过的互动课堂，点开即学。",
      parent: "projects",
    },
    graph: {
      label: "知识图谱",
      href: "/?view=graph",
      icon: "⌘",
      title: "看知识之间怎么连",
      description: "领域、主题与笔记之间的关联，以及知识流通路径。",
    },
  };
  const current = pages[page] || pages.knowledge;
  const nav = [pages.knowledge, pages.graph, pages.projects, pages.evaluation];
  const SUBNAV = {
    projects: [pages.learning, pages.classrooms],
  };
  // Learning tools stay under 项目与教学. 知识图谱 is a primary destination
  // because it is useful from every page, not only while browsing knowledge.
  const section = current.parent || page;
  const subNav = SUBNAV[section] || [];
  const aside = document.createElement("aside");
  aside.className = "wb-sidebar";
  aside.setAttribute("aria-label", "工作台导航");
  aside.innerHTML = `
    <a class="tk-brand" href="/" aria-label="返回工程知识库">
      <span class="tk-brand-mark" aria-hidden="true">K</span>
      <span class="tk-brand-text"><strong>工程知识库</strong><small>技术知识图谱</small></span>
    </a>
    <nav class="wb-nav">
      ${nav.map((item) => `<a href="${item.href}" ${item === current || pages[current.parent] === item ? 'aria-current="page"' : ""} title="${item.title}：${item.description}"><span class="wb-nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span></a>`).join("")}
    </nav>
    ${subNav.length ? `<nav class="wb-subnav" aria-label="学习入口">
      <p class="wb-subnav-label">学习</p>
      ${subNav.map((item) => `<a href="${item.href}" ${item === current ? 'aria-current="page"' : ""} title="${item.title}：${item.description}"><span class="wb-nav-icon wb-nav-icon--sub" aria-hidden="true">${item.icon}</span><span>${item.label}</span></a>`).join("")}
    </nav>` : ""}
    ${script?.dataset.domainTree != null ? '<nav class="wb-domains" id="domains" aria-label="知识领域"></nav>' : ""}
    <div class="wb-context">
      <p class="wb-context-label">当前位置</p>
      <h2>${current.title}</h2>
      <p>${current.description}</p>
    </div>
    <div class="wb-sidebar-footer">
      <div class="wb-sidebar-links"><a href="/auth/logout">退出</a></div>
    </div>
  `;
  document.body.classList.add("wb-host");
  document.body.insertBefore(aside, document.body.firstChild);

  /* The theme toggle is pinned to the top-right of the viewport rather than
     living in the sidebar footer, so it sits in the same place on every page
     (workspace, projects, learning) — the reader reaches for it by habit. */
  const themeToggle = document.createElement("button");
  themeToggle.type = "button";
  themeToggle.className = "wb-theme-toggle wb-theme-toggle--fixed";
  themeToggle.id = "wb-theme-toggle";
  themeToggle.setAttribute("aria-live", "polite");
  themeToggle.innerHTML =
    '<span id="wb-theme-icon" aria-hidden="true">☾</span><span id="wb-theme-label">夜晚模式</span>';
  document.body.appendChild(themeToggle);

  // Theme: an explicit choice is remembered; otherwise follow the OS and keep
  // following it until the visitor decides for themselves.
  const THEME_KEY = "tk-theme";
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const stored = () => {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  };
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark";
    document.getElementById("wb-theme-icon").textContent = dark ? "☀" : "☾";
    document.getElementById("wb-theme-label").textContent = dark ? "白天模式" : "夜晚模式";
    document.getElementById("wb-theme-toggle").setAttribute("aria-pressed", String(dark));
  };
  apply(stored() || (media.matches ? "dark" : "light"));
  media.addEventListener("change", (event) => {
    if (!stored()) apply(event.matches ? "dark" : "light");
  });
  document.getElementById("wb-theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode — the choice just will not persist */
    }
    apply(next);
  });
})();
