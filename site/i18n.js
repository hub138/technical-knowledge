/* UI language, English by default.
 *
 * Scope: this translates the interface — navigation, buttons, headings, status
 * labels, form fields and the like. It does not translate the knowledge notes.
 * Those are written in Chinese on purpose; machine-translating an explanation of
 * a mechanism produces something that reads fluently and is wrong. A note
 * without an English version says so at the top and shows the Chinese text
 * rather than pretending otherwise.
 *
 * Why the dictionary is keyed by the Chinese string rather than by an id:
 * every string already exists in the markup, so keying on the source means no
 * page needs a data-i18n attribute added to each element, and a string that is
 * missing from the dictionary simply stays as written instead of rendering as
 * a key like "nav.projects". The cost is that editing Chinese copy breaks its
 * translation; scripts/i18n_audit.py reports strings present in the pages but
 * absent from the dictionary, so that cannot go unnoticed.
 *
 * Applying a translation has two paths:
 *   - static markup: translateDOM() walks text nodes and attributes
 *   - JS-rendered content: call t() explicitly, since it is built after load
 */
(() => {
  "use strict";

  const STORAGE_KEY = "tk-lang";
  /* Chinese by default. The notes are written in Chinese and the readers are
     Chinese-speaking; English is there so the interface can be shown to someone
     who does not read Chinese, not as the house language. An earlier version
     defaulted to English, which made every visit open in the wrong language. */
  const DEFAULT_LANG = "zh";
  const SUPPORTED = ["en", "zh"];

  /* ── Dictionary ───────────────────────────────────────────────────────────
   * zh is the source language: the value is what the page already says.
   * Keeping both sides in one object means a missing translation is visible
   * by inspection rather than by switching languages and hunting.
   */
  const DICT = {
    // ── Navigation ──
    "知识库": { en: "Knowledge" },

    // ── Graph controls ──
    "关系网络": { en: "Relations" },
    "领域、主题与笔记之间的关联": { en: "How domains, topics and notes connect" },
    "从问题到证据、行动与反馈的路径": {
      en: "The path from a question to evidence, action and feedback",
    },
    "从目标、理解到练习、反馈与迁移": {
      en: "From goal and understanding to practice, feedback and transfer",
    },
    "能力、知识、编排、工具、运行与治理的分层": {
      en: "Layers: capability, knowledge, orchestration, tools, runtime, governance",
    },
    "技术选型象限": { en: "Technology quadrants" },
    "用控制方式与协作范围理解组件位置": {
      en: "Where a component sits, by control style and collaboration scope",
    },
    "工作流": { en: "Workflow" },
    "协议": { en: "Protocol" },
    "跨系统协作": { en: "Cross-system" },
    "知识流通": { en: "Knowledge flow" },
    "学习循环": { en: "Learning loop" },
    "AI 系统架构": { en: "AI system layers" },
    "选型象限": { en: "Selection quadrants" },
    "文章知识图谱": { en: "Article knowledge graph" },
    "放大": { en: "Zoom in" },
    "缩小": { en: "Zoom out" },
    "重置": { en: "Reset" },
    "放大图谱": { en: "Zoom in on the graph" },
    "缩小图谱": { en: "Zoom out of the graph" },
    "重置视图": { en: "Reset the view" },
    "重置缩放与平移": { en: "Reset zoom and pan" },
    "滚轮缩放 · 拖拽平移 · 点节点打开": {
      en: "Scroll to zoom · drag to pan · click a node to open",
    },

    // ── Article rail ──
    "本文目录": { en: "On this page" },
    "同模块其他文章": { en: "More in this module" },

    // ── Insights page ──
    "访问与反馈 · 工程知识库": { en: "Visits and feedback · engineering knowledge" },
    "概览": { en: "Summary" },
    "访客": { en: "Visitors" },
    "读得最多的文章": { en: "Most-read notes" },
    "只统计能对应到具体文章的访问。": {
      en: "Only visits that resolve to a specific note are counted.",
    },
    "这些数字能说明什么。": { en: "What these numbers do and do not show." },
    "知识图谱": { en: "Graph" },
    "项目与教学": { en: "Projects & Learning" },
    "Agent 评估": { en: "Agent Evaluation" },
    "学习中心": { en: "Learning" },

    // ── Learning centre ──
    "从知识点走到真正会用": { en: "From knowing a topic to actually using it" },
    "学习工具": { en: "Learning tools" },
    "每一步都有明确产出，不以“看完”为完成。": {
      en: "Every step produces something. Reading to the end does not count as done.",
    },
    "1. 选主题": { en: "1. Pick a topic" },
    "2. 选择学习动作": { en: "2. Choose what to do" },
    "3. 确认后生成": { en: "3. Confirm, then generate" },
    "我现在想学": { en: "I want to study" },
    "开始": { en: "Start" },
    "导师": { en: "Tutor" },
    "审查方案": { en: "Review a design" },
    "故障演练": { en: "Failure drill" },
    "案例推演": { en: "Case walkthrough" },
    "理解本质": { en: "Understand the mechanism" },
    "瓶颈模型": { en: "Bottleneck model" },
    "划清职责": { en: "Draw the boundaries" },
    "开始故障推演": { en: "Start the drill" },
    "开始架构审查": { en: "Start the review" },
    "当前边界": { en: "Current scope" },
    "查看能力与边界": { en: "Capability and scope" },
    "会消耗": { en: "Uses quota" },
    "检查中": { en: "Checking" },
    "已完成": { en: "Complete" },
    "检查知识库检索配置中": { en: "Checking the retrieval configuration" },
    "无需再找安装命令或猜页面入口。": {
      en: "No install commands to find, no entry points to guess.",
    },
    "用于形成直觉和互动练习；": { en: "For intuition and interactive practice; " },
    "用于追问、研究和复习。两者不是重复功能。": {
      en: "for questioning, research and review. They are not the same feature twice.",
    },
    /* 中文用全角问号自带右侧空隙，英文问号没有，所以要显式补一个空格，
       否则会渲染成 "Already generated a classroom?Open my classrooms"。
       同理适用于所有以标点结尾、后面紧跟行内链接的短句。 */
    "已经生成过课堂？": { en: "Already generated a classroom? " },
    "打开我的课堂 →": { en: "Open my classrooms →" },
    "打开互动课堂": { en: "Open the classroom" },
    "打开已生成示例": { en: "Open a generated example" },
    "打开案例课堂": { en: "Open the case classroom" },
    "打开诊断课堂": { en: "Open the diagnosis classroom" },
    "DeepTutor 学习导师": { en: "DeepTutor tutor" },
    "OpenMAIC 互动课堂": { en: "OpenMAIC classroom" },
    "描述你的问题，它会带出处回答": {
      en: "Describe the problem; the answer comes with sources",
    },

    // ── Classroom history ──
    "课堂历史：": { en: "Classroom history:" },
    "生成过的课堂": { en: "Generated classrooms" },
    "回到学习中心": { en: "Back to Learning" },
    "新建课堂 ↗": { en: "New classroom ↗" },
    "正在读取本地生成记录…": { en: "Reading the local generation log…" },
    "一次学习的去向": { en: "Where a session goes" },
    "为什么不自动同步": { en: "Why it does not sync automatically" },
    "为什么这里能看到": { en: "Why this list exists" },
    "关于失败任务": { en: "About failed runs" },
    "回看": { en: "Review" },
    "复核": { en: "Check" },
    "收录": { en: "File it" },
    "生成": { en: "Generate" },
    "尚未收录：": { en: "Not yet filed:" },
    "推荐收录：": { en: "Suggested:" },
    "正式知识：": { en: "In the knowledge base:" },
    "我的课堂": { en: "Classrooms" },
    "学习": { en: "Learn" },
    "当前位置": { en: "Current page" },
    "退出": { en: "Sign out" },

    // ── Brand ──
    "工程知识库": { en: "Engineering Knowledge" },
    "技术知识图谱": { en: "Technical knowledge graph" },

    // ── Theme + feedback controls ──
    "夜晚模式": { en: "Dark mode" },
    "白天模式": { en: "Light mode" },
    "正在发送…": { en: "Sending, please wait…" },
    "当前在首页，没有具体文章": { en: "On the home page — no specific article" },
    "正在读：": { en: "Reading: " },
    "例如：这一页的链接点不开；或者：希望补一张流程图。": {
      en: "For example: a link here is broken; or: a diagram would help.",
    },

    // ── Search + shortcuts ──
    "搜索知识、机制、项目或来源": { en: "Search knowledge, mechanisms, projects, sources" },
    "快捷键": { en: "Shortcuts" },
    "键盘快捷键": { en: "Keyboard shortcuts" },
    "阅读时不必离开键盘。Esc 随时关闭本面板。": {
      en: "Read without leaving the keyboard. Esc closes this panel at any time.",
    },
    "关闭": { en: "Close" },
    "然后": { en: "then" },
    "归档": { en: "Archive" },
    "查看键盘快捷键": { en: "See keyboard shortcuts" },
    "聚焦搜索框": { en: "Focus the search box" },
    "清空搜索，或从文章返回目录": { en: "Clear the search, or leave an article" },
    "在目录里上下移动选中条目": { en: "Move through the list" },
    "打开选中的条目": { en: "Open the selected entry" },
    "回到首页": { en: "Go home" },
    "打开知识图谱": { en: "Open the graph" },
    "打开项目与教学": { en: "Open projects and learning" },
    "切换白天 / 夜晚模式": { en: "Toggle light / dark" },
    "显示或关闭本面板": { en: "Show or hide this panel" },

    // ── Reader toolbar ──
    "← 返回目录": { en: "← Back to index" },
    "返回目录": { en: "Back to index" },
    "返回当前领域或搜索结果": { en: "Return to the current domain or search results" },
    "下载 .md": { en: "Download .md" },
    "下载这篇的 Markdown 原文": { en: "Download this note as Markdown" },
    "复制链接": { en: "Copy link" },
    "复制这篇的链接": { en: "Copy a link to this note" },
    "打印": { en: "Print" },
    "打印或另存为 PDF": { en: "Print or save as PDF" },
    "用这个主题学习": { en: "Study this topic" },

    // ── Home ──
    "把技术原理读到能上手用": { en: "Read the mechanism, then use it" },
    "知识领域": { en: "Domains" },
    "学习与实践": { en: "Learning and practice" },
    "评估与工程": { en: "Evaluation and engineering" },
    "辅助理解": { en: "Optional aids" },
    "保留资料": { en: "Retained material" },

    // ── Domain descriptions ──
    "AI系统": { en: "AI systems" },
    "后端与分布式系统": { en: "Backend and distributed systems" },
    "数据系统": { en: "Data systems" },
    "计算机系统与性能": { en: "Computer systems and performance" },
    "软件构建与质量": { en: "Software construction and quality" },
    "知识库管理": { en: "Knowledge base upkeep" },
    "总览": { en: "Overview" },
    "条来源": { en: "sources" },

    // ── Cards and status ──
    "已安装": { en: "Installed" },
    "已部署": { en: "Running" },
    "开源": { en: "Open source" },
    "无需 API Key": { en: "No API key" },
    "需访问码": { en: "Needs access code" },
    "需登录本机账号": { en: "Needs local sign-in" },
    "核验": { en: "verified" },
    "输入": { en: "Input" },
    "处理": { en: "Processing" },
    "产出": { en: "Output" },
    "状态未知": { en: "Status unknown" },
    "需要登录": { en: "Sign-in required" },
    "需要登录本机账号": { en: "Requires a local account" },
    "学习导师可用": { en: "Tutor ready" },
    "服务运行中": { en: "Service up" },
    "未启动": { en: "Not running" },
    "配置不完整": { en: "Incomplete setup" },
    "查看": { en: "View" },
    "打开": { en: "Open" },
    "完整使用指南": { en: "Full guide" },
    "实现与边界": { en: "How it works, and its limits" },
    "中文说明": { en: "Chinese README" },
    "查看写作契约": { en: "Writing contract" },
    "查看自研项目": { en: "Open the project" },
    "创建课堂": { en: "Create a classroom" },
    "进入学习导师": { en: "Open the tutor" },
    "打开学习中心": { en: "Open Learning" },
    "查看项目与教学": { en: "See projects and learning" },
    "查看知识图谱": { en: "See the knowledge graph" },
    "打开课堂历史": { en: "Classroom history" },
    "打开项目入口": { en: "Projects" },
    "查看收录方式": { en: "How notes get filed" },
    "先看使用说明": { en: "Read the guide first" },
    "为什么不能只信 Agent 的总结": { en: "Why an agent's summary is not evidence" },
    "为什么不能只信Agent的总结": { en: "Why an agent's summary is not proof" },

    // ── Projects page ──
    "项目与教学入口": { en: "Projects and learning" },
    "这里解决什么问题": { en: "What this page is for" },
    "访问方式": { en: "How to get in" },
    "怎么用": { en: "How to use it" },
    "学习产品": { en: "Learning products" },
    "工程方法与辅助可视化": { en: "Engineering methods and visualisation" },
    "已经融合到知识库": { en: "Already folded into the knowledge base" },
    "从主题到能力": { en: "From topic to capability" },
    "自研 Agent 评估": { en: "Agent evaluation (in-house)" },
    "自研 Agent 评估独立维护": { en: "Agent evaluation is maintained separately" },
    "方法如何反哺": { en: "How the methods feed back" },
    "知识点的教学输出": { en: "Teaching output per note" },
    "任务与项目理解": { en: "Task and project understanding" },
    "轨迹与事实证据": { en: "Trace and evidence" },
    "待开发：改进与回归": { en: "Not built yet: improvement and regression" },
    "互动课堂": { en: "Interactive classroom" },
    "学习导师": { en: "Study tutor" },
    "什么会花掉额度": { en: "What costs model quota" },
    "在别的设备上打开": { en: "Opening it on another device" },
    "从本页点「进入学习导师」，会直接进对话界面。": {
      en: "Use “Open the tutor” above; it goes straight to the chat.",
    },
    "点生成之前，先看一眼主题和材料范围。": { en: "Check the topic and materials before you generate." },
    "读知识不需要密码，用工具才需要。": { en: "Reading needs no password; tools do." },
    "学习产品优先，工程方法其次，可视化是辅助。跨项目仍成立的方法会进入对应知识主题；自研 Agent 评估独立维护。": {
      en: "Learning tools first, engineering methods second, visualisation as an aid. Methods that hold across projects go into the knowledge base; the in-house evaluation stays separate.",
    },
    "当前是本机访问：知识库公开可读，启动教学工具自动使用已配置凭据。": {
      en: "You are on this machine: the knowledge base is open, and starting a tool uses the configured credentials.",
    },
    "这里放我已经装好的学习工具，以及它们的源码和说明。想看哪个点哪个，不用记端口和路径。": {
      en: "The learning tools installed here, with their source and docs. Click through instead of remembering ports.",
    },

    // ── Learning ──
    "先给模型": { en: "Model first" },
    "再改条件": { en: "Change a condition" },
    "即时反馈": { en: "Immediate feedback" },
    "预测": { en: "Predict" },
    "对比": { en: "Compare" },
    "形成直觉": { en: "Build intuition" },
    "迁移验证": { en: "Transfer validation" },
    "选择主题": { en: "Pick a topic" },
    "检索与复习": { en: "Retrieve and review" },
    "用课堂、追问、练习和迁移检验是否真的会用。": {
      en: "Classrooms, questioning, practice and transfer, to check you can actually use it.",
    },

    // ── Insights ──
    "访问与反馈": { en: "Visits and feedback" },
    "仅本机可见": { en: "This machine only" },
    "总访问次数": { en: "Total visits" },
    "独立访客（按 IP）": { en: "Unique visitors (by IP)" },
    "今日访问": { en: "Today" },
    "待处理反馈": { en: "Open feedback" },
    "反馈总数": { en: "Feedback total" },
    "反馈收件箱": { en: "Feedback inbox" },
    "按时间倒序。标记会立刻写回本机日志，刷新后保留。": {
      en: "Newest first. Marking a row writes straight back to the local log.",
    },
    "共": { en: "" },
    "条 · 待处理": { en: " items · open " },
    "待处理": { en: "Unresolved" },
    "已读": { en: "Read" },
    "已处理": { en: "Done" },
    "本机": { en: "local" },
    "刷新": { en: "Refresh" },
    "切换日夜模式": { en: "Toggle light or dark mode" },
    "回到知识库": { en: "Back to Knowledge" },
    "其他": { en: "Other" },
    "（未指定文章）": { en: "(no article)" },
    "谁读过、提了什么": { en: "Who read what, and what they said" },
    "本机访问记录与读者反馈，只在这台机器上可见。": {
      en: "Local visit log and reader feedback — visible on this machine only.",
    },

    // ── Feedback dialog (rendered by shell.js) ──
    "发送失败": { en: "Could not send" },
    "提意见 / 报告问题": { en: "Feedback and problems" },
    "提个意见": { en: "Send feedback" },
    "提意见": { en: "Feedback" },
    "这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机。": {
      en: "Say what is wrong, unclear or missing on this page. Feedback stays on this machine.",
    },
    "反馈类型": { en: "Feedback type" },
    "内容有错": { en: "Something is wrong" },
    "看不懂": { en: "Hard to follow" },
    "想加点什么": { en: "Something is missing" },
    "这页有用": { en: "This page helped" },
    "具体说说": { en: "Tell me more" },
    "怎么称呼你（可不填）": { en: "Your name (optional)" },
    "企微中文名或英文名": { en: "Your WeCom name, Chinese or English" },
    "取消": { en: "Cancel" },
    "发送": { en: "Send" },
    "提意见或报告问题": { en: "Send feedback or report a problem" },
    "返回工程知识库": { en: "Back to the knowledge base" },
    "站点导航": { en: "Site navigation" },
    "打开目录": { en: "Open the contents" },
    "学习入口": { en: "Learning entries" },
    "目录": { en: "Contents" },
    "导师可用": { en: "Tutor available" },
    "互动课堂可用": { en: "Classroom available" },
    "把主题练成能力": { en: "Turn a topic into a skill" },
    "收到，谢谢反馈！": { en: "Got it, thanks." },
    "请先写点内容。": { en: "Write something first." },

    // ── Papers page ──
    "时间线": { en: "Timeline" },
    "正在读取…": { en: "Loading…" },
    "优质好文": { en: "Good reads" },
    // 首页那两栏的标题。词典按整串匹配，新短语要各自列一条，
    // 否则英文界面下会原样显示中文。
    "看完能判断：这东西适不适合你": { en: "See whether it fits what you're building" },
    "不用读完论文，也知道它值不值得读": { en: "Whether a paper is worth reading, without the read" },
    "每篇讲清三件事：": { en: "Three things, on every one:" },
    // 首页那块横滑区的标题。词典是整串匹配的，所以要单独列一条 ——
    // 只写「优质好文」的话，「每日优质好文」整串查不到，英文界面下会
    // 原样显示中文。
    "近三天优质好文": { en: "Good reads, last three days" },
    "BestBlogs 早报，滚动三天": { en: "BestBlogs' brief, rolling three days" },
    "配好 BestBlogs 的 API Key 后，这里会列出它最近三天的早报": {
      en: "Once BestBlogs' API key is configured, its briefs for the last three days appear here.",
    },
    "资源目录": { en: "Source index" },
    "追踪新论文": { en: "Tracking new papers" },
    "追踪新论文和解析": { en: "New papers, with write-ups" },
    "按时间倒序。每篇给出它解决的问题、做法，以及论文自己报出的数字——摘要里没写的就留空。2024 年前的收在「历史奠基」里。": {
      en: "Newest first. Each entry gives the problem, the approach, and the numbers the paper itself reports — anything the abstract leaves out stays blank. Papers before 2024 sit under Foundations.",
    },
    "论文追踪": { en: "Paper Tracking" },
    "追踪新论文，逐篇给出结构化解析；知识库的结论从这里取材。": { en: "New papers are tracked and analysed here, one by one. The knowledge base draws its evidence from them." },
    "最新论文怎么解析、怎么进知识库": { en: "How new papers are read and fed into the knowledge base" },
    "自己追踪的新论文，逐篇结构化解析，并回流到知识库。": { en: "New papers tracked here, analysed one by one, and folded back into the knowledge base." },
    "2023 及更早 · 历史奠基": { en: "2023 and earlier · Foundations" },
    "搜「标题 / 作者 / arXiv 编号」都没命中。试试论文标题里的一个词，或者 4 位年份。": { en: "No match on title, author or arXiv id. Try one distinctive word from the title, or a 4-digit year." },
    "这些论文是怎么挑出来、怎么解析的": { en: "How these papers are found and analysed" },
    "追踪管道、四道验证防线、L1/L2 分级解析的标准写在方法页里 —— 这个页面上每一条规则都能在那里找到出处。": { en: "The tracking pipeline, the four verification gates and the L1/L2 analysis standard are written up in the method page — every rule on this page traces back to it." },
    "看方法": { en: "Read the method" },
    "解决的问题": { en: "Problem" },
    "做法": { en: "Approach" },
    "关键结果": { en: "Key result" },
    "支撑": { en: "Supports" },
    "篇知识": { en: "knowledge notes" },
    "调研引用": { en: "Surveyed" },
    "已深度解析": { en: "Has deep read" },
    "解析": { en: "Analysis" },
    "全部": { en: "All" },
    "篇有摘要里的量化结果": { en: "with a measured result in the abstract" },
    "返回论文追踪": { en: "Back to paper tracking" },
    "arXiv 原文": { en: "arXiv" },
    "摘要要点": { en: "Abstract points" },
    "深度解读": { en: "Deep read" },
    "看原文摘要（上面每个字段的出处）": { en: "Read the abstract these fields come from" },
    "元数据与摘要来自 arXiv API": { en: "Metadata and abstract from the arXiv API" },
    "一句话概括": { en: "In one line" },
    "知识库中依赖它的结论": { en: "In the knowledge base, resting on it" },
    "这篇还没有深度解读": { en: "No deep read yet" },
    "上面是 L1，来自论文自己的摘要。深度解读（L2）要把全文读完才能写：摘要里没有消融实验、超参设置、失败案例和复现步骤，靠摘要拼出来的解读每一句都可能是错的。": { en: "The fields above are L1, taken from the paper's own abstract. A deep read (L2) needs the full paper: an abstract does not contain ablations, hyperparameters, failure cases or reproduction steps, so a deep read assembled from it would be wrong in ways a reader cannot detect." },
    "按追踪方法论的 L2 规范，需要补这八个模块：": { en: "The L2 standard requires these eight modules:" },
    "背景与问题": { en: "Background and problem" },
    "核心方法": { en: "Method" },
    "技术细节": { en: "Technical detail" },
    "实验与结果": { en: "Experiments and results" },
    "亮点与洞察": { en: "Strengths and insights" },
    "局限性": { en: "Limitations" },
    "复现指南": { en: "Reproduction guide" },
    "相关工作与启发": { en: "Related work and what it suggests" },
    "写好之后放进": { en: "Write it into" },
    "，页面会自动显示。": { en: " and this page picks it up automatically." },
    "缺少论文编号。": { en: "No paper id given." },
    "找不到这篇论文。": { en: "Paper not found." },
    "论据": { en: "Evidence" },
    "看这些论文还支撑了什么": { en: "See what else these papers support" },
    "PAPERS · 知识库的论据": { en: "PAPERS · the library's evidence" },
    "搜标题、作者、arXiv 编号": { en: "Search title, author, or arXiv id" },
    "这些论文撑起了这个知识库": { en: "The papers this library is built on" },
    "等": { en: "et al." },
    "篇知识以此为依据": { en: "notes rest on this" },
    "仅出现在调研清单里": { en: "listed as reading only" },
    "它支撑的结论": { en: "Conclusions that rest on it" },
    "展开摘要": { en: "Show abstract" },
    "收起摘要": { en: "Hide abstract" },
    "另被调研记录引用": { en: "Also cited by" },
    "处（无结论依赖它）": { en: "research record(s), with no conclusion depending on it" },
    "没有匹配的论文。": { en: "No paper matches." },
    "读不到论文注册表。运行 python3 scripts/fetch-papers.py 生成后再刷新。": { en: "Cannot read the paper registry. Run python3 scripts/fetch-papers.py, then reload." },
    "篇": { en: "papers" },
    "条结论有论文支撑": { en: "conclusions backed by a paper" },

    // ── Sources page ──
    // 卡片本身的 name/kind/gain/tags 不走词典 —— 它们来自 site/sources.js，
    // 按当前语言直接取（那一份数据里自带 en 字段）。这里只放页面骨架上的文案。
    "外部资源": { en: "Sources" },
    "外部有哪些做得更好的站": { en: "Sites that do this better" },
    "文章": { en: "Writing" },
    "成篇的文章，适合慢慢读。": { en: "Finished pieces, for slow reading." },
    "论文": { en: "Papers" },
    "一手研究。比二手解读可信，也更需要筛选。": {
      en: "Primary research. More trustworthy than a second-hand read, and in more need of filtering.",
    },
    "资讯": { en: "News" },
    "知道发生了什么。用来看动向，不当知识读。": {
      en: "Knowing what happened. For tracking the field, not as knowledge.",
    },
    "资源清单读不到": { en: "Cannot read the source list" },
    "检查 site/sources.js 是否加载成功，然后刷新。": {
      en: "Check that site/sources.js loaded, then reload.",
    },
    // 卡片里带回来的外部内容（标题、摘要）**不进词典** —— 那些是内容不是界面文案，
    // 英文站的内容在中文界面里显示英文是正常的。这里只放窗口自己的界面字。
    "最新几条": { en: "Latest" },
    "这一站暂时读不到，入口仍然可用。": {
      en: "This source is not reachable right now. The link above still works.",
    },
    "暂时没有新内容。": { en: "Nothing new right now." },
    "更新于": { en: "Updated" },
    "刚刚更新": { en: "Updated just now" },
    // 资源页的分类目录。「全部」已在词典里（图谱页用过），不重复定义。
    "资源分类": { en: "Source categories" },
    // 论文页的外部收录
    "外部收录": { en: "External index" },
    "已精读": { en: "Read closely" },
    "论文来源": { en: "Paper source" },
    "分类": { en: "Category" },
    "子领域": { en: "Subfield" },
    "会议": { en: "Venue" },
    "显示更多": { en: "Show more" },
    "筛出": { en: "Filtered" },
    "总计": { en: "total" },
    "两万三千篇顶会论文解读，来自": { en: "23,000 conference paper write-ups, from" },
    "，按论文自己的分类组织。点标题回原站看完整解读。": {
      en: ", organised the way the source files them. Open a title to read the full write-up there.",
    },
    "搜标题或方向": { en: "Search title or topic" },
    "读不到论文摘要索引。运行 python3 scripts/fetch-papernotes.py 生成后再刷新。": {
      en: "Cannot read the paper index. Run python3 scripts/fetch-papernotes.py, then reload.",
    },
    // 「正在读取…」和「刷新」已在词典里（前面几段），不在这里重复定义 ——
    // 同一个 key 定义两次时 JS 保留最后一个，前面那个变成死代码，
    // i18n_dict_audit 会把这种情况判为失败。

    // ── Home page: what every note answers ──
    "篇工程笔记，覆盖 AI 系统、后端、数据、系统性能与软件构建。写的都是能落到手上的东西：一个机制怎么运作、代价在哪、结论有没有实测支撑。": {
      en: "engineering notes on AI systems, backend, data, systems performance and software construction. Everything here is meant to be used: how a mechanism works, what it costs, and whether the conclusion was measured.",
    },
    "每一篇都回答这四个问题": { en: "Every note answers four questions" },
    "它为什么出现": { en: "Why it exists" },
    "之前卡在哪，没它的时候怎么办": { en: "what was stuck before it, and what people did instead" },
    "它怎么运作": { en: "How it works" },
    "机制是什么，关键那一步发生了什么": { en: "the mechanism, and what actually happens at the decisive step" },
    "它到底改变了什么": { en: "What it changes" },
    "哪个数字动了，在什么条件下测的": { en: "which number moved, measured under what conditions" },
    "什么时候不该用它": { en: "When not to use it" },
    "代价是什么，边界在哪": { en: "what it costs, and where the boundary is" },

    /* ── Page chrome, added 2026-09-18 ──────────────────────────────────────
     * scripts/i18n_audit.py reported 241 interface strings across six pages with
     * no translation, which showed up as Chinese sitting inside an English
     * interface. These are labels, buttons, status badges, field names and
     * short headings — the parts a reader navigates by, which the dictionary is
     * supposed to cover. Grouped by page in the same order the audit reports.
     */

    // ── projects/index.html ──
    "3100 运行中": { en: "3100 running" },
    "3782 运行中": { en: "3782 running" },
    "上游源码：": { en: "Upstream source:" },
    "互动课堂、测验、模拟、项目任务与反馈": { en: "Classroom, quizzes, simulation, project work and feedback" },
    "从本页点「打开课堂」，主题会带过去。": { en: "Use “Open classroom” above; the topic carries over." },
    "从这一页点进去，登录和主题都会自动带上。": { en: "Everything here carries the sign-in and the topic with it." },
    "先看使用说明 ↓": { en: "Read the usage notes ↓" },
    "在 GitHub 打开原始仓库，查看源码、Issue 与最新版本": {
      en: "Open the upstream repository on GitHub: source, issues and latest release",
    },
    "实验 / 待开发评估": { en: "Prototype · planned evaluation" },
    "对齐、设计、实现、TDD、审查与架构演进": {
      en: "Alignment, design, implementation, TDD, review and architectural change",
    },
    "工作区 / 引用": { en: "Workspace · citations" },
    "已同步技能": { en: "Skills synced" },
    "已安装 · 本机 CLI": { en: "Installed · local CLI" },
    "已安装 · 本机 Skills": { en: "Installed · local skills" },
    "已部署 · 3100": { en: "Deployed · 3100" },
    "已部署 · 3782": { en: "Deployed · 3782" },
    "开源 · Apache-2.0": { en: "Open source · Apache-2.0" },
    "开源 · MIT": { en: "Open source · MIT" },
    "形成理解": { en: "Build understanding" },
    "打开 DeepTutor：自动建立本机会话后进入 Chat，可直接提问": {
      en: "Open DeepTutor: starts a local session and goes straight to the chat",
    },
    "打开 OpenMAIC 互动课堂：会自动完成授权并带上主题，直接进入生成页": {
      en: "Open the OpenMAIC classroom: authorises and carries the topic to the generator",
    },
    "打开学习工作区": { en: "Open the workspace" },
    "打开课堂": { en: "Open classroom" },
    "操作": { en: "Action" },
    "改变数据、权限、负载或故障条件的项目任务": {
      en: "Project tasks that change data, permissions, load or failure conditions",
    },
    "星数与许可核验于 2026-09-17": { en: "Stars and licence verified 2026-09-17" },
    "最小实验、代码任务、配置练习和结果检查": {
      en: "Small experiments, coding tasks, configuration exercises and result checks",
    },
    "机制解释、对比表、架构图和数据流": {
      en: "Mechanism explanations, comparison tables, architecture diagrams and data flow",
    },
    "架构、工作流、序列、数据流与生命周期图": {
      en: "Architecture, workflow, sequence, data flow and lifecycle diagrams",
    },
    "查看 Matt Skills 各技能的作用与调用方式": { en: "See what each Matt skill does and how to call it" },
    "查看反哺机制": { en: "See how it feeds back" },
    "查看实现路线": { en: "See the implementation plan" },
    "查看技能说明": { en: "See the skills" },
    "查看自研 Agent 评估": { en: "See the in-house evaluation" },
    "查看自研 Agent 评估的实现路线与待开发项": { en: "See the in-house evaluation plan and what is still unbuilt" },
    "查看自研项目 →": { en: "See the in-house project →" },
    "查看融合记录": { en: "See the integration notes" },
    "查看评估契约": { en: "See the evaluation contract" },
    "检索、研究、记忆、笔记与复习工作区": {
      en: "Retrieval, research, memory, notes and revision in one workspace",
    },
    "理解": { en: "Understand" },
    "直接面向主题学习、资料研究、练习和复习。": { en: "For topic study, source research, practice and revision." },
    "知识库 / 图谱": { en: "Knowledge base · graph" },
    "评估": { en: "Evaluate" },
    "课堂 / 反馈": { en: "Classroom · feedback" },
    "轨迹回放、证据审查、故障注入和回归样本": {
      en: "Trace replay, evidence review, fault injection and regression samples",
    },
    "辅助 CLI": { en: "Helper CLI" },
    "阅读 Archify 中文说明：图类型、校验流程与 CLI 用法": {
      en: "Read the Archify notes: diagram types, validation flow and CLI usage",
    },
    "阅读 Archify 英文 README（README_EN.md）": { en: "Read the Archify English README (README_EN.md)" },
    "阅读 DeepTutor 中文说明：安装、模型配置与知识库用法": {
      en: "Read the DeepTutor notes: install, model configuration and knowledge base usage",
    },
    "阅读 DeepTutor 英文 README": { en: "Read the DeepTutor English README" },
    "阅读 OpenMAIC 中文说明：安装、模型配置与页面结构": {
      en: "Read the OpenMAIC notes: install, model configuration and page structure",
    },
    "验证与迁移": { en: "Validate and transfer" },
    "，比记 IP 稳。": { en: ", which survives an IP change." },

    // ── apps/learning/index.html ──
    "AI 应用工程": { en: "AI application engineering" },
    "AI 知识系统": { en: "AI knowledge systems" },
    "RAG：从一次检索到有状态证据系统": { en: "RAG: from a single retrieval to a stateful evidence system" },
    "可靠 Agent：决策、执行与事实边界": { en: "Reliable agents: decisions, execution and the boundary of fact" },
    "后端与性能：从请求路径到瓶颈证据": {
      en: "Backend and performance: from request path to bottleneck evidence",
    },
    "用当前主题创建课堂": { en: "Create a classroom on this topic" },
    "用当前主题开始追问": { en: "Start questioning this topic" },
    "知识库和这里的区别": { en: "How this differs from the knowledge base" },
    "第一次使用": { en: "First time here" },
    "系统工程": { en: "Systems engineering" },
    "组织系统": { en: "Structuring a system" },
    "装好就能用，不用再配环境": { en: "Ready to use; nothing to configure" },
    "装好就能用，已连上这个知识库": { en: "Ready to use; already connected to this knowledge base" },
    "解释演进": { en: "Explain how it evolved" },
    "让导师考我": { en: "Have the tutor test me" },
    "证据答辩": { en: "Defend with evidence" },
    "请求路径": { en: "Request path" },
    "读性能模型": { en: "Read the performance model" },
    "读核心机制": { en: "Read the core mechanism" },
    "读演进关系": { en: "Read how it evolved" },
    "读系统设计": { en: "Read the system design" },
    "读请求边界": { en: "Read the request boundary" },
    "读责任边界": { en: "Read where responsibility ends" },
    "课堂": { en: "Classroom" },
    "输入一个主题，检查预填内容后点生成": { en: "Enter a topic, check the prefill, then generate" },
    "适合追问、研究、笔记、掌握路径和长期记忆": {
      en: "For questioning, research, notes, mastery paths and long-term memory",
    },
    "预置学习路径": { en: "Ready-made learning paths" },

    // ── apps/learning/openmaic.html ──
    "/ OpenMAIC 互动课堂": { en: "/ OpenMAIC classroom" },
    "OpenMAIC 融合记录": { en: "OpenMAIC integration notes" },
    "RAG 前沿知识": { en: "RAG: current state" },
    "RAG 前沿路线": { en: "RAG: current directions" },
    "□ 不是步骤堆砌": { en: "□ Not a pile of steps" },
    "□ 有互动反馈": { en: "□ Interactive feedback" },
    "□ 有最小实践": { en: "□ A smallest useful practice" },
    "□ 有证据入口": { en: "□ A way in to the evidence" },
    "□ 有边界和代价": { en: "□ Boundaries and costs" },
    "□ 有迁移任务": { en: "□ A transfer task" },
    "不要使用旧的": { en: "Do not use stale" },
    "互动题、代码或配置练习、逐步反馈": {
      en: "Interactive questions, coding or configuration exercises, step-by-step feedback",
    },
    "从一次调用走到可观测、可验证的系统": { en: "From a single call to an observable, verifiable system" },
    "先写下你要掌握的主题": { en: "Write down the topic you want to master" },
    "入口原则": { en: "What belongs at the entrance" },
    "关键状态、数据流和因果关系是什么？": { en: "What are the key states, data flows and causal relationships?" },
    "其他机器访问": { en: "Reaching it from another machine" },
    "凭据": { en: "Credentials" },
    "分层讲解、流程图、最小例子或模拟": {
      en: "Layered explanation, diagrams, a smallest example or a simulation",
    },
    "取舍与演变": { en: "Trade-offs and how it changed" },
    "受保护入口": { en: "A gated entrance" },
    "可以直接复制这段思路，再替换主题和约束：": { en: "Copy this framing and swap in your own topic and constraints:" },
    "可接受的产出": { en: "An acceptable output" },
    "可靠 Agent": { en: "Reliable agents" },
    "可靠 Agent 架构": { en: "Reliable agent architecture" },
    "后端性能与一致性": { en: "Backend performance and consistency" },
    "启动": { en: "Getting started" },
    "和知识库如何配合": { en: "How it works with the knowledge base" },
    "在课堂里做出判断": { en: "Make the call inside the classroom" },
    "它解决了什么真实痛点？不解决什么？": { en: "What real problem does it solve, and what does it not solve?" },
    "官方 GitHub ↗": { en: "Official GitHub ↗" },
    "已生成的真实课堂": { en: "Real classrooms already generated" },
    "开始课堂 ↗": { en: "Start the classroom ↗" },
    "开源项目拆解": { en: "Tearing down an open-source project" },
    "怎样提出高质量课堂请求": { en: "How to ask for a good classroom" },
    "我能否先预测结果，再用证据解释偏差？": {
      en: "Can I predict the outcome first, then explain the gap with evidence?",
    },
    "打开后是 404、白框或没有主题": { en: "It opens to a 404, a blank frame, or no topic" },
    "打开真实课堂 ↗": { en: "Open a real classroom ↗" },
    "把一个主题学到能解释、能操作、能迁移": {
      en: "Learn a topic until you can explain it, operate it and transfer it",
    },
    "换约束后，原结论还成立吗？": { en: "Does the conclusion still hold once the constraints change?" },
    "推荐学习路径": { en: "Suggested paths" },
    "提出一个可学习的问题": { en: "Ask a question worth learning from" },
    "教学对象": { en: "Who it is for" },
    "最低应回答的问题": { en: "The minimum it must answer" },
    "服务端托管": { en: "Hosted by the site" },
    "本质与机制": { en: "Nature and mechanism" },
    "查看项目与源码 →": { en: "See the project and source →" },
    "检查生成前的大纲": { en: "Check the outline before generating" },
    "模型不可用或生成失败": { en: "The model is unavailable, or generation failed" },
    "版本/方案对比、选择条件、失败案例": {
      en: "Version or approach comparisons, selection criteria, failure cases",
    },
    "版本、论文、项目或实验数据可以继续追溯。": { en: "Versions, papers, projects or measurements remain traceable." },
    "生成后，你应该看到什么": { en: "What you should see after generating" },
    "用新约束完成迁移": { en: "Transfer it under the new constraints" },
    "看到“请输入访问码”": { en: "You see “enter the access code”" },
    "真实场景任务、验收标准、复盘问题": { en: "Real-scenario tasks, acceptance criteria, review questions" },
    "练习与反馈": { en: "Practice and feedback" },
    "缓存有效性与失效边界": { en: "Cache validity and where it breaks" },
    "讲清演变原因、收益、代价和生产边界": {
      en: "Explain why it evolved, the gains, the costs and the production boundary",
    },
    "请求模板": { en: "Request template" },
    "课堂服务检查中": { en: "Checking the classroom service" },
    "课堂质量检查": { en: "Classroom quality check" },
    "迁移与验证": { en: "Transfer and validation" },
    "这通常是直接打开了": { en: "This usually means you opened" },
    "这页解决什么问题": { en: "What this page is about" },
    "适合直接尝试的主题": { en: "Topics worth trying directly" },
    "适合配合仓库、代码和架构图做项目式学习": {
      en: "Good for project-based learning with a repository, code and diagrams",
    },
    "通过约束变化建立系统直觉，再做迁移": { en: "Build intuition by changing constraints, then transfer it" },
    "遇到错误时怎么恢复": { en: "How to recover from an error" },
    "问题与目的": { en: "Problem and purpose" },
    "问题场景、目标指标、适用边界": { en: "Problem scenario, target metric, applicable boundary" },
    "阅读本地中文项目说明 ↗": { en: "Read the local Chinese project notes ↗" },

    // ── apps/learning/intuition.html ──
    "Agent 状态": { en: "Agent state" },
    "RAG 召回": { en: "RAG recall" },
    "形成直觉的产出": { en: "What this builds" },
    "打开 OpenMAIC": { en: "Open OpenMAIC" },
    "打开课堂 ↗": { en: "Open the classroom ↗" },
    "缓存失效": { en: "Cache invalidation" },
    "解释": { en: "Explain" },
    "课堂会做什么": { en: "What the classroom does" },
    "迁移": { en: "Transfer" },
    "迁移任务": { en: "Transfer task" },
    "这次练习要产出什么": { en: "What this exercise should produce" },
    "适合形成直觉的主题示例": { en: "Example topics for building intuition" },

    // ── apps/learning/transfer.html ──
    "Agent 失败迁移": { en: "Agent failure transfer" },
    "RAG 场景迁移": { en: "RAG scenario transfer" },
    "会消耗什么": { en: "What it uses" },
    "可验证性": { en: "Verifiability" },
    "后端约束迁移": { en: "Backend constraint transfer" },
    "失败处理": { en: "Failure handling" },
    "工程取舍": { en: "Engineering trade-offs" },
    "开始前知道": { en: "Know before you start" },
    "打开 DeepTutor": { en: "Open DeepTutor" },
    "打开导师 ↗": { en: "Open the tutor ↗" },
    "换场景": { en: "Change the scenario" },
    "换约束": { en: "Change the constraints" },
    "查看项目说明": { en: "See the project notes" },
    "给反例": { en: "Give a counterexample" },
    "说证据": { en: "State the evidence" },
    "迁移验证的产出": { en: "What this validation produces" },
    "返回学习中心": { en: "Return to Learning" },
    "这次验证要产出什么": { en: "What this validation should produce" },
    "适合什么时候用": { en: "When to use it" },
    "适合迁移验证的主题示例": { en: "Example topics for transfer validation" },
    "适用边界": { en: "Where it applies" },
    "验证看什么": { en: "What validation looks at" },

    // ── apps/agent-evaluation/index.html ──
    "Agent 画像": { en: "Agent profile" },
    "SLO + 运营": { en: "SLO and operations" },
    "下一步实现顺序": { en: "What gets built next, in order" },
    "不能把模型文本当作命令已执行。": { en: "Model text is not evidence that a command ran." },
    "不能替代": { en: "Does not replace" },
    "不能用模糊“看起来完成”作断言。": { en: "“Looks done” is not an assertion." },
    "不能由 README 单独证明运行行为。": { en: "A README alone cannot prove runtime behaviour." },
    "不能脱离证据编造性能或适用性。": {
      en: "Performance and applicability cannot be asserted without evidence.",
    },
    "业务操作": { en: "Business operations" },
    "产物": { en: "Artefacts" },
    "任务夹具": { en: "Task fixture" },
    "任务契约": { en: "Task contract" },
    "判断": { en: "Judgement" },
    "功能交付": { en: "Feature delivery" },
    "协作 + 责任": { en: "Collaboration and responsibility" },
    "命令记录": { en: "Command log" },
    "回归": { en: "Regression" },
    "声明": { en: "Claim" },
    "复现": { en: "Reproduce" },
    "复现 + 因果": { en: "Reproduction and causation" },
    "多 Agent 协作": { en: "Multi-agent collaboration" },
    "安全 + 状态": { en: "Safety and state" },
    "当前：设计契约与静态原型": { en: "Now: design contract and static prototype" },
    "待开发：Trace 与证据投影": { en: "To build: trace capture and evidence projection" },
    "待开发：任务接入与隔离执行": { en: "To build: task intake and isolated execution" },
    "必须回答": { en: "Must answer" },
    "执行轨迹": { en: "Execution trace" },
    "把 Agent 的判断变成可验证证据": { en: "Turn an agent’s judgement into verifiable evidence" },
    "把观察到的事实映射到任务特定的质量标准。": { en: "Map observed facts onto task-specific quality criteria." },
    "持续层": { en: "Continuous layer" },
    "按任务选择评估维度": { en: "Choose evaluation dimensions per task" },
    "改进": { en: "Improvement" },
    "改进报告": { en: "Improvement report" },
    "检索与问答": { en: "Retrieval and question answering" },
    "结果 + 回归": { en: "Outcome and regression" },
    "结果事实": { en: "Outcome facts" },
    "结果证据": { en: "Outcome evidence" },
    "缺陷修复": { en: "Defect fix" },
    "行动层": { en: "Action layer" },
    "解释层": { en: "Explanation layer" },
    "计划接入的评估产物": { en: "Evaluation artefacts planned" },
    "证据 + 质量": { en: "Evidence and quality" },
    "证据包": { en: "Evidence bundle" },
    "证据链": { en: "Evidence chain" },
    "评估契约": { en: "Evaluation contract" },
    "输入事实": { en: "Input facts" },
    "过程事实": { en: "Process facts" },
    "退出码": { en: "Exit code" },
    "长期运行": { en: "Long-running" },
    "门禁：": { en: "Gate:" },
  };

  /* ── Current language ─────────────────────────────────────────────────── */
  const stored = () => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  };

  let current = (() => {
    const s = stored();
    if (s && SUPPORTED.includes(s)) return s;
    /* No stored choice. The site defaults to English even when the browser
       asks for Chinese, because the owner asked for that; the first visit
       writes the preference so a switch sticks. */
    return DEFAULT_LANG;
  })();

  /* Translate one string. zh returns the source unchanged. */
  const t = (source) => {
    if (current === "zh" || !source) return source;
    const entry = DICT[source];
    return entry && entry.en ? entry.en : source;
  };

  /* English back to Chinese. Needed because the DOM can hold either language:
     shell.js rebuilds the sidebar with innerHTML on every render, so a node
     created while the UI was English has English text and no memory of what it
     was translated from. Looking the string up in both directions means a
     rebuilt subtree still switches correctly. */
  const REVERSE = (() => {
    const map = new Map();
    for (const [zh, entry] of Object.entries(DICT)) {
      if (entry.en && !map.has(entry.en)) map.set(entry.en, zh);
    }
    return map;
  })();

  /* The Chinese source for whatever this string currently says, in either
     language. Returns the input when it is not a known string. */
  const sourceOf = (text) => {
    if (!text) return text;
    if (DICT[text]) return text;
    const zh = REVERSE.get(text);
    return zh !== undefined ? zh : text;
  };

  /* ── Applying to the DOM ──────────────────────────────────────────────────
   * Walks text nodes rather than elements, so a translated string can sit
   * beside markup inside the same parent (<b>背景</b> —— 这个技术…). Each node
   * remembers the Chinese it came from, so switching back is exact rather
   * than a reverse lookup that might collide.
   */
  const SOURCE_ATTR = "data-tk-src";

  const translateDOM = (root = document) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        const tag = parent.tagName;
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") {
          return NodeFilter.FILTER_REJECT;
        }
        return node.nodeValue && node.nodeValue.trim()
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT;
      },
    });

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    for (const node of nodes) {
      const raw = node.nodeValue;
      const trimmed = raw.trim();
      /* Resolve what this text originally said. The node remembers it when it
         has been through here before; otherwise look the string up in both
         directions, which also covers nodes rebuilt by another script while
         the UI was in English. */
      const remembered = node[SOURCE_ATTR];
      const source = remembered !== undefined ? remembered : sourceOf(trimmed);
      if (remembered === undefined && source !== trimmed) {
        Object.defineProperty(node, SOURCE_ATTR, {
          value: source,
          writable: true,
          configurable: true,
        });
      }
      const translated = t(source);
      if (trimmed === translated) continue;
      const at = raw.indexOf(trimmed);
      node.nodeValue = raw.slice(0, at) + translated + raw.slice(at + trimmed.length);
    }

    /* Attributes that are read by people, not just machines. The original is
       kept in a plain data-* attribute rather than dataset, because a key such
       as "tk-src-placeholder" gets camel-cased into a name that dataset cannot
       address. */
    const ATTRS = ["placeholder", "title", "aria-label", "alt"];
    root.querySelectorAll("*").forEach((el) => {
      for (const attr of ATTRS) {
        const key = `${SOURCE_ATTR}-${attr}`;
        if (!el.hasAttribute(key)) {
          const value = el.getAttribute(attr);
          if (!value) continue;
          /* Store the Chinese source whichever language the attribute is in,
             so an element built while the UI was English still switches. */
          const source = sourceOf(value);
          if (source === value && !/[\u4e00-\u9fff]/.test(value)) continue;
          el.setAttribute(key, source);
        }
        const translated = t(el.getAttribute(key));
        if (el.getAttribute(attr) !== translated) el.setAttribute(attr, translated);
      }
    });

    document.documentElement.lang = current === "en" ? "en" : "zh-CN";
    document.documentElement.dataset.lang = current;
  };

  /* ── Switching ────────────────────────────────────────────────────────── */
  const setLang = (lang) => {
    if (!SUPPORTED.includes(lang)) return;
    current = lang;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* private mode — the choice just will not persist */
    }
    /* Re-translate the static markup first, then the buttons. The order
       matters: translateDOM would treat the switch's own label as a
       translatable string and swap it back to the wrong language. */
    translateDOM();
    paintLangButtons();
    document.dispatchEvent(new CustomEvent("tk:lang", { detail: { lang } }));
  };

  /* One place that decides what the language switch says. It had been written
     out three times — twice here and once in shell.js — and the copies drifted
     as soon as the default language changed. */
  const paintLangButtons = (root = document) => {
    const label = current === "en" ? "中文" : "EN";
    const aria = current === "en" ? "切换为中文" : "Switch to English";
    root.querySelectorAll("[data-tk-lang-label]").forEach((node) => {
      node.textContent = label;
    });
    root.querySelectorAll("[data-tk-lang-toggle]").forEach((node) => {
      node.setAttribute("aria-label", aria);
      node.setAttribute("title", aria);
    });
  };

  const toggleLang = () => setLang(current === "en" ? "zh" : "en");

  /* The switch button lives in the sidebar footer, which shell.js builds after
     this runs, so it is wired on demand rather than at parse time. */
  const wireLangToggles = (root = document) => {
    root.querySelectorAll("[data-tk-lang-toggle]").forEach((node) => {
      if (node.dataset.tkLangWired) return;
      node.dataset.tkLangWired = "1";
      node.addEventListener("click", toggleLang);
    });
    /* Reflect the current language on any button that just appeared. */
    paintLangButtons(root);
  };

  window.TKI18N = {
    t,
    sourceOf,
    setLang,
    toggleLang,
    paintLangButtons,
    translateDOM,
    wireLangToggles,
    get lang() {
      return current;
    },
    DEFAULT_LANG,
    STORAGE_KEY,
    /* Exposed so the audit script can report coverage without parsing source. */
    DICT,
  };

  /* Set the language attribute before the first paint so CSS can key off it,
     then translate whatever markup has already parsed. */
  document.documentElement.lang = current === "en" ? "en" : "zh-CN";
  document.documentElement.dataset.lang = current;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      translateDOM();
      wireLangToggles();
    });
  } else {
    translateDOM();
    wireLangToggles();
  }
})();
