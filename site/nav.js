/* 全站导航的唯一来源。
 *
 * 之前主站（index.html 的 renderSharedNav）和工作台（workbench.js）各写了
 * 一份 items 数组，连图标都不一样，于是同一个"项目与教学"点进去导航会变样，
 * 而且主站那份压根没有"访问与反馈"这一项 —— 一下午的修改都只落在工作台那份上。
 *
 * 现在两边都通过 site/shell.js 的 TKShell.sidebar() 读这个文件。
 * 除本文件外，任何地方都不许再定义导航项。
 *
 * localOnly 的项由调用方按 /api/access 的结果决定是否渲染：中台列出访客地址和
 * 反馈内容，是运营者界面，别人的浏览器里不该出现这个入口。
 *
 * ── 图标：为什么必须是这一族 ──
 * 图标是符号字符，不是图标字体。不同符号的字形在行盒里的垂直位置并不一致：
 * 实测 ⌂ 上沿 -24、⌘ 上沿 -17、而 ▣◎◔ 族是 -19（40px 字号下），
 * 相差最多 11px —— 靠 CSS 的 align-items 调不平，因为那对齐的是盒子不是墨迹。
 * 侧边栏里五个图标就会看起来忽高忽低。
 *
 * 所以这里只用上沿一致的那一族：▣ ◎ ◔ ▷ ▤ ◉ ◧ ◨ ▥ ◫ ▦ ▧ ◘ ◙（上沿 -19、高 24）。
 * 加新项时请从这组里挑，别引入 ⌂ ⌘ ☰ ⬛ 这些 —— 它们会让整列重新错位。
 * site/base.css 的 .tk-nav-icon 负责盒子对齐，字形一致性由这里保证。
 */
window.TK_NAV = {
  items: [
    {
      key: "knowledge",
      label: "知识库",
      href: "/",
      icon: "▤",
      title: "按技术对象阅读知识",
      description: "阅读、搜索，并用图谱看知识之间的关系",
    },
    {
      key: "graph",
      label: "知识图谱",
      href: "/?view=graph",
      icon: "◉",
      group: "views",
      title: "看知识之间怎么连",
      description: "领域、主题与笔记之间的关联，以及知识流通路径",
    },
    {
      key: "panorama",
      label: "知识全景",
      pinned: true,
      href: "/?view=panorama",
      icon: "▥",
      group: "views",
      title: "两个正交维度看覆盖面",
      description: "系统层次 × 知识类型，空格子就是漏掉的方向",
    },
    {
      key: "papers",
      label: "论文追踪",
      href: "/papers",
      icon: "◫",
      title: "最新论文怎么解析、怎么进知识库",
      description: "自己追踪的新论文，逐篇结构化解析，并回流到知识库",
    },
    {
      key: "sources",
      label: "优质好文",
      href: "/sources",
      icon: "◱",
      title: "外部有哪些做得更好的站",
      description: "值得长期订阅的论文、文章与资讯源，每个都说明它补了什么",
    },
    {
      key: "projects",
      label: "项目与教学",
      href: "/projects",
      icon: "▣",
      title: "进入学习与工程工具",
      description: "已经安装的工具、学习入口和源码索引",
    },
    {
      key: "evaluation",
      label: "Agent 评估",
      href: "/apps/agent-evaluation/index.html",
      icon: "◎",
      title: "把判断绑定到证据",
      description: "用于评估 Agent 的原型：定义任务契约与证据边界，再接入执行与回归",
    },
    {
      key: "insights",
      label: "访问与反馈",
      href: "/insights",
      icon: "◔",
      title: "谁读过、提了什么",
      description: "本机访问记录与读者反馈，只在这台机器上可见",
      localOnly: true,
    },
    /* 学习入口挂在"项目与教学"下作为二级，不进主导航：课堂是随手要用的工具，
       不是浏览知识的第二条路径。主站刻意不显示这一层。 */
    {
      key: "learning",
      label: "学习中心",
      href: "/learn",
      icon: "▷",
      title: "把主题练成能力",
      description: "用课堂、追问、练习和迁移检验是否真的会用",
      parent: "projects",
    },
    {
      key: "classrooms",
      label: "我的课堂",
      href: "/learn/history",
      icon: "▦",
      title: "回到生成过的课堂",
      description: "列出本机生成过的互动课堂，点开即学",
      parent: "projects",
    },
  ],
  /* 由工作台页面渲染成二级导航，挂在"项目与教学"下。 */
  subitems: ["learning", "classrooms"],
};
