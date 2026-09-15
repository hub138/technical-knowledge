(() => {
  const script = document.currentScript;
  const page = script?.dataset.page || "workspace";
  const pages = {
    knowledge: {
      label: "知识库",
      href: "/",
      icon: "⌂",
      title: "先建立结构，再选择动作",
      description: "按技术对象阅读、搜索和连接知识。",
    },
    learning: {
      label: "学习中心",
      href: "/learn",
      icon: "▷",
      title: "把主题练成能力",
      description: "用课堂、追问、练习和迁移检验是否真的会用。",
    },
    projects: {
      label: "项目与工具",
      href: "/projects",
      icon: "▣",
      title: "选择已经安装的工具",
      description: "这里是能力入口和源码索引，不是第二套知识分类。",
    },
    evaluation: {
      label: "Agent 评估",
      href: "/apps/agent-evaluation/index.html",
      icon: "◎",
      title: "把判断绑定到证据",
      description: "自研评估项目的设计与后续实现入口。",
    },
  };
  const current = pages[page] || pages.knowledge;
  const nav = [
    pages.knowledge,
    pages.learning,
    pages.projects,
    pages.evaluation,
  ];
  const aside = document.createElement("aside");
  aside.className = "wb-sidebar";
  aside.setAttribute("aria-label", "工作台导航");
  aside.innerHTML = `
    <a class="wb-brand" href="/" aria-label="返回 technical-knowledge 知识库">
      <span class="wb-mark" aria-hidden="true">TK</span>
      <span class="wb-brand-text"><strong>technical-knowledge</strong><small>工程知识工作台</small></span>
    </a>
    <nav class="wb-nav">
      ${nav.map((item) => `<a href="${item.href}" ${item === current ? 'aria-current="page"' : ""} ${item !== current && item !== pages.knowledge ? 'target="_blank" rel="noopener noreferrer"' : ""} title="${item.title}：${item.description}"><span class="wb-nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span></a>`).join("")}
    </nav>
    <div class="wb-context">
      <p class="wb-context-label">当前位置</p>
      <h2>${current.title}</h2>
      <p>${current.description}</p>
    </div>
    <div class="wb-sidebar-footer"><a href="/?view=graph">图谱</a><a href="/auth/logout">退出</a></div>
  `;
  document.body.classList.add("wb-host");
  document.body.insertBefore(aside, document.body.firstChild);
})();
