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
    insights: {
      label: "访问与反馈",
      href: "/insights",
      icon: "◔",
      title: "谁读过、提了什么",
      description: "本机访问记录与读者反馈，只存在本机 data/ 目录。",
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
  const nav = [
    pages.knowledge,
    pages.graph,
    pages.projects,
    pages.evaluation,
    pages.insights,
  ];
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

  /* Feedback entry, matching the knowledge workspace. Companion pages are not
     the reader, so there is no article to attach; the panel says which page
     instead. Same endpoint, so everything lands in one inbox. */
  const PAGE_LABELS = {
    projects: "项目与教学",
    learning: "学习中心",
    classrooms: "我的课堂",
    evaluation: "Agent 评估",
    insights: "访问与反馈",
  };
  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "wb-fab";
  fab.id = "wb-fab";
  fab.title = "提意见 / 报告问题";
  fab.setAttribute("aria-label", "提意见或报告问题");
  fab.innerHTML = '<span aria-hidden="true">?</span><span class="wb-fab-label">提意见</span>';
  document.body.appendChild(fab);

  const overlay = document.createElement("div");
  overlay.className = "wb-fb-overlay";
  overlay.id = "wb-fb-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "wb-fb-title");
  overlay.hidden = true;
  overlay.innerHTML = `
    <form class="wb-fb-panel" id="wb-fb-form">
      <h2 id="wb-fb-title">提个意见</h2>
      <p class="wb-fb-sub">这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机。</p>
      <p class="wb-fb-where" id="wb-fb-where"></p>
      <div class="wb-fb-kinds" role="radiogroup" aria-label="反馈类型">
        <label><input type="radio" name="wb-kind" value="bug" checked><span>内容有错</span></label>
        <label><input type="radio" name="wb-kind" value="confusing"><span>看不懂</span></label>
        <label><input type="radio" name="wb-kind" value="suggestion"><span>想加点什么</span></label>
        <label><input type="radio" name="wb-kind" value="praise"><span>这页有用</span></label>
      </div>
      <label class="wb-fb-field"><span>具体说说</span><textarea id="wb-fb-message" maxlength="4000" required placeholder="例如：这一页的链接点不开；或者：希望补一张流程图。"></textarea><small id="wb-fb-count">0 / 4000</small></label>
      <label class="wb-fb-field"><span>怎么称呼你（可不填）</span><input id="wb-fb-name" maxlength="60" placeholder="企微中文名或英文名" autocomplete="nickname"></label>
      <div class="wb-fb-actions">
        <button type="button" id="wb-fb-cancel">取消</button>
        <button type="submit" id="wb-fb-submit">发送</button>
      </div>
      <p class="wb-fb-note" id="wb-fb-note"></p>
    </form>`;
  document.body.appendChild(overlay);

  const FB_NAME_KEY = "tk-feedback-name";
  const messageBox = overlay.querySelector("#wb-fb-message");
  const nameBox = overlay.querySelector("#wb-fb-name");
  const noteBox = overlay.querySelector("#wb-fb-note");
  const show = (open) => {
    overlay.hidden = !open;
    overlay.classList.toggle("open", open);
    if (open) {
      overlay.querySelector("#wb-fb-where").innerHTML =
        `当前页面：<b>${PAGE_LABELS[page] || current.label || page}</b>`;
      messageBox.focus();
    } else if (document.activeElement && overlay.contains(document.activeElement)) {
      fab.focus();
    }
  };
  try {
    const saved = localStorage.getItem(FB_NAME_KEY);
    if (saved) nameBox.value = saved;
  } catch {
    /* private mode — the name just will not persist */
  }
  const count = () => {
    const box = overlay.querySelector("#wb-fb-count");
    box.textContent = `${messageBox.value.length} / 4000`;
  };
  messageBox.addEventListener("input", count);
  count();
  fab.onclick = () => show(true);
  overlay.querySelector("#wb-fb-cancel").onclick = () => show(false);
  overlay.onclick = (event) => {
    if (event.target === overlay) show(false);
  };
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && overlay.classList.contains("open")) {
      show(false);
      event.preventDefault();
    }
  });
  overlay.querySelector("#wb-fb-form").onsubmit = async (event) => {
    event.preventDefault();
    const submit = overlay.querySelector("#wb-fb-submit");
    const text = messageBox.value.trim();
    if (!text) {
      noteBox.textContent = "请先写点内容。";
      noteBox.classList.add("err");
      messageBox.focus();
      return;
    }
    submit.disabled = true;
    noteBox.classList.remove("err");
    noteBox.textContent = "正在发送…";
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: overlay.querySelector('input[name="wb-kind"]:checked')?.value || "other",
          message: text,
          path: "",
          title: PAGE_LABELS[page] || document.title,
          name: nameBox.value.trim(),
          contact: nameBox.value.trim(),
          page: location.pathname,
          screen: `${screen.width}x${screen.height}`,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "发送失败");
      try {
        localStorage.setItem(FB_NAME_KEY, nameBox.value.trim());
      } catch {
        /* ignore */
      }
      messageBox.value = "";
      count();
      noteBox.textContent = data.message || "收到，谢谢反馈！";
      setTimeout(() => show(false), 900);
    } catch (error) {
      noteBox.textContent = String(error.message || error);
      noteBox.classList.add("err");
    } finally {
      submit.disabled = false;
    }
  };
  /* A visit per workbench page, so /insights can show which tools get used. */
  fetch("/api/visit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path: "",
      title: PAGE_LABELS[page] || document.title,
      screen: `${screen.width}x${screen.height}`,
    }),
  }).catch(() => {});

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
