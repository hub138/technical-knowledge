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
    "变化快": { en: "changes fast" },
    "变化中等": { en: "changes moderately" },
    "变化慢": { en: "changes slowly" },

    // ── Graph controls ──
    "关系网络": { en: "Relations" },
    "领域、主题与笔记之间的关联": { en: "How domains, topics and notes connect" },
    "从问题到证据、行动与反馈的路径": {
      en: "The path from a question to evidence, action and feedback",
    },
    "从目标、理解到练习、反馈与迁移": {
      en: "From goal and understanding to practice, feedback and transfer",
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
    "访客": { en: "Visitors" },
    "读得最多的文章与页面": { en: "Most-read notes and pages" },
    /* 2026-09-22 i18n 修复：页面文案已改为无句号（insights.html 350 行），
       原键带句号导致精确匹配失败，英文态残留中文。键去句号对齐页面。 */
    "含全景、图谱等视图页；只统计有具体位置的访问": {
      en: "Includes view pages such as panorama and graph; only visits with a concrete location are counted",
    },
    "还没有访问记录": { en: "No visits recorded yet" },
    /* 2026-09-22 i18n 修复：insights 页 354 行文案带句号，补带句号版本词条，
       双词条策略兼容两种页面形态（多 AI 并行改动期抗反复）。 */
    "知识图谱": { en: "Graph" },
    "项目与教学": { en: "Projects & Learning" },
    "Agent 评估": { en: "Agent Evaluation" },
    "学习中心": { en: "Learning" },

    // ── Learning centre ──
    "从知识点走到真正会用": { en: "From knowing a topic to actually using it" },
    "学习工具": { en: "Learning tools" },
    /* 2026-09-22 i18n 修复：键去句号，对齐 learning 页 649 行实际文案（无句号）。 */
    "每一步都有明确产出，不以“看完”为完成": {
      en: "Every step produces something. Reading to the end does not count as done",
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
    /* 2026-09-22 i18n 修复：键去句号，对齐 learning 页 865 行实际文案（无句号）。 */
    "无需再找安装命令或猜页面入口": {
      en: "No install commands to find, no entry points to guess",
    },
    "用于形成直觉和互动练习；": { en: "For intuition and interactive practice; " },
    "用于追问、研究和复习。两者不是重复功能": {
      en: "for questioning, research and review. They are not the same feature twice",
    },
    /* 2026-09-22 i18n 修复：learning 页 879 行文案带句号，补带句号版本词条（双词条策略）。 */
    "用于追问、研究和复习。两者不是重复功能。": {
      en: "for questioning, research and review. They are not the same feature twice.",
    },
    /* 中文用全角问号自带右侧空隙，英文问号没有，所以要显式补一个空格，
       否则会渲染成 "Already generated a classroom?Open my classrooms"。
       同理适用于所有以标点结尾、后面紧跟行内链接的短句。 */
    "已经生成过课堂？": { en: "Already generated a classroom? " },
    /* 【2026-09-22 去箭头同步】页面文案删掉 → 后，旧 key「打开我的课堂 →」
       成了孤儿（页面不再引用），换成本 key。 */
    "打开我的课堂": { en: "Open my classrooms" },
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
    /* 【rt20】history 页正文句：EN 态 DOM 实测残留 30 条，其中静态
       正文句（hero 副题、panel 副题、purpose 长句、四阶段句、rules
       三条、callout 句）此前全部缺词条。逐条补齐。 */
    "继续打开本机生成过的互动课堂，查看生成状态，并把稳定结论复核后收录进知识库。": {
      en: "Reopen interactive classrooms generated on this machine, check how generation went, and file the settled conclusions into the knowledge base after review.",
    },
    "按时间倒序刷新；进行中的任务会实时显示进度，失败任务保留原因。": {
      en: "Refreshed newest-first; running jobs show live progress and failed runs keep their reason.",
    },
    "每个课堂生成时，OpenMAIC 会把课程名和任务进度写到本机数据目录；本页直接读取这些记录，所以你不用记课堂 ID 或端口。课堂负责继续学习，知识库负责“复核后收录”。": {
      en: "When a classroom is generated, OpenMAIC writes the course name and job progress to a local data directory; this page reads those records, so you never have to remember classroom IDs or ports. The classroom is for continued learning; the knowledge base is for “filed after review”.",
    },
    "从生成的课堂到写进知识库，按下面的顺序操作即可。": {
      en: "From a generated classroom into the knowledge base, follow the steps below.",
    },
    "在 OpenMAIC 中确认主题、范围和模型调用，再生成互动课堂。": {
      en: "Confirm the topic, scope and model calls in OpenMAIC, then generate the interactive classroom.",
    },
    "在上面的列表里重新打开，继续编辑、练习或复用。": {
      en: "Reopen it from the list above to keep editing, practising or reusing.",
    },
    "检查事实、来源、适用边界和练习是否真的覆盖目标；模型生成的解释不能替代核验。": {
      en: "Check that facts, sources, applicability boundaries and exercises actually cover the goal; a model-generated explanation is no substitute for verification.",
    },
    "把稳定结论整理到对应领域的 Markdown 主题页，保留来源、版本和待复核项。": {
      en: "Write the settled conclusions into the topic page for the domain, keeping sources, versions and items pending review.",
    },
    "在上面直接打开，或到 OpenMAIC 首页查看、编辑和继续学习。": {
      en: "Open them right here, or head to the OpenMAIC home page to view, edit and keep learning.",
    },
    "按技术对象归类阅读，来源与更新时间可追踪。": {
      en: "Read them grouped by technical object, with traceable sources and update times.",
    },
    "复制课堂中已核验的机制、反例和实验结果，合并到现有主题，而不是整页搬运。": {
      en: "Copy verified mechanisms, counter-examples and experiment results into existing topics instead of moving whole pages.",
    },
    "新概念、未核验断言和一次性练习留在课堂，等待下一轮事实检查。": {
      en: "New concepts, unverified claims and one-off exercises stay in the classroom, awaiting the next round of fact-checking.",
    },
    "失败任务会保留原因，避免把“模型超时”误当成知识结论。多数超时是模型链路抖动，重跑通常即可恢复。": {
      en: "Failed runs keep their reason, so a “model timeout” is never mistaken for a knowledge conclusion. Most timeouts are transient model-chain flakiness; rerunning usually recovers.",
    },
    "当前 OpenMAIC 的课堂列表主要由它自己的浏览器存储管理，知识库服务无法安全读取另一个端口的 IndexedDB，也不应该绕过你的确认把生成内容写进长期知识。": {
      en: "OpenMAIC manages its own classroom list in its own browser storage; the knowledge-base service cannot safely read an IndexedDB on another port, and should not write generated content into long-term knowledge without your sign-off.",
    },
    "还没有可显示的生成任务。": {
      en: "No generation jobs to show yet.",
    },
    /* 【rt20】history 页动态卡片 UI 串（渲染脚本每 5s 重写
       innerHTML，translateDOM 覆盖不到，已改走 TKI18N.t()）。
       课程标题（"RAG重排与混合检索"等）是用户数据不译。 */
    "已生成": { en: "Generated" },
    "失败": { en: "Failed" },
    /* 进行中=生成任务状态，运行中=服务在线状态，二者语义不同，不能共享
       "Running"：REVERSE 反查表先到先得，共享会让 EN 态 DOM 反查回翻成
       错误的中文（i18n_dict_audit 碰撞）。 */
    "进行中": { en: "In progress" },
    "未知状态": { en: "Unknown" },
    "场景": { en: "Scenes" },
    "任务": { en: "Job" },
    "生成未完成": { en: "Generation unfinished" },
    "查看原因": { en: "Why it failed" },
    "未记录具体原因": { en: "no reason recorded" },
    "未命名的生成任务": { en: "Untitled generation job" },
    "暂时无法读取生成记录；OpenMAIC 课堂本身仍可从上方入口打开。": {
      en: "Cannot read the generation log right now; OpenMAIC classrooms remain reachable from the entry above.",
    },
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

    // ── Search + shortcuts ──
    "搜索知识、机制、项目或来源": { en: "Search knowledge, mechanisms, projects, sources" },
    "快捷键": { en: "Shortcuts" },
    "键盘快捷键": { en: "Keyboard shortcuts" },
    "阅读时不必离开键盘。Esc 随时关闭本面板": {
      en: "Read without leaving the keyboard. Esc closes this panel at any time",
    },
    "关闭": { en: "Close" },
    "然后": { en: "then" },
    "归档": { en: "Archive" },
    /* 【rt24】主题名词条。与领域名同理：侧栏/目录/矩阵的主题是导航
       结构，EN 态需要可读译名。44 个主题按领域内含义精译，保持短
       （导航标签位）。 */
    "性能": { en: "Performance" },
    /* 方法=导航主题标签（matrix.js 消费）。核心方法=论文页 L2 八模块标签
       （papers/paper.html 的 MODULES），二者语义不同，不共享 "Method"：
       REVERSE 反查表先到先得，共享会让 EN 态回翻错中文。 */
    "方法": { en: "Method" },
    "概览": { en: "Section overview" },
    "入门": { en: "Getting started" },
    "心智模型": { en: "Mental models" },
    "工程实践": { en: "Engineering practice" },
    "调试": { en: "Debugging" },
    "组织与流程": { en: "Organisation and process" },
    /* 【rt24 补漏】api/notes 实测比首次清单多 4 个主题，覆盖核对发现。
       质量与运营/资源与容量两条与 rt14 批（文件尾）重复，已删去这里的
       早期版本：JS 对象重复 key 只保留最后一个，留着的是死代码
       （i18n_dict_audit 报 2x duplicate）。 */
    "配置": { en: "Configuration" },
    "首页": { en: "Home" },
    /* 【rt24·标题批 1/7】AI 系统工程域 94 篇文章标题。用户要求
       EN 态标题翻译（点名篇目在此域）。标题多为机制陈述句，按
       导航语气精译。Clippings 外部剪藏标题保留原文不译。 */
    "AI 系统工程：把模型能力变成生产能力": { en: "AI systems engineering: turning model capability into production capacity" },
    "AI 辅助研发必须形成证据闭环": { en: "AI-assisted development must close the evidence loop" },
    "知识库的学习闭环：从来源到迁移": { en: "The knowledge base learning loop: from sources to transfer" },
    "Agent状态机与任务恢复：进度是状态不是聊天记录": { en: "Agent state machines and task recovery: progress is state, not chat history" },
    "ReAct计划执行搜索：三种行动范式的适用边界": { en: "ReAct, planning, and search: where each action paradigm fits" },
    "代码智能体需要结构索引、任务探索与运行证据": { en: "Coding agents need structural indexes, task exploration, and runtime evidence" },
    "任务分解的质量决定 Agent 的上限": { en: "Task decomposition quality caps the agent" },
    "先用工作流，只有路径无法预先枚举时才使用 Agent": { en: "Use workflows first; reach for agents only when paths cannot be enumerated" },
    "反思要有外部锚点，否则只是自我说服": { en: "Reflection needs external anchors, or it is self-persuasion" },
    "多智能体只在能并行或需要独立上下文时才值得": { en: "Multi-agent systems pay off only for parallelism or isolated contexts" },
    "工具是受约束的能力，不是提示词里的函数名": { en: "Tools are constrained capabilities, not function names in a prompt" },
    "构建可靠 Agent 应用：从模型调用到可运营系统": { en: "Building reliable agent apps: from model calls to operable systems" },
    "模型负责判断，运行时负责执行语义": { en: "Models judge; the runtime owns execution semantics" },
    "浏览器与Computer Use Agent：高噪声观察下的受控操作": { en: "Browsers and computer-use agents: controlled action under noisy observation" },
    "结构化输出与约束解码：schema约束形状，事实另需验证": { en: "Structured output and constrained decoding: schemas constrain shape; facts still need checking" },
    "结构化输出的约束解码：让模型输出可解析": { en: "Constrained decoding for structured output: making model output parseable" },
    "AI 可以做语义决策，系统必须守住事实边界": { en: "AI can make semantic decisions; the system must guard factual boundaries" },
    "执行证据必须独立于 AI 结论": { en: "Execution evidence must be independent of AI conclusions" },
    "提示注入和工具越权是不同威胁": { en: "Prompt injection and tool privilege escalation are different threats" },
    "模型与数据供应链需要可验证来源": { en: "Model and data supply chains need verifiable provenance" },
    "模型权重文件是可执行输入：从 pickle 信任模型到格式即边界": { en: "Model weight files are executable input: from pickled trust to format-as-boundary" },
    "沙箱限制能力，策略限制行为": { en: "Sandbox limits capability; policy limits behaviour" },
    "红队测试与越狱防御：提示注入的攻防工程": { en: "Red-teaming and jailbreak defence: the engineering of prompt injection" },
    "AI 平台必须统一模型、数据、评测与发布版本": { en: "An AI platform must unify models, data, evaluation, and releases" },
    "FlashAttention是IO感知的精确算法，不是近似": { en: "FlashAttention is IO-aware and exact, not an approximation" },
    "GPU显存管理决定服务容量上限": { en: "GPU memory management caps serving capacity" },
    "Prefill 与 Decode 决定 LLM 服务如何调度": { en: "Prefill and decode decide how LLM serving schedules" },
    "批处理、KV 缓存、量化与并行如何改变服务容量": { en: "How batching, KV cache, quantisation and parallelism change serving capacity" },
    "推理批处理的两难：吞吐与延迟的调度天平": { en: "The inference batching dilemma: throughput versus latency" },
    "推理服务的单位请求成本从token定价推出来": { en: "Unit request cost of inference serving follows from token pricing" },
    "推理服务的核心矛盾是延迟、吞吐、显存与质量": { en: "Inference serving's core tension: latency, throughput, memory, quality" },
    "模型服务架构从单进程到分布式副本": { en: "Model serving architecture: from single process to distributed replicas" },
    "模型路由与级联：小模型过滤大模型兜底的省钱结构": { en: "Model routing and cascades: small models filter, big models backstop" },
    "模型量化的精度经济学：位宽精度与显存的三角": { en: "The economics of quantisation: bits, precision, and memory" },
    "数据集、特征与模型版本必须可追溯": { en: "Datasets, features, and model versions must be traceable" },
    "数据飞轮的工程闭环：日志回流清洗与标注": { en: "The data flywheel loop: log reflux, cleaning, and labelling" },
    "模型发布需要注册、灰度与回滚": { en: "Model release needs a registry, canary rollout, and rollback" },
    "训练数据治理：来源、许可与污染决定语料的长期价值": { en: "Training data governance: provenance, licensing, and contamination decide long-term value" },
    "KV缓存与上下文长度的显存账：为什么长上下文贵": { en: "The KV-cache memory ledger: why long context is expensive" },
    "上下文工程是在有限预算内构造决策现场": { en: "Context engineering: building the decision scene within a budget" },
    "上下文工程的分层设计：系统提示工具结果与记忆": { en: "Layered context engineering: system prompts, tool results, and memory" },
    "多轮对话要管理上下文而不是累积它": { en: "Multi-turn dialogue must manage context, not accumulate it" },
    "模型提出候选，系统定义正确性": { en: "The model proposes; the system defines correctness" },
    "记忆写入治理：来源、主体与过期决定记忆的可信度": { en: "Memory-write governance: source, subject, and expiry decide trust" },
    "记忆是受治理的状态，不是更长的聊天记录": { en: "Memory is governed state, not a longer chat log" },
    "跨会话状态的一致性先于记忆的长度": { en: "Cross-session consistency comes before memory length" },
    "预训练、后训练、RAG 与工具改变不同层次": { en: "Pre-training, post-training, RAG, and tools change different layers" },
    "GPU执行模型与显存层级：SIMT与合并访存": { en: "The GPU execution model and memory hierarchy: SIMT and coalesced access" },
    "LoRA与参数高效微调：改行为不改基座": { en: "LoRA and parameter-efficient tuning: change behaviour, not the base" },
    "MoE 用稀疏激活换取参数容量和通信复杂度": { en: "MoE trades sparse activation for parameter capacity and communication cost" },
    "MoE路由的工程问题：负载不均与显存碎片": { en: "MoE routing in practice: load imbalance and memory fragmentation" },
    "Scaling Law 把训练预算分配成可测量假设": { en: "Scaling laws turn training budgets into measurable hypotheses" },
    "Token、Embedding 与表示学习连接数据和模型": { en: "Tokens, embeddings, and representation learning connect data and models" },
    "Transformer 如何把序列建模成可扩展计算": { en: "How Transformers turn sequence modelling into scalable computation" },
    "位置编码和长上下文限制有效利用": { en: "Positional encoding and long-context utilisation limits" },
    "分布式训练与并行策略如何切分模型": { en: "How distributed training and parallelism split a model" },
    "后训练对齐与微调改变行为边界": { en: "Post-training alignment and tuning shift behavioural boundaries" },
    "多模态模型把不同输入映射到共同推理接口": { en: "Multimodal models map different inputs to a shared reasoning interface" },
    "投机采样与推测解码：小模型带路大模型确认": { en: "Speculative sampling and decoding: small model leads, big model confirms" },
    "混合精度与数值稳定：低位宽训练的溢出与下溢管理": { en: "Mixed precision and numerical stability: managing overflow and underflow" },
    "蒸馏与模型合并：用小模型承接已验证的能力": { en: "Distillation and model merging: small models carrying proven capability" },
    "解码与采样参数：概率分布到生成文本的控制面": { en: "Decoding and sampling: the control plane from distribution to text" },
    "解码采样决定生成行为而不是知识本身": { en: "Decoding and sampling shape generation behaviour, not knowledge" },
    "预训练数据决定模型能力上限": { en: "Pre-training data caps model capability" },
    "AI 技术动态": { en: "AI tech radar" },
    "Agent 技术栈选型不是框架排名": { en: "Agent stack selection is not a framework ranking" },
    "MCP与A2A的分工：工具协议与Agent协议不互相替代": { en: "MCP versus A2A: tool protocol and agent protocol do not replace each other" },
    "MCP 接入必须验证协议、身份与工具约定": { en: "MCP integration must verify protocol, identity, and tool contracts" },
    "MCP 连接能力，A2A 委托任务": { en: "MCP connects capabilities; A2A delegates tasks" },
    "模型、框架、运行时与协议解决不同问题": { en: "Models, frameworks, runtimes, and protocols answer different questions" },
    "精调与RAG的边界：什么时候微调更划算": { en: "Fine-tuning versus RAG: when tuning pays off" },
    "GraphRAG 适合关系与全局问题但成本更高": { en: "GraphRAG fits relational and global questions, at higher cost" },
    "RAG 数据管道从文档到可引用证据": { en: "RAG data pipelines: from documents to citable evidence" },
    "RAG的新鲜度与权限传播：撤回的数据不能再被检索到": { en: "RAG freshness and permission propagation: revoked data must stay unretrievable" },
    "RAG 的核心是选择可引用证据": { en: "The heart of RAG is selecting citable evidence" },
    "向量数据库不是 RAG 本身": { en: "A vector database is not RAG itself" },
    "多模态RAG：图表、PDF与音频的证据不能只靠文本化": { en: "Multimodal RAG: charts, PDFs, and audio need more than text conversion" },
    "检索从一次查询演进为有状态的证据获取": { en: "Retrieval is evolving from one-shot queries to stateful evidence gathering" },
    "混合检索、重排与查询改写各自解决什么问题": { en: "Hybrid retrieval, reranking, and query rewriting: what each one solves" },
    "Agent 的缓存与结果复用": { en: "Agent caching and result reuse" },
    "Agent评估系统的设计约定": { en: "The design contract of an agent evaluation system" },
    "Agent 评测必须覆盖轨迹，而不只看最终答案": { en: "Agent evaluation must cover trajectories, not just final answers" },
    "RAG 评测要分离检索质量与生成质量": { en: "RAG evaluation must separate retrieval quality from generation quality" },
    "人在环路要设在不可逆的决策点": { en: "Put humans in the loop at irreversible decision points" },
    "可观测性必须能重建一次决策": { en: "Observability must be able to reconstruct a decision" },
    "可靠生成需要结构、证据、拒答与回归": { en: "Reliable generation needs structure, evidence, refusal, and regression" },
    "失败要分类才能对症下药": { en: "Failures must be classified before they can be treated" },
    "学习活动需要结果、轨迹与迁移证据": { en: "Learning activities need outcome, trajectory, and transfer evidence" },
    "幻觉的工程边界——哪些场景模型不该被单独信任": { en: "The engineering boundary of hallucination — where models must not be trusted alone" },
    "成本控制要从上下文和重试两头下手": { en: "Cost control works both ends: context and retries" },
    "提示词是代码，要版本化和回归测试": { en: "Prompts are code: version them and regression-test them" },
    "离线评测与在线评测回答不同问题": { en: "Offline and online evaluation answer different questions" },
    "评测集的构建与维护决定所有评测的地基": { en: "Building and maintaining eval sets is the foundation of all evaluation" },
    "评测集的构建与维护：从场景采样到难度分层": { en: "Building and maintaining eval sets: from scenario sampling to difficulty tiers" },
    /* 【rt25·标题批 2/7】缺陷分析域 60 篇。案例标题按
       "Case N: mechanism — consequence" 骨架精译，保留编号与
       双段结构，方便与中文原题对照。 */
    "案例七：兼容与性能——滞后的依赖与放大的日志": { en: "Case 7: compatibility and performance — lagging dependencies and amplified logs" },
    "案例四十三：升级把前提带走了——依赖行为变更引发的下游失效": { en: "Case 43: the upgrade took its premises away — downstream breakage from dependency behaviour changes" },
    "从复现到回归——让证据走完一圈": { en: "From reproduction to regression — letting evidence run the full loop" },
    "回归风险评估把修复的爆炸半径圈出来": { en: "Regression risk assessment fences off the blast radius of a fix" },
    "回归风险评估的通用骨架：从变更面到测试选择": { en: "A general skeleton for regression risk assessment: from change surface to test selection" },
    "证据链的够用判据——从孤证到可裁决": { en: "When the evidence chain is enough — from a lone data point to a decidable case" },
    "案例二十六：公告栏没查门禁——Redis 的 ACL 键名泄露与解析崩溃": { en: "Case 26: the bulletin board skipped the gate — Redis ACL key-name leaks and parser crashes" },
    "案例五：安全两例——认证绕过与带漏洞依赖": { en: "Case 5: two security cases — auth bypass and a vulnerable dependency" },
    "案例四十四：投毒不是写错，是写给你看——依赖投毒的三个真实剧本": { en: "Case 44: poisoning is not a bug, it is written for you — three real dependency-poisoning scripts" },
    "并发缺陷的复现策略：压力放大与确定性调度": { en: "Reproducing concurrency bugs: stress amplification and deterministic scheduling" },
    "时间型缺陷的判定树：过期竞态与时钟依赖": { en: "A decision tree for time-dependent bugs: expiry races and clock dependencies" },
    "案例三十一：回收之后还在飞——跨线程复用可回收对象": { en: "Case 31: still flying after recycling — cross-thread reuse of recyclable objects" },
    "案例三十二：取到了已经不存在的那个——估算器的读取竞态": { en: "Case 32: fetched the one that no longer exists — a read race in the estimator" },
    "案例三：并发两面——写回调卡死与心跳竞态": { en: "Case 3: two faces of concurrency — a stuck write callback and a heartbeat race" },
    "案例二十：关闭之后还有人在用——生命周期的时序竞态": { en: "Case 20: someone still using it after close — a lifecycle timing race" },
    "案例十九：在回调里改自己——清理路径的重入与回收后复用": { en: "Case 19: mutating itself from a callback — re-entry on the cleanup path and use after recycle" },
    "案例十四：一方取消，旁观者陪葬——RocksDB 状态加载的并发陷阱": { en: "Case 14: one side cancels, bystanders go down too — a concurrency trap in RocksDB state loading" },
    "案例四十：谁在回答谁——Pulsar 连接复用与去重的键不完整": { en: "Case 40: who is answering whom — Pulsar connection reuse and incomplete dedup keys" },
    "修复优先级排序修复顺序的决策框架": { en: "Fix priority: a decision framework for repair order" },
    "影响判断——这条修复值不值得跟": { en: "Judging impact — whether this fix is worth following" },
    "影响面估算先于修复——从改一行到伤多少服务": { en: "Estimating blast radius before fixing — from one changed line to how many hurt services" },
    "案例三十七：锁自己变成了瓶颈——争用背后的临界区错配": { en: "Case 37: the lock became the bottleneck — critical-section mismatch behind the contention" },
    "案例二十五：库自带了一支军队——OpenBLAS 的隐式线程": { en: "Case 25: the library shipped an army — OpenBLAS and its hidden threads" },
    "案例二十四：并行度被自己折叠——repartition 的 2 的幂倾斜": { en: "Case 24: parallelism folded by itself — power-of-two skew in repartition" },
    "案例三十三：估算不等于算术——按大小推条目的错算": { en: "Case 33: estimation is not arithmetic — miscounting entries from sizes" },
    "案例三十九：身份在改写中丢失——RLS 子查询与视图 DEFAULT 的静默失真": { en: "Case 39: identity lost in rewriting — silent distortion from RLS subqueries and view DEFAULTs" },
    "案例三十四：省下的句柄与多出的删除——一次优化引入的回归": { en: "Case 34: handles saved, deletions gained — a regression introduced by an optimisation" },
    "案例三十：中间缺了一块——跨地域复制的 ack 空洞": { en: "Case 30: a hole in the middle — ack gaps in cross-region replication" },
    "案例九：数字越过了边界——Redis 里三次截断导致的崩溃": { en: "Case 9: numbers across the boundary — three truncations that crashed Redis" },
    "案例二十九：离开的人还占着座位——机架信息的陈旧映射": { en: "Case 29: the departed still hold seats — stale rack-info mappings" },
    "案例二：静默错算——Spark SQL Union 的别名陷阱": { en: "Case 2: silent miscalculation — the alias trap in Spark SQL unions" },
    "案例十三：键序与列名——Spark SQL 又两种静默错算": { en: "Case 13: key order and column names — two more silent miscounts in Spark SQL" },
    "案例十八：空集合被当成了\"全部已确认\"——游标跳过的位置": { en: "Case 18: an empty set read as \"all confirmed\" — positions the cursor skipped" },
    "案例十六：数据被自己人删掉——entry log 头里的假账": { en: "Case 16: data deleted by its own side — false books in the entry-log header" },
    "案例十：类型说谎时——静默删数据的 TTL 与算错的比较": { en: "Case 10: when types lie — a TTL that silently deletes data and a miscounted comparison" },
    "案例四十一：确认了却没确认——Pulsar 消息语义的三种失真": { en: "Case 41: confirmed but not confirmed — three distortions of Pulsar message semantics" },
    "案例四十二：备份里的假账——恢复路径的静默损坏": { en: "Case 42: false books in the backup — silent corruption on the restore path" },
    "静默失真的检测靠对账与不变量而不是报错": { en: "Detecting silent distortion relies on reconciliation and invariants, not on errors" },
    "症状到机制的判定树——新缺陷的归类入口": { en: "A symptom-to-mechanism decision tree — the entry point for classifying new defects" },
    "磁盘坏道与静默损坏的检测修复路径": { en: "Detecting and repairing bad sectors and silent corruption" },
    "网卡静默降速与链路劣化：协商、光功率与吞吐基线": { en: "Silent NIC downshift and link degradation: negotiation, optical power, and throughput baselines" },
    "案例一：垃圾回收线程的终止——BookKeeper 磁盘写满": { en: "Case 1: termination of the garbage-collection thread — BookKeeper with a full disk" },
  "案例三十六：写被自己的回调堵住——挂起的 add 回调": { en: "Case 36: writes blocked by their own callback — a stuck add callback" },
    "案例二十一：异常路径上没有完成——永不兑现的 future": { en: "Case 21: never completed on the error path — futures that never resolve" },
    "案例二十三：一次抖动变成一次重算——SASL 拉取没有重试": { en: "Case 23: one hiccup becomes a recompute — SASL fetch without retries" },
    "案例二十二：时间也是输入——夏令时让序列生成越界": { en: "Case 22: time is input too — daylight saving pushes sequence generation out of range" },
    "案例八：承诺没有兑现——Pulsar 里六个永不返回的请求": { en: "Case 8: promises unkept — six Pulsar requests that never return" },
    "案例十一：上游修好了，你这边没有——一个发行分支的移植缺口": { en: "Case 11: fixed upstream, not on your side — a backport gap on a release branch" },
    "案例十二：调度线程的永久等待——广播写锁不释放": { en: "Case 12: the scheduler waits forever — a broadcast write lock never released" },
    "缺陷分析五步法——从个案到通用模型": { en: "A five-step method for defect analysis — from incident to general model" },
    "缺陷分析的本质——期望与现实的偏差": { en: "The essence of defect analysis — the gap between expectation and reality" },
    "缺陷分析：从个案到体系——导读与开源地图": { en: "Defect analysis: from incidents to systems — a guide and an open-source map" },
    "案例六：容量与泄漏——连接泄漏和 SST 堆积": { en: "Case 6: capacity and leaks — connection leaks and SST pile-up" },
    "案例十七：删除列表里的幽灵——永不收敛的待删账本": { en: "Case 17: ghosts in the deletion list — a deletion ledger that never converges" },
    "资源泄漏的三段式排查法：预筛确认与归因": { en: "A three-stage approach to resource leaks: pre-screening, confirmation, and attribution" },
    "案例三十五：后写的覆盖了先写的——策略层级的覆盖顺序": { en: "Case 35: later writes override earlier ones — override order across policy tiers" },
    "案例三十八：没有写下来的版本——默认值里的迁移债": { en: "Case 38: the version that was never written down — migration debt hidden in defaults" },
    "案例十五：错误最晚在哪一刻暴露——Imputer 与公平调度的两种延迟": { en: "Case 15: the latest moment an error can surface — two delayed failures, Imputer and fair scheduling" },
    "案例四：配置不生效——recover 速率与重复日志": { en: "Case 4: configuration that never took effect — recovery rate and duplicated logs" },
    "配置类缺陷的静态防线：schema校验与默认值审计": { en: "A static front line against configuration defects: schema validation and default-value audits" },
    /* 【rt26·标题批 3/7】后端系统域 59 篇（域总览已于 rt24 领域批译出，
       本批插入其余 58 条）。方法论句式直译，保留冒号骨架。 */
    "任务生命周期必须覆盖进程、日志、超时与清理": { en: "A task lifecycle must cover process, logs, timeouts and cleanup" },
    "分布式锁的正确与错误用法：fencing与租约": { en: "Distributed locks, right and wrong: fencing and leases" },
    "后台任务不能依赖终端会话维持生命周期": { en: "Background tasks cannot rely on a terminal session for their lifecycle" },
    /* 【rt26】原译 93 字符恰好超关系图两行容量 1 字（92），去掉冗余 from 缩到 86。 */
    "幂等性的完整谱系：从操作语义到删除接口的天然陷阱": { en: "The full spectrum of idempotency: operation semantics and the natural trap of delete APIs" },
    "并发控制先定义共享状态和完成条件": { en: "Concurrency control starts by defining shared state and completion conditions" },
    "调度必须同时处理优先级、公平与背压": { en: "Scheduling must handle priority, fairness and backpressure together" },
    "队列和流系统用时间与容量换取解耦": { en: "Queues and stream systems trade time and capacity for decoupling" },
    "限流熔断与隔离控制故障半径": { en: "Rate limiting, circuit breaking and isolation control the failure radius" },
    "Raft选举与日志复制把共识变成工程实现": { en: "Raft elections and log replication turn consensus into an engineering implementation" },
    "Saga把长事务变成补偿链，代价是失去隔离性": { en: "Saga turns long transactions into compensation chains at the cost of isolation" },
    "一致性模型与共识解决不同问题": { en: "Consistency models and consensus solve different problems" },
    "健康检查只能提供有时效的失败证据": { en: "Health checks only provide time-limited evidence of failure" },
    "分布式事务的分类与各自失败形态": { en: "A taxonomy of distributed transactions and how each one fails" },
    "复制分片与再平衡改变数据归属": { en: "Replication, sharding and rebalancing change data ownership" },
    "时间顺序与因果必须显式建模": { en: "Time ordering and causality must be modelled explicitly" },
    "消息投递与业务提交需要显式的一致性边界": { en: "Message delivery and business commits need an explicit consistency boundary" },
    "电源与时钟：UTC与单调钟的工程含义": { en: "Power and clocks: the engineering meaning of UTC and monotonic time" },
    "租约必须配合 Fencing Token 阻止过期持有者": { en: "Leases must pair with fencing tokens to stop expired holders" },
    "超时、重试与幂等共同定义调用语义": { en: "Timeouts, retries and idempotency together define call semantics" },
    "超时的层次设计：连接、读写与整链路的预算分配": { en: "Layered timeout design: budgeting across connections, reads/writes and the full chain" },
    "部分失败决定分布式系统的设计": { en: "Partial failure dictates distributed-system design" },
    "重试的正确姿势：退避、抖动与重试预算": { en: "Retries done right: backoff, jitter and retry budgets" },
    "CDN的回源与边缘缓存：静态加速背后的机制": { en: "CDN origin fetches and edge caching: the mechanics behind static acceleration" },
    "DNS解析的全链路：递归缓存与失效传播": { en: "The full path of DNS resolution: recursive caching and invalidation propagation" },
    "Kubernetes 管理资源状态，不管理业务正确性": { en: "Kubernetes manages resource state, not business correctness" },
    "QUIC之后的传输层：HTTP3与连接迁移的工程红利": { en: "The transport layer after QUIC: HTTP/3 and the engineering dividends of connection migration" },
    "TCP连接建立与断开的状态机：握手挥手与异常路径": { en: "The TCP connection state machine: handshakes, teardown and abnormal paths" },
    "TLS握手与证书链：信任是怎么一层层背书的": { en: "The TLS handshake and certificate chains: how trust is endorsed layer by layer" },
    "socket读写缓冲区：拥塞窗口与应用层背压的连接点": { en: "Socket read/write buffers: where the congestion window meets application backpressure" },
    "代理与网关的谱系：正向反向与sidecar各自解决什么": { en: "A spectrum of proxies and gateways: what forward, reverse and sidecar each solve" },
    "基础设施选型先比较责任边界与故障模型": { en: "Infrastructure selection starts with comparing responsibility boundaries and failure models" },
    "容器隔离资源边界与镜像身份": { en: "Containers isolate resource boundaries and image identity" },
    "容量规划与压测要用同一个负载模型说话": { en: "Capacity planning and load testing must speak the same load model" },
    "拥塞控制的四代演进：从AIMD到BBR的思路转变": { en: "Four generations of congestion control: the shift in thinking from AIMD to BBR" },
    "服务网格控制面与数据面：mTLS与流量治理": { en: "Service mesh control plane and data plane: mTLS and traffic governance" },
    "服务网格统一通信治理但不负责业务正确性": { en: "Service meshes unify communication governance, not business correctness" },
    "网卡与内核旁路：中断与轮询的取舍": { en: "NICs and kernel bypass: the trade-off between interrupts and polling" },
    "网络命名空间与容器网络：vethbridge与overlay": { en: "Network namespaces and container networking: veth, bridge and overlay" },
    "长连接网关的工程要点：心跳推送与连接迁移": { en: "Engineering essentials of long-connection gateways: heartbeats, push and connection migration" },
    "ACL 把权限挂在资源上": { en: "ACLs attach permissions to resources" },
    "API 接口约定定义输入输出和演进边界": { en: "API contracts define inputs, outputs and evolution boundaries" },
  "HTTP语义的分层：方法、状态码与头部的约定角色": { en: "HTTP semantics in layers: the contract roles of methods, status codes and headers" },
    "HTTP 请求穿过浏览器、网络与服务端边界": { en: "An HTTP request crosses browser, network and server boundaries" },
    "RPC框架的通用骨架：序列化连接管理与超时传递": { en: "A common skeleton for RPC frameworks: serialisation, connection management and timeout propagation" },
    "事件驱动架构的解耦代价：最终一致与可追溯性": { en: "The decoupling cost of event-driven architecture: eventual consistency and traceability" },
    "优雅停机的完成语义：排空连接与任务交接": { en: "The completion semantics of graceful shutdown: draining connections and handing over tasks" },
    "健康检查的三层语义：存活就绪与深度": { en: "Three levels of health-check semantics: liveness, readiness and depth" },
    "分布式限流的四种算法：计数漏桶令牌与滑动窗口": { en: "Four algorithms for distributed rate limiting: counters, leaky buckets, tokens and sliding windows" },
    "容量估算的通用骨架：从峰值QPS到机器数的推导演练": { en: "A general skeleton for capacity estimation: working from peak QPS to machine count" },
    "微服务划分的判据：从团队认知到数据边界": { en: "Criteria for partitioning microservices: from team cognition to data boundaries" },
    "服务发现与负载均衡决定请求发往哪里": { en: "Service discovery and load balancing decide where requests go" },
    "服务降级是有损服务，损什么损多少要变成业务决策": { en: "Service degradation is lossy serving: what to lose and how much must become a business decision" },
    "流量入口只负责路由与连接，不负责业务正确性": { en: "Traffic entry points handle routing and connections, not business correctness" },
    "缓存改变读写路径、一致性与故障模式": { en: "Caches change read/write paths, consistency and failure modes" },
    "缓存穿透击穿与雪崩是三种不同的失效模式": { en: "Cache penetration, breakdown and avalanche are three distinct failure modes" },
    "背压的传递链路：从下游饱和到上游减速": { en: "The propagation chain of backpressure: from downstream saturation to upstream slowdown" },
    "认证授权决定请求能看什么和做什么": { en: "Authentication and authorisation decide what a request can see and do" },
    "连接池的容量数学：池大小与排队等待的权衡": { en: "The capacity math of connection pools: sizing versus queueing wait" },
    /* 【rt27·标题批 4/7】软件构建域 56 篇（域总览已于 rt24 领域批译出，
       本批插入其余 55 条）。方法论句式直译，保留冒号骨架。 */
    "Docker与K8s词汇的设计逻辑": { en: "The design logic of Docker and K8s vocabulary" },
    "Git 操作先区分工作区、索引与历史": { en: "Git operations start by separating the working tree, index and history" },
    "Linux常用命令的词源地图": { en: "An etymological map of common Linux commands" },
    "Linux 调查先收集事实再改变状态": { en: "Linux troubleshooting collects facts before changing state" },
    "Make 描述依赖图，不自动保证可重复构建": { en: "Make describes the dependency graph; it does not guarantee reproducible builds" },
    "依赖供应链需要锁定来源与构建输入": { en: "Dependency supply chains need locked sources and build inputs" },
    "依赖升级按风险分层：验证阶梯、节奏策略与 CVE 响应": { en: "Dependency upgrades are tiered by risk; compatibility verification follows the tiers" },
    "依赖升级的半衰期策略：跟随与锁定的平衡": { en: "A half-life strategy for dependency upgrades: balancing following and locking" },
    "本地复现环境是修线上问题的第一现场": { en: "A local reproduction environment is the first crime scene for production issues" },
    "维护者信任是供应链信任的地基：贡献者治理与维护者变更审计": { en: "Maintainer trust is the foundation of supply-chain trust: contributor governance and maintainer-change audits" },
    "词汇即接口：Linux与容器命令的词源与设计": { en: "Vocabulary is the interface: the etymology and design of Linux and container commands" },
    "静态分析在门禁里定位为证据生成器": { en: "Static analysis is positioned in the gate as an evidence generator" },
    "API 与 Schema 演进必须兼容新旧消费者": { en: "API and schema evolution must stay compatible with old and new consumers" },
    "API演进的兼容性纪律：废弃流程与版本策略": { en: "The compatibility discipline of API evolution: deprecation flows and versioning strategy" },
    "AST 提供语法结构，语义仍需符号与运行证据": { en: "ASTs provide syntactic structure; semantics still need symbol and runtime evidence" },
    "分层与依赖方向决定可测试性和演进成本": { en: "Layering and dependency direction decide testability and evolution cost" },
    "技术方案先写清约束、取舍与验证": { en: "Technical designs start by stating constraints, trade-offs and verification" },
    "架构组织高成本决策与演进边界": { en: "Architecture organises high-cost decisions and evolution boundaries" },
    "架构适应度函数：把架构约束写成可执行检查": { en: "Architecture fitness functions: turning architectural constraints into executable checks" },
    "状态机把隐式状态变成显式约束": { en: "State machines turn implicit state into explicit constraints" },
    "策略与依赖注入把变化关在边界外": { en: "Strategy and dependency injection lock change outside the boundary" },
    "绞杀者模式用增量迁移替代整体重写": { en: "The strangler pattern replaces wholesale rewrites with incremental migration" },
    "编译器与 JIT 把源码变成可执行行为": { en: "Compilers and JITs turn source code into executable behaviour" },
    "装饰器与中间件把横切关注点串成链": { en: "Decorators and middleware chain cross-cutting concerns together" },
    "观察者与事件解耦发布者与订阅者": { en: "Observers and events decouple publishers from subscribers" },
    "设计模式解决的是变化点的隔离，不是代码复用": { en: "Design patterns solve the isolation of variation points, not code reuse" },
    "购买与自建的决策框架：每条约束都摆上桌面": { en: "A build-vs-buy decision frame: putting every constraint on the table" },
    "适配器与防腐层隔离外部模型": { en: "Adapters and anti-corruption layers isolate external models" },
    "重构的安全边界由测试网和绞杀者模式共同划定": { en: "The safe boundary of refactoring is drawn jointly by test nets and the strangler pattern" },
    "错误处理是策略问题，异常只是运输手段": { en: "Error handling is a policy question; exceptions are just transport" },
    "错误处理的分类学：错误类型与恢复策略的映射": { en: "A taxonomy of error handling: mapping error types to recovery strategies" },
    "静态分析发现结构问题但不能证明行为正确": { en: "Static analysis finds structural problems but cannot prove behaviour correct" },
    "领域建模的实施路径：从事件风暴到聚合边界": { en: "A practical path for domain modelling: from event storming to aggregate boundaries" },
    "AI 做顶级 UI 设计：从创作到验证的完整回路": { en: "AI doing top-tier UI design: a complete loop from creation to verification" },
    "CI 流水线把反馈速度和发布证据连接起来": { en: "CI pipelines connect feedback speed with release evidence" },
    "发布门禁必须绑定真实证据": { en: "Release gates must bind to real evidence" },
    "可观测性断言：把运行时行为写进测试": { en: "Observability assertions: writing runtime behaviour into tests" },
    "接口约定测试的适用边界：消费者驱动与提供者验证": { en: "The applicable boundary of contract testing: consumer-driven and provider verification" },
    "测试替身按依赖行为而非名字分类": { en: "Test doubles are classified by dependent behaviour, not by name" },
    "测试策略从风险选择证据": { en: "Test strategy selects evidence from risk" },
    "混沌工程验证系统是否真的能处理故障": { en: "Chaos engineering verifies whether the system can really handle failures" },
    "灰度与功能开关的边界：交付节奏与配置漂移": { en: "The boundary of canary releases and feature flags: delivery cadence and configuration drift" },
    "覆盖率的三种读法：行分支与路径覆盖的证据强度": { en: "Three readings of coverage: the evidential strength of line, branch and path coverage" },
    "调试从假设到最小复现": { en: "Debugging goes from hypothesis to minimal reproduction" },
    "配置与特性开关分离部署与发布": { en: "Configuration and feature flags separate deployment from release" },
    "静态分析的证据边界：它证明什么不证明什么": { en: "The evidential boundary of static analysis: what it proves and what it does not" },
    "算法复杂度连接规模与资源成本": { en: "Algorithmic complexity links scale to resource cost" },
    /* 【rt27】原译 119 字符超出关系图两行容量（8.2px 底线 106），缩至 104 去掉 the visible impact 冗余包装，双要点保留。 */
    "CPU微架构与流水线：分支预测乱序执行对程序员的可见影响": { en: "CPU microarchitecture and pipelines: branch prediction and out-of-order execution for programmers" },
    "Go 并发以所有权、取消与错误传播为边界": { en: "Go concurrency is bounded by ownership, cancellation and error propagation" },
    "Python 并发先区分协程、线程、进程与解释器": { en: "Python concurrency starts by distinguishing coroutines, threads, processes and interpreters" },
    "Python 数据访问必须显式拥有连接与事务": { en: "Python data access must explicitly own connections and transactions" },
    "Spring 代理与 Bean 生命周期会改变调用边界": { en: "Spring proxies and bean lifecycles change invocation boundaries" },
    "TypeScript 类型边界与 Node 事件循环共同约束服务": { en: "TypeScript type boundaries and the Node event loop jointly constrain services" },
    "内存模型决定并发读写何时可见": { en: "Memory models decide when concurrent reads and writes become visible" },
    "跨语言并发模型必须同时比较抽象与运行机制": { en: "Cross-language concurrency models must compare abstraction and runtime mechanics together" },
    /* 【rt28·标题批 5/7】数据系统域 41 篇（域总览已于 rt24 领域批译出，
       本批插入其余 40 条）。方法论句式直译，保留冒号骨架。 */
    "LSM 树用写放大换取顺序写和可扩展性": { en: "LSM-trees trade write amplification for sequential writes and scalability" },
    "SQLite 与 MySQL 代表不同的并发与运维边界": { en: "SQLite and MySQL represent different concurrency and operations boundaries" },
    "SSD与HDD的IO特性差异：随机写与写放大": { en: "SSD versus HDD IO characteristics: random writes and write amplification" },
    "一致性哈希把再平衡的数据移动量压到平均槽位": { en: "Consistent hashing compresses rebalancing data movement to the average slot" },
    "事务边界应覆盖完整业务用例": { en: "Transaction boundaries should cover complete business use cases" },
    "事务隔离决定并发读写能观察到什么": { en: "Transaction isolation decides what concurrent reads and writes can observe" },
    "分库分表只在单库成为瓶颈后使用": { en: "Sharding is used only after a single database becomes the bottleneck" },
    "分片键设计以查询与均衡为双重约束": { en: "Shard key design is doubly constrained by queries and balance" },
    "复制滞后的一致性补救：读己之写与会话保证": { en: "Consistency remedies for replication lag: read-your-writes and session guarantees" },
    "存储引擎的两大路线：B树与LSM的写读取舍": { en: "The two routes of storage engines: the write-read trade-off between B-trees and LSM" },
    "崩溃一致性给文件系统补上POSIX未定义部分": { en: "Crash consistency fills in the parts POSIX leaves undefined for file systems" },
    "数据分布不均是分片集群的第一大故障源": { en: "Uneven data distribution is the top failure source of sharded clusters" },
    "读写三放大是存储引擎的中央权衡": { en: "The three amplifications—read, write, space—are the central trade-off of storage engines" },
    "非关系数据库按访问模式选择数据模型": { en: "Non-relational databases choose data models by access pattern" },
    "InnoDB 用日志连接事务、恢复与复制": { en: "InnoDB uses logs to connect transactions, recovery and replication" },
    "MySQL 空间、容量与在线运维": { en: "MySQL space, capacity and online operations" },
    "RAID等级与数据可靠性：镜像与纠删的数学": { en: "RAID levels and data reliability: the math of mirroring and erasure coding" },
    "分区再平衡的三种策略：固定取模与一致性哈希": { en: "Three rebalancing strategies for partitions: fixed modulo and consistent hashing" },
    "在线schema变更走expand与contract，不锁表是底线": { en: "Online schema changes go through expand and contract; no table locks are the floor" },
    "备份恢复是可验证的时间边界": { en: "Backup and restore is a verifiable time boundary" },
    "备份的价值由恢复演练来验证": { en: "The value of backups is verified by restore drills" },
    "复制的三种模式：主从、多主与无主的失败形态": { en: "Three replication modes: the failure shapes of leader-follower, multi-leader and leaderless" },
    "多活架构按冲突类型选择一致性策略，而不是按距离": { en: "Active-active architectures choose consistency strategies by conflict type, not by distance" },
    "数据库基准必须描述负载与资源边界": { en: "Database benchmarks must describe workload and resource boundaries" },
    "SQL 语义由关系、集合和窗口共同决定": { en: "SQL semantics are jointly decided by relations, sets and windows" },
    "关系模型用约束表达业务事实": { en: "The relational model expresses business facts through constraints" },
    "消失的数值：浮点格式与精度陷阱": { en: "Vanishing values: floating-point formats and precision traps" },
    "聚合边界由业务不变量而不是 ER 图决定": { en: "Aggregate boundaries are decided by business invariants, not ER diagrams" },
    "数据治理把质量责任放到写路径上": { en: "Data governance puts quality responsibility on the write path" },
    "数据质量与血缘让指标可以被解释": { en: "Data quality and lineage make metrics explainable" },
    "数据质量的三重校验：完整性时效与一致性": { en: "The triple check of data quality: completeness, timeliness and consistency" },
    "CDC 把数据库变化传播为可重放事实": { en: "CDC propagates database changes as replayable facts" },
    "批处理与流处理共享逻辑但不共享时间语义": { en: "Batch and stream processing share logic but not time semantics" },
    "数据编排要保证依赖、重试与幂等": { en: "Data orchestration must guarantee dependencies, retries and idempotency" },
    "物化视图把重复计算变成增量维护": { en: "Materialised views turn repeated computation into incremental maintenance" },
    "B+Tree 索引为访问路径服务": { en: "B+Tree indexes serve access paths" },
    "一条 SQL 如何穿过优化器与存储引擎": { en: "How a SQL statement travels through the optimiser and the storage engine" },
    "列存与向量化执行：OLAP引擎快的两个来源": { en: "Columnar storage and vectorised execution: the two sources of OLAP engine speed" },
    "列式存储把扫描与压缩交给分析路径": { en: "Columnar storage hands scanning and compression to the analytical path" },
    "慢查询治理从发现到索引闭环": { en: "Slow query governance: from discovery to index closure" },
    /* 【rt29·标题批 6/7】性能工程域 39 篇（域总览已于 rt24 领域批译出，
       本批插入其余 38 条）。方法论句式直译，保留冒号骨架。 */
    "CPU 性能来自有效执行与数据供给": { en: "CPU performance comes from effective execution and data supply" },
    "CPU 缓存与分支决定有效执行时间": { en: "CPU caches and branches decide effective execution time" },
    "ECC内存把单比特错误挡在报告之前": { en: "ECC memory stops single-bit errors before they reach reports" },
    "GPU 性能取决于计算、访存、并行与通信": { en: "GPU performance depends on compute, memory access, parallelism and communication" },
    "NUMA让跨槽访问付出带宽与延迟代价": { en: "NUMA makes cross-socket access pay in bandwidth and latency" },
    "SIMD与数据并行：一行代码的多个通道": { en: "SIMD and data parallelism: multiple lanes in one line of code" },
    "大页与TLB：地址翻译的隐藏成本": { en: "Huge pages and the TLB: the hidden cost of address translation" },
    "无锁数据结构的证据门槛：CAS与内存序": { en: "The evidence bar for lock-free structures: CAS and memory ordering" },
    "缓存行与伪共享：64字节里的并发性能": { en: "Cache lines and false sharing: concurrent performance inside 64 bytes" },
    "DNS解析是延迟与故障的隐形入口": { en: "DNS resolution is the hidden entry point of latency and failure" },
    "QUIC把传输握手与加密合流到用户态": { en: "QUIC merges transport handshake and encryption into userspace" },
    "RDMA绕过内核但要付出可运维性代价": { en: "RDMA bypasses the kernel but pays in operability" },
    "SSD的写放大来自介质要先擦后写": { en: "SSD write amplification comes from erase-before-write media" },
    "Socket 与 TCP 把连接可靠性分成多层": { en: "Sockets and TCP split connection reliability into layers" },
    "TIME_WAIT是连接收尾的代价与设计": { en: "TIME_WAIT is the cost and design of closing connections" },
    "TLS握手与证书链决定连接建立成本": { en: "TLS handshakes and certificate chains decide connection setup cost" },
    "cache分配策略与命中率：LFU与LRU的实证对比": { en: "Cache eviction policies and hit rates: LFU versus LRU, an empirical comparison" },
    "交付前的网络检查清单：二十项逐条过，三项全绿再上线": { en: "A pre-delivery network checklist" },
    "存储 I/O 性能取决于访问模式、队列与持久化语义": { en: "Storage IO performance depends on access pattern, queueing and persistence semantics" },
    "拥塞控制在吞吐与公平之间动态调节": { en: "Congestion control dynamically tunes between throughput and fairness" },
    "端到端网络延迟来自排队、协议、传输与处理": { en: "End-to-end network latency comes from queueing, protocols, transport and processing" },
    "cgroups把机器切成可调度的资源单元": { en: "cgroups slice the machine into schedulable resource units" },
    "io_uring与异步IO演进：系统调用省下的开销": { en: "io_uring and the evolution of async IO: the overhead saved from system calls" },
    "垃圾回收与内存分配决定延迟尾部": { en: "Garbage collection and memory allocation decide the latency tail" },
    "脏页回写在性能与崩溃丢失窗口间权衡": { en: "Dirty page writeback balances performance against the crash-loss window" },
    "虚拟内存与文件系统把地址和持久化分层": { en: "Virtual memory and file systems layer addresses and persistence" },
    "进程线程与系统调用构成执行边界": { en: "Processes, threads and system calls form the execution boundary" },
    "零拷贝把数据通路的CPU让给业务": { en: "Zero-copy hands the data path's CPU back to the business" },
    "tcpdump与抓包定位网络问题的现场方法": { en: "tcpdump and packet capture: the field method for locating network problems" },
    "优化收益递减决定何时该停手": { en: "Diminishing returns decide when optimisation should stop" },
    "基准测试必须先定义负载和测量误差": { en: "Benchmarks must first define workload and measurement error" },
    "市面Benchmark的设计读法：宏微与中间层基准": { en: "How to read mainstream benchmark designs: macro, micro and mid-level benchmarks" },
    "性能剖析与火焰图": { en: "Performance profiling and flame graphs" },
    "性能回归门禁：把性能预算写进CI": { en: "Performance regression gates: writing performance budgets into CI" },
    "性能问题定位方法": { en: "A method for locating performance problems" },
    "指标、日志、Trace与剖析各答一问，合起来才构成证据": { en: "Metrics, logs, traces and profiling each answer one question; together they form evidence" },
    "排队论给容量一个可推导的模型": { en: "Queueing theory gives capacity a derivable model" },
    /* 【rt30·标题批 7/7】知识库管理域 34 篇（域总览「知识库管理」
       已在前批译出，本批插其余 33 条）。占位符 {{date:YYYY-MM-DD}}
       原样保留；英文论文标题 EN 同值保键集完整。标题批至此收齐。 */
    "AI 系统内容缺口研究": { en: "AI systems content gap research" },
    "全库新鲜度审计": { en: "Whole-library freshness audit" },
    "全量编辑进度": { en: "Full editing progress" },
    "知识库变更日志": { en: "Knowledge base changelog" },
    "外部输入区": { en: "External input area" },
    "学习与迭代方法": { en: "Learning and iteration methods" },
    "学习工具使用与调用成本": { en: "Learning tool usage and invocation costs" },
    "待核验内容": { en: "Content pending verification" },
    "每日外部更新 {{date:YYYY-MM-DD}}": { en: "Daily external updates {{date:YYYY-MM-DD}}" },
    "AI 研发迭代框架案例证据": { en: "Evidence from AI R&D iteration framework cases" },
    "Agent 应用工程技术核验": { en: "Engineering verification of agent applications" },
    "Archify：可验证技术图谱生成器": { en: "Archify: a verifiable technical knowledge graph generator" },
    "DeepTutor：带检索、记忆与研究闭环的学习伴侣": { en: "DeepTutor: a learning companion with retrieval, memory and a research loop" },
    "Matt Skills：让 AI 先理解再修改": { en: "Matt Skills: let AI understand before it edits" },
    "OpenMAIC：多智能体互动课堂与可复用技能": { en: "OpenMAIC: multi-agent interactive classrooms and reusable skills" },
    "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks": { en: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" },
    "论文标题": { en: "Paper titles" },
    "项目或仓库名称": { en: "Project or repository names" },
    "来源与证据说明": { en: "Sources and evidence notes" },
    "外部来源注册表": { en: "External source registry" },
    "知识体系缺口审计": { en: "Knowledge system gap audit" },
    "知识库范围与结构": { en: "Knowledge base scope and structure" },
    "知识更新方法论": { en: "Knowledge update methodology" },
    "知识演化机制": { en: "Knowledge evolution mechanisms" },
    "知识点写作与教学输出规范": { en: "The writing and teaching conventions for knowledge points" },
    "知识质量标准": { en: "Knowledge quality standards" },
    "面向发布的知识写作文风规范": { en: "The publication-facing style conventions for knowledge writing" },
    "项目方法反哺机制": { en: "The project-to-method feedback loop" },
    "一篇知识怎么写": { en: "How to write one piece of knowledge" },
    "知识从哪来，怎么更新": { en: "Where knowledge comes from, and how it updates" },
    "知识完善度怎么判断——四象限与九个信号": { en: "How to judge knowledge completeness: four quadrants and nine signals" },
    "知识缺口怎么补——图谱关系槽与补强工作流": { en: "How to fill knowledge gaps: graph relation slots and reinforcement workflows" },
    "论文怎么追踪、怎么解析": { en: "How to track and parse papers" },
    "系统指标、结构化事件与观测方法": { en: "System metrics, structured events and observation methods" },
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
    /* 【rt24】用户明确要求：EN 态侧栏领域名要翻译（此前按"用户数据不译"
       约定保留中文，用户推翻了这条——领域名是导航结构的一部分，读者
       必须能读懂才能导航）。七个领域名手工精译，冒号副题是领域定位
       句，按导航语气译。 */
    "AI 系统工程：从模型能力到生产能力": { en: "AI systems: from model capability to production" },
    "缺陷分析：从个案到体系": { en: "Defect analysis: from incidents to systems" },
    "后端系统：在并发、失败与变化中维持服务": { en: "Backend systems: serving through concurrency, failure and change" },
    "软件构建：让变化可以理解、验证与交付": { en: "Software construction: making change understandable, verifiable, deliverable" },
    "数据系统：在并发与故障中保存事实": { en: "Data systems: keeping facts alive through concurrency and faults" },
    "性能工程：从用户等待到资源瓶颈": { en: "Performance engineering: from user latency to resource bottlenecks" },
    // 【反复迭代后结果·rt13】首页辅助理解区新增「知识库管理」卡的正文与链接翻译。
    // 依据：领域卡迁移到辅助理解区后 EN 态只有标题被词典命中，正文/链接裸奔中文。
    "维护本站的元文档：怎么写、怎么判断完善度、缺口怎么补、论文怎么追踪、来源怎么更新": { en: "Meta docs for running this site: how notes are written, how completeness is judged, how gaps are filled, how papers are tracked, how sources are refreshed" },
    "打开元文档": { en: "Open the meta docs" },
    /* 总览=panorama 视图的维度标签（panorama-view.js），知识全景=导航项名。
       两者在 EN 态都用 Panorama 会撞车（审计报碰撞）；总览回退 Overview，
       概览已另译 Section overview，无冲突。 */
    "总览": { en: "Overview" },
    /* 【2026-09-22 孤儿清理】「条来源」「已部署」全站零消费
       （apps/ 与 site/ 排除 .bak 后 grep 无命中），删除。 */

    // ── Cards and status ──
    "已安装": { en: "Installed" },
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
    "服务运行中": { en: "Service up" },
    "未启动": { en: "Not running" },
    "配置不完整": { en: "Incomplete setup" },
    "查看": { en: "View" },
    "打开": { en: "Open" },
    "完整使用指南": { en: "Full guide" },
    "实现与边界": { en: "How it works, and its limits" },
    "中文说明": { en: "Chinese README" },
    "查看写作规范": { en: "Writing conventions" },
    "查看评估原型": { en: "Open the prototype" },
    "创建课堂": { en: "Create a classroom" },
    "进入学习导师": { en: "Open the tutor" },
    "打开学习中心": { en: "Open Learning" },
    "查看项目与教学": { en: "See projects and learning" },
    "查看知识图谱": { en: "See the knowledge graph" },
    "打开课堂历史": { en: "Open class history" },
    "打开项目入口": { en: "Open the projects page" },
    "查看收录方式": { en: "See how they are collected" },
    "先看使用说明": { en: "Read the guide first" },
    "为什么不能只信 Agent 的总结": { en: "Why an agent's summary is not evidence" },
    "为什么不能只信Agent的总结": { en: "Why an agent's summary is not proof" },

    // ── Progress view (added 2026-09-21: i18n_audit reported them missing) ──
    "标记已学": { en: "Mark learned" },
    "✓ 标记已学": { en: "✓ Mark learned" },
    "✓ 已读": { en: "✓ Learned" },
    "标记已读": { en: "Mark mastered" },
    "输入即筛选 · 回车搜索": { en: "Type to filter · Enter to search" },
    "标记这篇为已读（只保存在本浏览器）": { en: "Mark this note as learned (this browser only)" },
    "未读": { en: "Not yet" },
    "我的阅读": { en: "Progress" },
    "导出": { en: "Export" },
    "导入": { en: "Import" },
    "把标注下载成 JSON 文件": { en: "Download your annotations as a JSON file" },
    "从 JSON 文件导入标注": { en: "Import annotations from a JSON file" },
    "清除全部标注": { en: "Clear all annotations" },
    "稍后读": { en: "Later" },
    "稍后读，点击取消": { en: "On the read-later list; click to remove" },
    "加入稍后读": { en: "Add to the read-later list" },
    "知识全景": { en: "Panorama" },
    "覆盖矩阵": { en: "Cover matrix" },
    "八层技术栈": { en: "8-layer stack" },
    "视角": { en: "Views" },
    "查看 Agent 评估原型": { en: "See the agent-evaluation prototype" },
    "两个正交维度看覆盖面：空格子就是漏掉的方向": {
      en: "Coverage on two axes: an empty cell is a missing direction",
    },
    "标记已读、排稍后读——只保存在这台浏览器上，不会上传": {
      en: "Mark notes learned or for later — kept in this browser, never uploaded",
    },
    "{n} 篇已读 · {p}%": { en: "{n} learned · {p}%" },

    // ── Home, wave 2 (added 2026-09-21): strings the static audit cannot see,
    //    because renderHome / renderDigest / renderAtlas / enhanceDomains /
    //    applyHomeStatus / shell.js build them in JS. translateDOM picks them
    //    up via retranslate(); template-literal strings still need t_(). ──
    "近七天优质好文": { en: "Good reads, last seven days" },
    "BestBlogs 人工精审 · 评分排序": { en: "BestBlogs human-reviewed · ranked by score" },
    "早报暂时更新失败，以下为最近一次成功抓取的存量 · ": {
      en: "The brief failed to update; below is the last good fetch · ",
    },
    "往前": { en: "Scroll back" },
    "往后": { en: "Scroll forward" },
    "全部来源": { en: "All sources" },
    "今日早报": { en: "Today's brief" },
    "评分": { en: "score" },
    "知识地形": { en: "The shape of the library" },
    "打开完整图谱": { en: "Open the full graph" },
    "知识领域分布图": { en: "Domain map of the knowledge base" },
    "篇已归入领域的笔记按主题分布。圆越大，主题下的笔记越多。归档来源与剪藏不计入": {
      en: "Topic spread of the notes filed under domains. A bigger dot means more notes. Archived sources and clippings don't count.",
    },
    "按技术本身归类，不按课程或时间排。Agent 相关的内容归在 AI 系统工程下，和上下文、检索、质量放在一起": {
      en: "Grouped by the technology itself, not by course or date. Agent material sits under AI systems engineering, next to context, retrieval and quality",
    },
    "模型、训练、上下文、RAG、Agent、推理服务、平台、安全与评测": {
      en: "Models, training, context, RAG, agents, inference serving, platforms, security and evaluation",
    },
    "请求、并发、消息、复制、一致性、故障恢复和基础设施": {
      en: "Requests, concurrency, messaging, replication, consistency, recovery and infrastructure",
    },
    "从真实上游缺陷学判断、复现、合入与回归，每条案例都有上游 commit 可查": {
      en: "Judgement, reproduction, merges and regressions learned from real upstream defects; every case cites an upstream commit",
    },
    "建模、SQL、事务、索引、CDC、流处理、治理和恢复": {
      en: "Modelling, SQL, transactions, indexing, CDC, streaming, governance and recovery",
    },
    "进程、CPU、GPU、内存、I/O、网络、观测和容量": {
      en: "Processes, CPU, GPU, memory, I/O, networking, observability and capacity",
    },
    "架构、语言运行时、依赖、测试、CI/CD、发布和调试": {
      en: "Architecture, language runtimes, dependencies, testing, CI/CD, releases and debugging",
    },
    "怎么写、怎么判断完善度、缺口怎么补、论文怎么追踪、来源怎么更新": {
      en: "How to write, how to judge completeness, how to fill gaps, how papers are tracked, how sources are refreshed",
    },
    "从 学习中心 选择预置路径，或直接进入课堂和导师。主题会预填，确认后才调用模型": {
      en: "Pick a preset path in the Learning centre, or go straight to a classroom or a tutor. Topics arrive pre-filled; the model is called only after you confirm",
    },
    "互动课堂与项目式学习": { en: "Interactive classes and project-based learning" },
    "资料研究、问答与掌握路径": { en: "Document research, Q&A and mastery paths" },
    "已部署 · 本机 3100": { en: "Deployed · local port 3100" },
    "2 个老师": { en: "2 tutors" },
    "已部署 · 本机 3782": { en: "Deployed · local port 3782" },
    "2026-09-17 核验": { en: "Verified 2026-09-17" },
    "一个要掌握的工程问题、学习目标或参考材料": { en: "An engineering problem to master, a learning goal, or reference material" },
    "把目标拆成讲解、互动、测验、模拟、代码练习或 PBL 任务": { en: "Breaks the goal into explainers, interactions, quizzes, simulations, code drills or PBL tasks" },
    "可操作课堂、即时反馈，以及改变约束后的迁移任务": { en: "A working classroom, live feedback, and transfer tasks with changed constraints" },
    "文档、知识库、问题、代码仓库或已有笔记": { en: "Documents, a knowledge base, a question, a repo, or existing notes" },
    "按目标路由到 Chat、Research、Solve、Visualize 或 Mastery Path，并复用来源与记忆": {
      en: "Routes by goal to Chat, Research, Solve, Visualize or Mastery Path, reusing sources and memory",
    },
    "带来源回答、研究报告、笔记、问题集和可持续复习路径": { en: "Sourced answers, research reports, notes, problem sets and a lasting review path" },
    /* 【rt22】原键带句号导致精确匹配失败（DOM 文本无句号），英文态
       残留中文。键去句号对齐页面。 */
    "评估原型回答\"到底有没有变好\"，把 Agent 的判断绑定到证据；开源的工程流程提供能直接照做的做法": {
      en: "The evaluation prototype answers \"did it actually get better\" and binds agent judgement to evidence; the open-source workflows give practices you can copy directly",
    },
    "任务、Trace、证据与回归": { en: "Tasks, traces, evidence and regression" },
    "原型期": { en: "Prototype" },
    "任务目标、仓库版本、权限、预算和真实执行记录": { en: "A task goal, repo revision, permissions, budget and real execution records" },
    // 【反复迭代后结果·rt13】key 随产出行文案重写同步更新（旧 key「把 Agent 的判断绑定到…」已无引用）。
"带证据链的评估结论与回归清单；当前是设计约定与静态原型": { en: "Evaluation conclusions with evidence chains and regression checklists; currently a design convention and a static prototype" },
    "设计约定": { en: "Design conventions" },
    "工程任务的可复用 Agent 流程": { en: "Reusable agent workflows for engineering tasks" },
    "需求、设计文档、代码库与失败反馈": { en: "Requirements, design docs, a codebase and failure feedback" },
    "边界清楚的实现、测试证据和可进入下一轮的反馈": { en: "A scoped implementation, test evidence and feedback ready for the next round" },
    "查看 Skills": { en: "See the skills" },
    "架构图和源码用来查清一个东西和其它东西的关系：它依赖什么、被谁依赖。需要的时候打开，不需要就跳过": {
      en: "Architecture graphs and source are for pinning down what depends on what. Open them when needed, skip them when not",
    },
    "Archify · 可验证架构图": { en: "Archify · verifiable architecture graphs" },
    "把系统描述或仓库证据变成类型化图，再经确定性校验生成可交互 HTML/SVG；用于需要精确校验的架构图": {
      en: "Turns a system description or repo evidence into a typed graph, then deterministic validation into interactive HTML/SVG; for graphs that must verify",
    },
    "Archify 方法": { en: "The Archify method" },
    "项目与融合记录": { en: "Projects and how they folded in" },
    "查看四个上游项目的源码位置、说明、当前状态和进入知识库的方法": {
      en: "Where each upstream project lives, what it is, its current state, and how it entered the library",
    },
    "课堂历史": { en: "Class history" },
    "生成的课堂先在 OpenMAIC 中继续；复核后再整理进 Markdown 知识": {
      en: "Generated classes continue in OpenMAIC; once reviewed they are folded into the Markdown notes",
    },
    /* 2026-09-22 箭头收编：原「打开项目入口 →」「打开课堂历史 →」「查看收录方式 →」
       三个带箭头 key 已删（箭头改由 CSS .wa-open::after 渲染，两种语言不再各写
       一遍箭头）。无箭头 key 的英文译文沿用按钮语境（Open the projects page /
       Open class history / See how they are collected），不再用旧译 Projects /
       Classroom history / How notes get filed——那是栏目标题语气，放在按钮上
       不像动作指令。链接指向本站 /launch/openmaic，非外站，不用 ↗。 */

    /* 【rt22】notice 文案曾在页面改版时更新，词典键还停留在旧句，
       英文态残留中文。键对齐现行 DOM 文本。 */
    "先看懂一个领域，从知识领域卡片进入；想动手练，用学习工具；想知道系统到底有没有变好，看 Agent 评估": {
      en: "To understand a field first, enter from the domain cards; to practise, use the learning tools; to know whether the system actually got better, check the Agent evaluation",
    },
    "显示设置": { en: "Display settings" },
    /* 【rt23】侧边栏导航 title（悬浮提示）此前无词条，EN 态全裸奔
       中文（translateDOM 的 ATTRS 机制只会翻词典里有的键）。
       来源：shell.js 导航渲染。五条一次补齐。 */
    "按技术对象阅读知识": { en: "Browse knowledge by technical object" },
    "看知识之间怎么连": { en: "See how knowledge connects" },
    "两个正交维度看覆盖面": { en: "Coverage across two orthogonal axes" },
    "进入学习与工程工具": { en: "Open learning and engineering tools" },
    "把判断绑定到证据": { en: "Bind judgement to evidence" },
    "切换语言": { en: "Switch language" },
    "收起目录": { en: "Collapse the contents" },
    "BestBlogs 今日早报": { en: "BestBlogs today's brief" },
    "点域名、主题圆或笔记圆点，": { en: "Click a domain, topic circle or note dot" },
    "点主题名查看该主题下的全部笔记": { en: "Tap a topic to see all its notes" },
    /* 译文头部空格（勿删）：本 key 与上一 key 在 renderGraph 里是相邻两个
     * span，HTML 模板不留空格（中文靠「，」分隔）。英文两段尾/首都无标点，
     * 无此空格会拼成「dotto」。空格放译文而非模板：中文模式下 inline 的
     * 尾随空格会被行内盒折叠规则吞掉，无副作用。放在词条外是因为
     * i18n_dict_audit 的 ENTRY 正则要求「key: {」后直接跟 en:。 */
    "只看与它相关的连线；再点一次或按 Esc 取消，双击笔记进原文": {
      en: " to keep only its edges; click again or Esc to clear. Double-click a note to open it",
    },
    "实现借鉴 d3 link 曲线、Obsidian 局部图谱与 Cosmograph 的聚焦方式：按领域分列，曲线表达跨域引用，聚焦时点亮相关路径": {
      en: "Borrowed from d3 link curves, Obsidian's local graph and Cosmograph's focus: domains in columns, curves for cross-domain citations, focus lighting the related paths",
    },
    "知识类型 →": { en: "Kinds →" },
    "↓ 系统层次": { en: "↓ Layers" },
    "合计": { en: "Total" },
    "空": { en: "dot" },
    "漏掉的方向": { en: "Missing directions" },
    "没有空格子": { en: "No empty cells" },
    "层次靠关键词推断": { en: "layer inferred by keyword" },
    "收藏 ${favCount} 篇常驻 · 七天 Top 20": { en: "${favCount} favorites pinned · Top 20 of the week" },
    "字数": { en: "Word count" },

    // ── Reader relations & graph extras (wave 2) ──
    "条入链 · ": { en: " incoming · " },
    "条延伸": { en: " outgoing" },
    "引用当前节点": { en: "Cites this note" },
    "从当前节点延伸": { en: "Extends from this note" },
    "展开知识图谱": { en: "Expand the graph" },
    "折叠知识图谱": { en: "Collapse the graph" },
    /* 【rt24】雷达卡（时效内容置顶卡）的 UI 串。卡片标题本身是笔记数据
       （title），但"每周更新"是固定标签。 */
    "每周更新": { en: "Updated weekly" },
    "的直接知识图谱": { en: " — immediate knowledge graph" },
    "同模块": { en: "Same module" },
    "篇）·": { en: "in the graph)" },
    "篇 ·": { en: " notes · " },
    /* 英文端必须能区分：这里带篇数语义，下面的裸箭头是通用方向符号。
       两者都译 "→" 时反查无法判断该还原成哪个中文源（i18n-dict 检查项）。 */
    "篇 →": { en: " notes →" },
    "→": { en: "→" },
    "个主题": { en: "topics" },
    "已聚焦域：": { en: "Focused domain: " },
    "已聚焦笔记：": { en: "Focused note: " },
    "已聚焦主题：": { en: "Focused topic: " },
    "点空白或 Esc 取消 · 双击笔记圆点进原文": { en: "click empty space or Esc to clear · double-click a note dot to open it" },
    "滚轮缩放 · 拖拽平移 · 点域、主题或笔记聚焦": {
      en: "Scroll to zoom · drag to pan · click a domain, topic or note to focus",
    },
    "圆越大，主题下的笔记越多": { en: "A bigger circle means more notes under the topic" },
    "已读环": { en: "topic mastery ring" },
    "在知识图谱中聚焦 ": { en: "Focus in the graph: " },
    "图谱聚焦 →": { en: "Focus in graph →" },
    "，点按聚焦该域": { en: " — click to focus this domain" },

    // ── Directory / search / loading states (wave 2) ──
    "篇 · 主题按知识对象归属": { en: " notes · topics grouped by what they are about" },
    "按标题": { en: "By title" },
    "按更新": { en: "By updated" },
    "搜索结果": { en: "Search results" },
    "全部知识": { en: "All notes" },
    "没有找到": { en: "Nothing found for" },
    "试试更短的关键词（如 “RAG”“缓存”），或按 <kbd>Esc</kbd> 清空搜索回到全部知识": {
      en: "Try a shorter keyword (like “RAG” or “cache”), or press <kbd>Esc</kbd> to clear the search",
    },
    "清除「": { en: "Clear the “" },
    "」筛选": { en: "” filter" },
    "打开笔记": { en: "Open note" },
    "入口": { en: "Entry" },
    "主题按知识对象归属": { en: "Topics grouped by what they are about" },

    // ── Progress view dynamic strings (wave 2) ──
    "已读，点击取消": { en: "Learned — click to undo" },
    "标记为已读": { en: "Mark as learned" },
    "最近读完": { en: "Recently learned" },
    "下一步": { en: "Next up" },
    "这个过滤条件下没有文章": { en: "No notes under this filter" },
    " / ": { en: " / " },
    "已读 · ": { en: "learned · " },
    "稍后读 ": { en: "later " },
    "清除全部阅读标注？这会重置这台浏览器上的所有进度。": {
      en: "Clear every learned mark? This resets all progress on this browser",
    },
    "导入失败：文件不是有效的进度 JSON": { en: "Import failed: not a valid progress JSON file" },
    "先打开一篇文章再下载": { en: "Open a note first, then download" },
    "先打开一篇文章再复制": { en: "Open a note first, then copy" },
    "已开始下载 Markdown 原文": { en: "Markdown download started" },
    "下载失败，请稍后重试": { en: "Download failed, please try again later" },
    "链接已复制": { en: "Link copied" },
    "图表渲染失败，但正文仍然可读": { en: "A diagram failed to render, the text still reads fine" },
    "这篇笔记暂时无法打开，请稍后重试": { en: "This note can't be opened right now, try again shortly" },
    "请求失败": { en: "Request failed" },
    "学习工具状态暂时不可用，入口仍然可以打开": { en: "Learning tools' status is unavailable, the entries still open" },

    // ── Home hero-meta & counts (wave 2, variable strings via t_) ──
    "工程知识，每条讲清一个机制怎么运作、代价在哪": { en: "​" },
    "个": { en: " " },
    "全部 N 篇": { en: "All ({n})" },
    "全部 X 篇": { en: "All ({x})" },
    "还有 ": { en: "+ " },
    "收起": { en: "Show fewer" },
    "收藏 ": { en: "␣" },
    "篇常驻 · 七天 Top 20": { en: "favorites pinned · Top 20 of the week" },
    " 字": { en: " chars" },
    "约 ": { en: "about " },
    " 分钟": { en: " min" },

    // ── Panorama dynamic strings (wave 2) ──
    "当前矩阵只统计「": { en: "The matrix now counts only " },
    "」域的文章，点侧栏「总览」或域名可切换": { en: " — switch domains from the sidebar" },
    "等待笔记数据…": { en: "Waiting for notes…" },
    "的文章不进技术矩阵（元知识与剪藏被排除），换个域试试": {
      en: " notes don't enter the technical matrix (meta-knowledge and clippings are excluded). Try another domain.",
    },
    "每行是一个<b>系统层次</b>（问题出在哪一层），每列是一种<b>知识类型</b>（这一层我懂的是哪种知识）": {
      en: "Each <b>row</b> is a system layer (where the problem lives), each <b>column</b> is a kind of knowledge (which kind you hold at that layer)",
    },
    "两轴正交，<b>空格子才是真的漏</b>：一维只说得出哪一类少，说不出哪个方向空": {
      en: "The two axes are orthogonal, so <b>an empty cell is a real gap</b>: one axis only says a kind is thin, never which direction is empty",
    },
    "当前域：": { en: "Current domain: " },
    "篇入矩阵，点格子看文章": { en: " in the matrix. Click a cell to see the notes" },
    "列 · 知识类型": { en: "Columns: kinds" },
    "行 · 系统层次": { en: "Rows: layers" },
    "整行 · ": { en: "Whole row: " },
    "整列 · ": { en: "Whole column: " },
    " 篇 · 这一层上全部类型的文章": { en: " notes · every kind of note at this layer" },
    " 篇 · 所有层里这一类知识的文章": { en: " notes · every layer holding this kind" },
    "分类依据：frontmatter 的 tags 与 type（244/245 篇有标签）。层次靠关键词推断的有 ": {
      en: "Classified by frontmatter tags and type (244 of 245 tagged). Layer inferred by keyword: ",
    },
    " 篇，在文章列表里标出，这些格子的数字请当参考": { en: " notes, flagged in the lists — treat those cells as indicative" },
    "知识内容加载较慢，仍在重试…": { en: "Loading is slow, still trying…" },
    "知识内容暂时读不到": { en: "Can't read the knowledge content right now" },
    "本机服务可能正在重启。稍等几秒后重试，或检查站点是否在运行": {
      en: "The local server may be restarting. Retry in a few seconds, or check that the site is running",
    },
    "重新加载": { en: "Reload" },
    "正在读取知识库…": { en: "Reading the library…" },

    // ── Projects page ──
    "项目与教学入口": { en: "Projects and learning" },
    "这里解决什么问题": { en: "What this page is for" },
    "访问方式": { en: "How to get in" },
    "怎么用": { en: "How to use it" },
    "学习产品": { en: "Learning products" },
    "工程方法与辅助可视化": { en: "Engineering methods and visualisation" },
    "已经融合到知识库": { en: "Already folded into the knowledge base" },
    "从主题到能力": { en: "From topic to capability" },
    "Agent 评估独立维护": { en: "Agent evaluation is maintained separately" },
    "方法如何反哺": { en: "How the methods feed back" },
    "知识点的教学输出": { en: "Teaching output per note" },
    "任务与项目理解": { en: "Task and project understanding" },
    "轨迹与事实证据": { en: "Trace and evidence" },
    "待开发：改进与回归": { en: "Not built yet: improvement and regression" },
    "互动课堂": { en: "Interactive classroom" },
    "学习导师": { en: "Study tutor" },
    "什么会花掉额度": { en: "What costs model quota" },
    "在别的设备上打开": { en: "Opening it on another device" },
    "从本页点「进入学习导师」，会直接进对话界面": {
      en: "Use “Open the tutor” above; it goes straight to the chat",
    },
    /* 2026-09-22 i18n 修复：projects 页文案带句号（627/635 行），补带句号版本词条（双词条策略）。 */
    "读知识不需要密码，用工具才需要": { en: "Reading needs no password; tools do" },
    "读知识不需要密码，用工具才需要。": { en: "Reading needs no password; tools do." },
    "学习产品优先，工程方法其次，可视化是辅助。跨项目仍成立的方法会进入对应知识主题；Agent 评估独立维护": {
      en: "Learning tools first, engineering methods second, visualisation as an aid. Methods that hold across projects go into the knowledge base; agent evaluation stays separate",
    },
    "这里放我已经装好的学习工具，以及它们的源码和说明。想看哪个点哪个，不用记端口和路径": {
      en: "The learning tools installed here, with their source and docs. Click through instead of remembering ports",
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
    "用课堂、追问、练习和迁移检验是否真的会用": {
      en: "Classrooms, questioning, practice and transfer, to check you can actually use it",
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
    "按时间倒序。标记会立刻写回本机日志，刷新后保留": {
      en: "Newest first. Marking a row writes straight back to the local log",
    },
    "共": { en: "​ " },
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
    "本机访问记录与读者反馈，只在这台机器上可见": {
      en: "Local visit log and reader feedback — visible on this machine only",
    },
    /* 【rt21】insights 页 EN 态清零专项：hero 副题此前被 <code>data/</code>
       标签切成多个文本节点（"…数据只存在本机"/" 目录，不进版本库…"
       /" 其他设备…"），translateDOM 按节点逐个翻译，只有第一段有词条
       → 改源码为单行整句（HTML 折叠空白，视觉不变）。动态表格/卡片/
       空态由 JS 渲染（translateDOM 不重跑），已接 tr()，词条补齐。 */
    "谁读过这个知识库、读了什么、提了什么意见。数据只存在本机": {
      en: "Who has read this knowledge base, what they read, and what they said. The data lives only in this machine's ",
    },
    "目录，不进版本库、不外发。这一页也只对本机开放 —— 其他设备即使有站点密码也读不到。": {
      en: " directory; it never enters version control and never leaves. This page is local-only too — other devices cannot read it even with the site password.",
    },
    "访问量按 IP 去重：同一台设备换网络会被算成两个人，局域网 NAT 后的多台设备可能共用一个 IP。它是用来发现「哪些内容有人在看、哪些反馈还没处理」的信号，不是精确的用户统计。": {
      en: "Visits are de-duplicated by IP: one device switching networks counts as two people, while several devices behind a LAN NAT may share one IP. Treat it as a signal for “which content gets read and which feedback is still open”, not precise user analytics.",
    },
    "名字来自本人填写，或本机 git 配置；不做身份校验": {
      en: "Names come from what visitors typed in or the local git config; no identity check",
    },
    "还没有反馈": { en: "No feedback yet" },
    "知识库里的悬浮按钮可以让读者随手提意见": {
      en: "The floating button in the knowledge base lets readers drop feedback as they read",
    },
    "建议": { en: "Suggestion" },
    "有用": { en: "Helpful" },
    "局域网": { en: "LAN" },
    "未知": { en: "unknown" },
    "天前": { en: "d ago" },
    "个月前": { en: "mo ago" },
    "个来源": { en: "sources" },
    "还没有访问记录。": { en: "No visits recorded yet." },
    "读不到中台数据：": { en: "Cannot read the insights data: " },
    "确认站点服务在运行，然后刷新": {
      en: "Make sure the site service is running, then refresh",
    },
    "来源": { en: "Origin" },
    "环境": { en: "Client" },
    "访问": { en: "Visits" },
    "页面": { en: "Pages" },
    "首次": { en: "First" },
    "最近": { en: "Last" },
    "阅读": { en: "Reads" },

    // ── Feedback dialog (rendered by shell.js) ──
    "发送失败": { en: "Could not send" },
    "提意见 / 报告问题": { en: "Feedback and problems" },
    "提个意见": { en: "Send feedback" },
    "提意见": { en: "Feedback" },
    "这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机": {
      en: "Say what is wrong, unclear or missing on this page. Feedback stays on this machine",
    },
    "反馈类型": { en: "Feedback type" },
    /* 【rt23】反馈面板 placeholder 两条此前无词条：ATTRS 机制只翻词典
       有的键，overlay 渲染后调 translateDOM(overlay) 时机是对的，
       缺的是这两条键本身（反馈面板 shell.js 全站注入，所有页面受益）。 */
    "例如：这一页的链接点不开；或者：希望补一张流程图": { en: "For example: a link on this page is broken; or: wish there were a flow chart" },
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
    "把主题练成能力": { en: "Turn a topic into a skill" },
    "收到，谢谢反馈！": { en: "Got it, thanks." },
    "请先写点内容。": { en: "Write something first" },

    // ── Papers page ──
    "时间线": { en: "Timeline" },
    "正在读取…": { en: "Loading…" },
    "优质好文": { en: "Good reads" },
    // 首页那两栏的标题。词典按整串匹配，新短语要各自列一条，
    // 否则英文界面下会原样显示中文。
    "不用读完论文，也知道它值不值得读": { en: "Whether a paper is worth reading, without the read" },
    "每篇讲清三件事：": { en: "Three things, on every one:" },
    // 首页那块横滑区的标题。词典是整串匹配的，所以要单独列一条 ——
    // 只写「优质好文」的话，「每日优质好文」整串查不到，英文界面下会
    // 原样显示中文。
    "近三天优质好文": { en: "Good reads, last three days" },
    "BestBlogs 早报，滚动三天": { en: "BestBlogs' brief, rolling three days" },
    "配好 BestBlogs 的 API Key 后，这里会列出它最近三天的早报": {
      en: "Once BestBlogs' API key is configured, its briefs for the last three days appear here",
    },
    "资源目录": { en: "Source index" },
    "追踪新论文": { en: "Tracking new papers" },
    "收藏夹": { en: "Favorites" },
    "取消收藏": { en: "Remove from favorites" },
    "收藏": { en: "Favorite" },
    "收藏夹满了": { en: "Favorites full" },
    "先留着": { en: "Keep it" },
    "确认取消": { en: "Remove" },
    "好的": { en: "Got it" },
    "这篇文章": { en: "this article" },
    "收藏上限是 100 篇。它是一座精选的书架，不是仓库——先取消一些不常读的，再把它放进来": { en: "The shelf holds 100 favorites. It is a curated bookshelf, not a warehouse — remove a few you no longer read, then add this one" },
    "收藏没有保存成功，请稍后再试。": { en: "Saving the favorite failed. Please try again later." },
    "收藏于": { en: "Favorited" },
    "追踪新论文和解析": { en: "New papers, with write-ups" },
    "按时间倒序。每篇给出它解决的问题、做法，以及论文自己报出的数字——摘要里没写的就留空。2024 年前的收在「历史奠基」里": {
      en: "Newest first. Each entry gives the problem, the approach, and the numbers the paper itself reports — anything the abstract leaves out stays blank. Papers before 2024 sit under Foundations",
    },
    "论文追踪": { en: "Paper Tracking" },
    "追踪新论文，逐篇给出结构化解析；知识库的结论从这里取材": { en: "New papers are tracked and analysed here, one by one. The knowledge base draws its evidence from them" },
    "最新论文怎么解析、怎么进知识库": { en: "How new papers are read and fed into the knowledge base" },
    "自己追踪的新论文，逐篇结构化解析，并回流到知识库": { en: "New papers tracked here, analysed one by one, and folded back into the knowledge base" },
    "2023 及更早 · 历史奠基": { en: "2023 and earlier · Foundations" },
    "搜「标题 / 作者 / arXiv 编号」都没命中。试试论文标题里的一个词，或者 4 位年份": { en: "No match on title, author or arXiv id. Try one distinctive word from the title, or a 4-digit year" },
    "这些论文是怎么挑出来、怎么解析的": { en: "How these papers are found and analysed" },
    "追踪管道、四道验证防线、L1/L2 分级解析的标准写在方法页里 —— 这个页面上每一条规则都能在那里找到出处": { en: "The tracking pipeline, the four verification gates and the L1/L2 analysis standard are written up in the method page — every rule on this page traces back to it" },
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
    "上面是 L1，来自论文自己的摘要。深度解读（L2）要把全文读完才能写：摘要里没有消融实验、超参设置、失败案例和复现步骤，靠摘要拼出来的解读每一句都可能是错的": { en: "The fields above are L1, taken from the paper's own abstract. A deep read (L2) needs the full paper: an abstract does not contain ablations, hyperparameters, failure cases or reproduction steps, so a deep read assembled from it would be wrong in ways a reader cannot detect." },
    "按追踪方法论的 L2 规范，需要补这八个模块：": { en: "The L2 standard requires these eight modules:" },
    "背景与问题": { en: "Background and problem" },
    "核心方法": { en: "Core method" },
    "技术细节": { en: "Technical detail" },
    "实验与结果": { en: "Experiments and results" },
    "亮点与洞察": { en: "Strengths and insights" },
    "局限性": { en: "Limitations" },
    "复现指南": { en: "Reproduction guide" },
    "相关工作与启发": { en: "Related work and what it suggests" },
    "写好之后放进": { en: "Write it into" },
    "，页面会自动显示。": { en: " and this page picks it up automatically" },
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
    "没有匹配的论文。": { en: "No paper matches" },
    /* 2026-09-22 i18n 修复补录：papers 页 renderPin 的方法链接文案，
       渲染处已套 tr() 但词表缺条目，英文态残留中文。 */
    "筛选与解析方法": { en: "How papers are picked and read" },
    "读不到论文注册表。运行 python3 scripts/fetch-papers.py 生成后再刷新": { en: "Cannot read the paper registry. Run python3 scripts/fetch-papers.py, then reload" },
    "篇": { en: "papers" },
    "条结论有论文支撑": { en: "conclusions backed by a paper" },

    // ── Sources page ──
    // 卡片本身的 name/kind/gain/tags 不走词典 —— 它们来自 site/sources.js，
    // 按当前语言直接取（那一份数据里自带 en 字段）。这里只放页面骨架上的文案。
    "外部资源": { en: "Sources" },
    "外部有哪些做得更好的站": { en: "Sites that do this better" },
    "文章": { en: "Writing" },
    "成篇的文章，适合慢慢读": { en: "Finished pieces, for slow reading" },
    "论文": { en: "Papers" },
    "一手研究。比二手解读可信，也更需要筛选": {
      en: "Primary research. More trustworthy than a second-hand read, and in more need of filtering",
    },
    "资讯": { en: "News" },
    "知道发生了什么。用来看动向，不当知识读": {
      en: "Knowing what happened. For tracking the field, not as knowledge",
    },
    "资源清单读不到": { en: "Cannot read the source list" },
    "检查 site/sources.js 是否加载成功，然后刷新": {
      en: "Check that site/sources.js loaded, then reload",
    },
    // 卡片里带回来的外部内容（标题、摘要）**不进词典** —— 那些是内容不是界面文案，
    // 英文站的内容在中文界面里显示英文是正常的。这里只放窗口自己的界面字。
    "最新几条": { en: "Latest" },
    "这一站暂时读不到，入口仍然可用": {
      en: "This source is not reachable right now. The link above still works",
    },
    "暂时没有新内容。": { en: "Nothing new right now" },
    "更新于": { en: "Updated" },
    "刚刚更新": { en: "Updated just now" },
    // 资源页的分类目录。「全部」已在词典里（图谱页用过），不重复定义。
    "资源分类": { en: "Source categories" },
    /* 2026-09-22 i18n 修复补录：以下 4 条是 sources 页遗漏的界面文案。
       占位符走 translateDOM 的 ATTRS 自动翻译；其余 3 条是 JS 渲染处 tr() 查词，
       之前词表缺条目导致英文态回退中文。 */
    "搜站点、说明或文章标题": { en: "Search sites, notes, or article titles" },
    "AI总结": { en: "AI summary" },
    "最新一篇": { en: "Latest piece" },
    "内容来源": { en: "Content source" },
    // 论文页的外部收录
    "外部收录": { en: "External index" },
    "索引抓取于": { en: "Index fetched on" },
    "已精读": { en: "Read closely" },
    "论文来源": { en: "Paper source" },
    "分类": { en: "Category" },
    "子领域": { en: "Subfield" },
    "会议": { en: "Venue" },
    "显示更多": { en: "Show more" },
    "筛出": { en: "Filtered" },
    "总计": { en: "total" },
    "两万三千篇顶会论文解读，来自": { en: "23,000 conference paper write-ups, from" },
    /* 2026-09-22 i18n 修复：键补尾句号，对齐 papers 页 761 行 span 的实际文案
       （此前键无句号导致精确匹配失败，英文态该文本节点残留中文）。 */
    "，按论文自己的分类组织。点标题回原站看完整解读。": {
      en: ", organised the way the source files them. Open a title to read the full write-up there.",
    },
    "搜标题或方向": { en: "Search title or topic" },
    "读不到论文摘要索引。运行 python3 scripts/fetch-papernotes.py 生成后再刷新": {
      en: "Cannot read the paper index. Run python3 scripts/fetch-papernotes.py, then reload",
    },
    // 「正在读取…」和「刷新」已在词典里（前面几段），不在这里重复定义 ——
    // 同一个 key 定义两次时 JS 保留最后一个，前面那个变成死代码，
    // i18n_dict_audit 会把这种情况判为失败。

    // ── Home page: what every note answers ──
    /* Hero 那句：数字由 heroLede() 按实际篇数算，所以词典里存的是
     * 带占位符的模板 —— 固定文案查不到，模板才能一套覆盖 186 和以后任何数。 */
    "{n} 篇工程知识，每条讲清一个机制怎么运作、代价在哪": {
      en: "{n} engineering notes, each spelling out how a mechanism works and what it costs",
    },
    /* 左栏四问。这四条同时被首页和文章页的解析框架引用，
     * 换文案要一起换，否则英文界面下会一半新一半旧。 */
    "这一页有什么": { en: "What is on this page" },
    /* 首页两栏的标签：先说是哪一栏（知识 / 论文），再说读者拿走什么。
     *
     * 英文不能也用 "Knowledge"：导航里的「知识库」已经占了这一条，词典要求
     * 一条译文只能反查回一个中文来源，复用会报歧义。这里说的是"知识条目"这个
     * 内容类型，和右边 "Papers" 对仗，用 TNotes 更准。 */
    "知识": { en: "Notes" },
    "收录的是最新研究，每篇都按同一套问题拆开。扫一眼解析就能判断它讲的是什么、代价在哪，再决定要不要读原文": {
      en: "Recent research, each paper broken down along the same four questions. Skim the analysis to see what it claims and what it costs, then decide whether the paper itself deserves your time",
    },
    /* 右栏四问和左栏同一套，只有第一条的对象不同（论文"想解决什么"）。
     * 其余三条和左栏共用同一条译文，改的时候要一起看。 */
    "它想解决什么": { en: "What it solves" },
    "它怎么做的": { en: "How the method works" },
    "思路怎么来的": { en: "Where the idea comes from" },
    "为什么这样设计，换了什么假设": { en: "Why this design, and which assumption it traded" },
    "它为什么出现": { en: "Why it exists" },
    "之前卡在哪，没它的时候怎么办": { en: "What was stuck before" },
    "它怎么运作": { en: "How it works" },
    "机制是什么，关键那一步发生了什么": { en: "The mechanism, and its key step" },
    "做法是什么，凭什么成立": { en: "How it is done, and why that holds" },
    "它到底改变了什么": { en: "What it changes" },
    "哪个数字动了，在什么条件下测的": { en: "which number moved, measured under what conditions" },
    "什么时候不该用它": { en: "When not to use it" },
    "代价是什么，边界在哪": { en: "Cost and limits" },

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
    "从这一页点进去，登录和主题都会自动带上": { en: "Everything here carries the sign-in and the topic with it" },
    /* 2026-09-22 i18n 修复：projects 页文案带句号（601/611 行），补带句号版本词条（双词条策略）。 */
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
    "查看技能说明": { en: "See skill notes" },
    "查看 Agent 评估": { en: "See the agent evaluation" },
    "查看 Agent 评估的实现路线与待开发项": { en: "See the evaluation plan and what is still unbuilt" },
    "查看评估原型 →": { en: "See the prototype →" },
    "查看融合记录": { en: "See the integration notes" },
    "查看评估约定": { en: "See the evaluation conventions" },
    "检索、研究、记忆、笔记与复习工作区": {
      en: "Retrieval, research, memory, notes and revision in one workspace",
    },
    "理解": { en: "Understand" },
    /* 2026-09-22 i18n 修复：projects 页 643 行文案带句号，补带句号版本词条（双词条策略）。 */
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
    "，比记 IP 稳。": { en: ", which survives an IP change" },

    // ── apps/learning/index.html ──
    "AI 应用工程": { en: "AI application engineering" },
    "AI 知识系统": { en: "AI knowledge systems" },
    "RAG：从一次检索到有状态证据系统": { en: "RAG: from a single retrieval to a stateful evidence system" },
    "可靠 Agent：决策、执行与事实边界": { en: "Reliable agents: decisions, execution and the boundary of fact" },
    "后端与性能：从请求路径到瓶颈证据": {
      en: "Backend and performance: from request path to bottleneck evidence",
    },
    "真实缺陷解剖：从入门到精通": {
      en: "Real-defect dissection: from first steps to mastery",
    },
    "认识缺陷": { en: "Recognize the defect" },
    "两个真实缺陷对照：崩溃的会喊，静默算错的更致命": {
      en: "Two real defects side by side: crashes shout, silent wrong answers are deadlier",
    },
    "读缺陷的本质": { en: "Read what a defect is" },
    "学会判断": { en: "Learn to triage" },
    /* 2026-09-22 i18n 修复：键去句号，对齐 learning 页 831 行实际文案（无句号）。 */
    "四种结论加证据分级，决定人力往哪里投": {
      en: "Four verdicts plus evidence grades decide where the effort goes",
    },
    "读影响判断": { en: "Read impact triage" },
    "走完证据圈": { en: "Close the evidence loop" },
    "复现、合入、回归三步，每一步都留下可复查的证据": {
      en: "Reproduce, merge and regress — each step leaves evidence you can re-check",
    },
    "读复现到回归": { en: "Read reproduction to regression" },
    "导师考你": { en: "Tutor checks you" },
    /* 2026-09-22 i18n 修复：键去句号，对齐 learning 页 847 行实际文案（无句号）。 */
    "拿一条真实缺陷，从影响判断一路考到回归": {
      en: "One real defect, tested from impact triage all the way to regression",
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

    /* 【反复迭代后结果·rt17】以下 21 条是 learning 页正文级引导文案的英文翻译。
       背景：这些句子长于审计脚本的 CHROME_MAX_LENGTH=20 阈值，被归为"知识正文（设计上
       保持中文）"而从未进词典；但截图证据表明它们是界面引导（hero 导语、路径目标句、
       步骤描述、状态徽章、额度说明），EN 态半中半英观感是半成品。键逐字符复制自
       apps/learning/index.html 实际渲染文本（含句中换行空白），改中文文案须同步改键。 */
    "先用知识库建立结构，再用课堂形成直觉，用导师追问和复习，最后改掉一个约束再走一遍，看判断还成不成立。生成前始终由你确认，不会打开页面就消耗模型额度。": {
      en: "Build structure with the knowledge base first, then intuition in classrooms, questioning and review with the tutor, and finally change one constraint and run it again to see if the judgment still holds. Generation always waits for your confirmation; opening the page costs no model quota.",
    },
    "知识库回答“有哪些知识、它们怎么关联”。这里回答“选一个主题，做点什么才能真的会用”。只想读，回知识库就行": {
      en: "The knowledge base answers what knowledge exists and how it connects. This page answers what to do with one topic so you can actually use it. If you only want to read, stay in the knowledge base",
    },
    "两个工具都已经装好并在运行。右边的小绿标是它们此刻的真实状态": {
      en: "Both tools are installed and running. The small green badges on the right are their live status",
    },
    "适合理解机制、互动练习、测验、模拟和项目任务": {
      en: "For understanding mechanisms, interactive practice, quizzes, simulations and project tasks",
    },
    /* JS 渲染（fetch /api/learning/status 后写入），见 learning 页 958-970 行。
       已配置分支含动态数字（N 个知识库），词典整句键无法匹配，页面按两段拼接渲染。 */
    "运行中": { en: "Running" },
    "知识库检索已配置 · ": { en: "Retrieval configured · " },
    " 个知识库": { en: " knowledge bases" },
    /* 「导师可用」在下方 1673 行区域定义（Tutor is ready），此处旧定义是
       JS 重复 key 死代码，删除（i18n_dict_audit 报 2x duplicate）。 */
    "对话、研究、学习路径都能用；读资料提问暂时不行（缺 Embedding），页面上会如实标出来": {
      en: "Chat, research and learning paths all work; asking questions over documents does not yet (missing Embedding) — the page states this honestly",
    },
    "只有点击生成课堂后才调用模型；复杂互动课堂通常调用多轮": {
      en: "The model is called only after you click generate; a complex classroom usually takes several rounds",
    },
    "目标：能解释每次演进解决的瓶颈，并为真实场景选择检索、重排、图或\n                Agentic 路径。": {
      en: "Goal: explain the bottleneck each step of the evolution solved, and choose retrieval, reranking, graph or agentic paths for a real scenario.",
    },
    "证据选择为什么比“接一个向量库”更接近 RAG 的核心": {
      en: "Why evidence selection is closer to the core of RAG than plugging in a vector store",
    },
    "查询改写、混合检索、重排和状态循环分别暴露了什么旧瓶颈": {
      en: "Which old bottlenecks query rewriting, hybrid retrieval, reranking and stateful loops each exposed",
    },
    "让课堂用失败案例、对比和互动题检验你的判断": {
      en: "Let the classroom test your judgment with failure cases, contrasts and interactive questions",
    },
    "给出客服、代码库和长报告三个场景，逐一决定检索架构与评测指标。": {
      en: "Given support, a code repository and a long report, decide the retrieval architecture and evaluation metrics for each.",
    },
    "目标：能设计 Agent\n                的状态、工具、权限、证据和评估方式，而不是只会套框架。": {
      en: "Goal: design an agent's state, tools, permissions, evidence and evaluation instead of only applying a framework.",
    },
    "模型负责语义决策，运行时负责执行语义、隔离和可恢复状态": {
      en: "The model owns semantic decisions; the runtime owns executing semantics, isolation and recoverable state",
    },
    "状态机、工具约定、记忆、人工审批与故障恢复如何组合": {
      en: "How state machines, tool conventions, memory, human approval and failure recovery compose",
    },
    "以代码 Agent 为例，从任务接收到执行证据完整走一遍": {
      en: "Walk one code agent end to end, from receiving the task to evidence of execution",
    },
    "你提交架构，导师只追问无法证明、无法恢复或权限过宽的地方。": {
      en: "You submit the design; the tutor only asks about what cannot be proven, cannot be recovered, or is over-permissioned.",
    },
    "目标：能把延迟和可靠性问题沿请求、队列、存储、运行时和资源边界拆开验证。": {
      en: "Goal: split latency and reliability problems along request, queue, storage, runtime and resource boundaries, and verify each.",
    },
    "浏览器、网络、入口、服务和存储如何共同决定一次响应": {
      en: "How browser, network, entry point, service and storage together decide one response",
    },
    "等待、排队、CPU、内存、I/O 与锁竞争如何形成尾延迟": {
      en: "How waiting, queueing, CPU, memory, I/O and lock contention form tail latency",
    },
    "对一次 P99 抖动构造假设树和最小观测计划": {
      en: "Build a hypothesis tree and a minimal observation plan for one P99 spike",
    },
    "每提出一个根因，都必须给出能证伪它的指标或实验": {
      en: "Every root cause you propose must come with a metric or experiment that could falsify it",
    },
    "目标：能对一条真实缺陷独立完成影响判断、复现、合入与回归，并把每一步写成可复核的证据。": {
      en: "Goal: take one real defect through impact triage, reproduction, merge and regression on your own, writing each step as re-checkable evidence.",
    },
    "使用上方主题框或预置路径。主题写成一个真实问题，比只写“RAG”更容易获得有效教学。": {
      en: "Use the topic box above or a ready-made path. A topic written as a real question teaches better than a bare “RAG”.",
    },
    "入口只预填内容，不自动发送。检查目标和范围后再提交，模型额度由你的明确操作触发。": {
      en: "The entry only prefills; nothing is sent automatically. Check the goal and scope before submitting — model quota is spent only by your explicit action.",
    },
    /* 【反复迭代后结果·rt17b】projects 页 3 条 + insights 页 1 条短引导句。
       审计脚本此前报缺失（CHROME_MAX_LENGTH 内但未进词典），本轮补齐。 */
    "从本页点「打开课堂」，主题会带过去。": {
      en: "Click Open Classroom here and the topic travels with you.",
    },
    "点生成之前，先看一眼主题和材料范围。": {
      en: "Before generating, take one look at the topic and the material scope.",
    },
    "直接面向主题学习、资料研究、练习和复习。": {
      en: "Built for topic learning, material research, practice and review.",
    },
    "这些数字能说明什么。": {
      en: "What these numbers can and cannot tell you.",
    },

    /* 【反复迭代后结果·rt18】projects 页 36 条界面引导文案（页首导语、工具用途说明、
       状态徽章、源码行、能力表、工作流步骤、Agent 评估卡）。与 rt17 同根因：长于
       CHROME_MAX_LENGTH=20 被审计脚本归为"知识正文"，但它们是界面引导而非知识正文。
       键逐字符复制自 projects/index.html 实际渲染文本（含句中换行空白）。 */
    "四个第三方开源项目按实际用途排列：学习产品优先，工程方法其次，可视化是辅助。跨项目仍成立的方法会进入对应知识主题；Agent\n          评估独立维护。": {
      en: "Four third-party open-source projects, ordered by actual use: learning products first, engineering methods next, visualization as support. Methods that hold across projects land in the matching knowledge topics; agent evaluation is maintained separately.",
    },
    "这里放我已经装好的学习工具，以及它们的源码和说明。想看哪个点哪个，不用记端口和路径。": {
      en: "The learning tools I have installed, with their source and docs. Click the one you want; no ports or paths to remember.",
    },
    "当前是本机访问：知识库公开可读，启动教学工具自动使用已配置凭据": {
      en: "Local access right now: the knowledge base is public-readable, and launching a learning tool uses the configured credentials",
    },
    "想先把一个主题讲明白，用 OpenMAIC。输入主题后它会生成一节课，包含讲解、\n              互动、测验和练习。": {
      en: "To explain one topic first, use OpenMAIC. Give it a topic and it generates a lesson with explanation, interaction, quizzes and practice.",
    },
    "想就着一个问题反复追问，用 DeepTutor。它可以读你导入的资料，回答时给出出处，\n              也能把薄弱的地方整理成复习路径。": {
      en: "To push hard on one question, use DeepTutor. It reads the materials you import, answers with citations, and turns weak spots into review paths.",
    },
    "从本页点「进入学习导师」，会直接进对话界面。": {
      en: "Click Enter Tutor here and you land straight in the conversation view.",
    },
    "读文章、搜索、看图谱都不花钱。只有让工具生成内容时才会调用模型 ——\n              而这一步永远由你确认，页面不会自动发送。": {
      en: "Reading, search and graphs cost nothing. The model is called only when a tool generates content — and that step is always confirmed by you; pages never send on their own.",
    },
    "手机或同事的电脑也能读这些知识，只是启动教学工具时需要密码。\n              地址用": {
      en: "A phone or a colleague's computer can read this knowledge too; starting a learning tool just asks for a password. The address is",
    },
    "互动课堂可用": { en: "Classroom ready" },
    /* 导师可用=learning 页状态芯片，学习导师可用=projects 页状态文案，
       两个都是"DeepTutor 在线"但中文措辞不同，共享 "Tutor ready" 会让
       REVERSE 反查回翻错中文。 */
    "导师可用": { en: "Tutor is ready" },
    "把一个主题变成可操作的课堂。根据目标选择讲解、互动、测验、PBL\n              或可视化页面，适合把知识点从“读懂”推进到“做出来”。": {
      en: "Turn one topic into a hands-on classroom. Choose explanation, interaction, quizzes, PBL or visual pages by goal — good for moving from “understood” to “can do”.",
    },
    "本地源码：projects/OpenMAIC · 教学入口：本机 3100 端口": {
      en: "Local source: projects/OpenMAIC · Entry: localhost port 3100",
    },
    /* projects-page.js fetch 回调按 /api/access 结果二选一渲染（同 rt17 模式：
       晚于 translateDOM 写入），页面侧已改走 TKI18N.t()。 */
    "当前是其他设备访问：知识库公开可读；启动教学工具前需要输入访问密码": {
      en: "You are visiting from another device: the knowledge base is public-readable; starting a learning tool asks for the access password",
    },
    "访问状态暂时无法确认；知识库仍可阅读，启动教学工具时会按需要求授权": {
      en: "Access state could not be confirmed; the knowledge base stays readable, and a learning tool will ask for authorization when needed",
    },
    "把资料导入知识库后进行带引用问答、深度研究、可视化和掌握路径。它适合处理需要来源、追问和长期复习的主题。": {
      en: "Import materials into a knowledge base, then do cited Q&A, deep research, visualization and mastery paths. Best for topics that need sources, follow-ups and long-term review.",
    },
    "本地源码：projects/DeepTutor · 教学入口：本机 3782\n              端口，自动建立会话": {
      en: "Local source: projects/DeepTutor · Entry: localhost port 3782, session auto-created",
    },
    "帮助 Agent 形成可靠工程流程，或让系统关系更容易检查。": {
      en: "Helps agents form reliable engineering flows, or makes system relations easier to inspect.",
    },
    "把 Agent\n              的工程工作拆成可复用流程：先理解边界，再形成规格，按小步反馈实施，最后用测试和审查确认结果。": {
      en: "Splits an agent's engineering work into reusable flows: understand the boundary first, form a spec, implement in small feedback steps, confirm with tests and review.",
    },
    "本地源码：projects/mattpocock-skills · 技能已软链接到\n              Codex、Cursor、CodeBuddy": {
      en: "Local source: projects/mattpocock-skills · Skills symlinked into Codex, Cursor, CodeBuddy",
    },
    "把系统描述或仓库证据变成类型化图描述，再经过确定性校验生成可交互\n              HTML/SVG。它负责让关系可追踪，不负责替人编造业务事实。": {
      en: "Turns system descriptions or repo evidence into typed graph descriptions, then generates interactive HTML/SVG through deterministic checks. It makes relations traceable; it does not invent business facts.",
    },
    "本地源码：projects/archify/archify ·\n              适合：架构阅读、知识关系、证据图": {
      en: "Local source: projects/archify/archify · Good for: architecture reading, knowledge relations, evidence graphs",
    },
    "项目名称只用于回溯，跨项目仍成立的机制已经进入对应技术主题。": {
      en: "Project names are for tracing back; mechanisms that hold across projects have landed in their knowledge topics.",
    },
    "先区分稳定原则、当前能力、可复用结构和项目细节，再决定进入主题页、模板、候选区还是仅保留源码。": {
      en: "First separate stable principles, current capabilities, reusable structures and project details, then decide: topic page, template, candidate zone, or source only.",
    },
    "按学习目标选择讲解、互动、测验、模拟与项目任务": {
      en: "Choose explanation, interaction, quizzes, simulation or project tasks by learning goal",
    },
    "能力路由、来源与索引分层、记忆生命周期、复习路径": {
      en: "Capability routing, source & index layering, memory lifecycle, review paths",
    },
    "一手来源研究、复用优先、反馈回路、TDD 与审查": {
      en: "Primary-source research, reuse-first, feedback loops, TDD and review",
    },
    "类型化图描述、证据节点、确定性验证、last-good 交付": {
      en: "Typed graph descriptions, evidence nodes, deterministic checks, last-good delivery",
    },
    "不是每个主题都做成同一种页面，输出类型由要形成的能力决定。": {
      en: "Not every topic becomes the same kind of page; the output type follows the capability you want to build.",
    },
    "一条实际使用路径，把知识、教学、复习和验证连起来。": {
      en: "One real usage path linking knowledge, teaching, review and verification.",
    },
    "从知识库按技术领域找到一个要解决的问题，必要时用图谱定位前置关系。": {
      en: "Pick a problem from the knowledge base by domain; use the graph to locate prerequisites when needed.",
    },
    "用 OpenMAIC 生成解释、互动、测验或项目任务。": {
      en: "Generate explanations, interactions, quizzes or project tasks with OpenMAIC.",
    },
    "用 DeepTutor 导入来源，追问、研究、记忆和复习。": {
      en: "Import sources with DeepTutor; question, research, remember, review.",
    },
    "用真实结果检验理解；评估运行时完成后，再用于 Agent\n              轨迹和证据审查。": {
      en: "Test understanding against real results; once the evaluation runtime is ready, also for agent traces and evidence review.",
    },
    "当前完成设计约定、静态原型和基础包；真实任务接入、隔离执行、Trace\n              与证据投影仍待开发。": {
      en: "Design conventions, static prototype and base package are done; real task intake, isolated execution, trace and evidence projection are still to build.",
    },
    "识别语言、构建系统、环境、测试入口和成功条件，由 Agent 提出方案。": {
      en: "Identify language, build system, environment, test entry and success criteria; the agent proposes the plan.",
    },
    "保存实际命令、退出码、日志、产物、提交和任务代际，不能只相信 Agent\n              的总结。": {
      en: "Keep the actual commands, exit codes, logs, artifacts, commits and task generations — never trust only the agent's summary.",
    },
    "把失败分类为编译、依赖、权限、资源、产品未触发或断言失败，再生成最小回归任务。": {
      en: "Classify failures as build, dependency, permission, resource, product-not-triggered or assertion, then generate a minimal regression task.",
    },
    "这不是第三方开源项目，也不是已经可以运行真实评测的成品。模型负责理解和决策，未来的评估运行时负责隔离、执行、证据和一致性。": {
      en: "This is not a third-party open-source project, nor a finished product that can run real evaluations yet. The model owns understanding and decisions; the future evaluation runtime owns isolation, execution, evidence and consistency.",
    },

    "额度说明：阅读知识库不消耗模型\n          Token；打开工具不消耗；发送问题或生成课堂才消耗。互动课堂通常比单轮问答调用更多，长材料、深度研究和多轮追问也会显著增加消耗。": {
      en: "Quota: reading the knowledge base costs no model tokens; opening a tool costs nothing; sending a question or generating a classroom does. Interactive classrooms usually cost more than a single answer, and long materials, deep research and multi-turn questioning add up quickly.",
    },

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
    "入口原则": { en: "What belongs at the entrance" },
    "关键状态、数据流和因果关系是什么？": { en: "What are the key states, data flows and causal relationships?" },
    "其他机器访问": { en: "Reaching it from another machine" },
    "凭据": { en: "Credentials" },
    "分层讲解、流程图、最小例子或模拟": {
      en: "Layered explanation, diagrams, a smallest example or a simulation",
    },
    "取舍与演变": { en: "Trade-offs and how it changed" },
    "受保护入口": { en: "A gated entrance" },
    "可接受的产出": { en: "An acceptable output" },
    "可靠 Agent": { en: "Reliable agents" },
    "可靠 Agent 架构": { en: "Reliable agent architecture" },
    "后端性能与一致性": { en: "Backend performance and consistency" },
    /* 启动=openmaic 状态芯片"启动 受保护入口"的动词语义；入门=learning
       路径标签。语义不同，不共享 "Getting started"。 */
    "启动": { en: "Launch" },
    "和知识库如何配合": { en: "How it works with the knowledge base" },
    "在课堂里做出判断": { en: "Make the call inside the classroom" },
    "它解决了什么真实痛点？不解决什么？": { en: "What real problem does it solve, and what does it not solve?" },
    "官方 GitHub ↗": { en: "Official GitHub ↗" },
    "已生成的真实课堂": { en: "Real classrooms already generated" },
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
    /* 【2026-09-22 去箭头同步】页面文案删掉 → 后旧 key 成孤儿，换成本 key。 */
    "查看项目与源码": { en: "See the project and source" },
    "检查生成前的大纲": { en: "Check the outline before generating" },
    "模型不可用或生成失败": { en: "The model is unavailable, or generation failed" },
    "版本/方案对比、选择条件、失败案例": {
      en: "Version or approach comparisons, selection criteria, failure cases",
    },
    "版本、论文、项目或实验数据可以继续追溯": { en: "Versions, papers, projects or measurements remain traceable" },
    /* 2026-09-22 i18n 修复：openmaic 页 317 行文案带句号，补带句号版本词条（双词条策略）。 */
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
    /* 【rt20】details 恢复段被 <code> 标签切成两个文本节点
       （…直接打开了 <code>3100</code>，绕过了…），translateDOM 按节点
       逐个翻译，前半已有键，后半此前无键，EN 态残留。 */
    "，绕过了本知识库的启动入口。关闭该标签，回到本页点击“开始课堂”；入口会先完成授权，再把主题带入课堂。": {
      en: " directly, bypassing this knowledge base's launch entry. Close that tab, come back and click “Start classroom”; the entry authorises first, then carries the topic in.",
    },
    "路径。回到本页确认“课堂服务”状态，再重新点击启动；若服务刚重启，刷新本页后再试。": {
      en: " path. Come back, check the “classroom service” status, then click launch again; if the service just restarted, reload this page and retry.",
    },
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
    /* 【rt20】openmaic 页正文句补齐：EN 态 DOM 实测残留 29 条。
       既有 3 条短键（这通常是直接打开了/不要使用旧的/页面本身不会
       要求你输入 Key 的前半）因源码句中断行从未命中，此轮连同整句
       一起补全量词条；表格问题句与 checklist 句此前无词条。 */
    "把知识库里的主题变成讲解、对比、测验、模拟或项目任务。页面打开不会调用模型；只有你在课堂中生成或提问时才使用额度。": {
      en: "Turn a knowledge-base topic into explanations, comparisons, quizzes, simulations or project tasks. Opening the page calls no model; quota is used only when you generate or ask inside the classroom.",
    },
    "通过这个入口会自动带上授权；手动访问端口可能停在授权页或空白页。": {
      en: "This entry carries the authorisation automatically; opening the port by hand can leave you on an auth page or a blank one.",
    },
    "知识库告诉你要学什么；这页帮你把主题交给课堂、检查产出质量，并在结果不对时知道从哪里恢复。": {
      en: "The knowledge base tells you what to learn; this page hands the topic to the classroom, checks the output quality, and shows where to recover when things go wrong.",
    },
    "每一步都要留下判断或产出，不以摘要为完成。": {
      en: "Every step must leave a judgement or an artefact; a summary does not count as done.",
    },
    "写主题、目标和背景，例如“我要比较 Hybrid Search 与 Reranker 在长文档 RAG 中的收益”。越具体，课堂越容易围绕判断展开。": {
      en: "Write the topic, goal and background, e.g. “I want to compare the gains of Hybrid Search vs a reranker on long-document RAG”. The more specific, the more the classroom revolves around judgement.",
    },
    "先看它是否覆盖问题、本质、机制、边界和示例。发现范围过大或过旧时，先改主题，不要直接生成。": {
      en: "Check whether it covers the problem, the essence, the mechanism, boundaries and examples. If the scope is too broad or stale, fix the topic first instead of generating.",
    },
    "回答预测题、比较方案、观察模拟或完成小任务。教师与助教的价值在于解释“为什么”，不是替你报答案。": {
      en: "Answer prediction questions, compare approaches, watch simulations or finish small tasks. The teacher and assistant are valuable for explaining “why”, not for reporting answers for you.",
    },
    "换数据规模、延迟预算、权限或故障条件重新选择方案。能解释取舍，才说明知识已经变成工程能力。": {
      en: "Re-choose the approach under new data scale, latency budget, permissions or fault conditions. Explaining the trade-off is what shows the knowledge has become engineering skill.",
    },
    "点击一个预设会填入上方输入框；你仍然可以修改后再启动。": {
      en: "Clicking a preset fills the input above; you can still edit it before launching.",
    },
    "可以直接复制这段思路，再替换主题和约束：": {
      en: "Copy this pattern and swap in your own topic and constraints:",
    },
    "请围绕【主题】设计一堂面向【我的基础】的互动课。先说明它解决什么问题、核心机制和演变原因，再用一个最小例子讲清楚；加入方案对比、失败案例、互动题和即时反馈；最后给出一个带【约束】的迁移任务，并列出需要查证的来源。": {
      en: "Design an interactive lesson on [topic] for [my background]. Start with the problem it solves, the core mechanism and why it evolved, then make it concrete with a minimal example; include approach comparisons, failure cases, interactive questions and live feedback; end with a transfer task under [constraints] and list the sources to verify.",
    },
    "如果主题依赖最新版本、论文或项目动态，请在请求中写明“以当前资料为准并标出来源”；课堂用于学习和练习，关键事实仍回到知识库来源页核对。": {
      en: "If the topic depends on recent versions, papers or project news, say “go by current sources and cite them” in the request; the classroom is for learning and practice, while key facts still get checked against knowledge-base source pages.",
    },
    "下面是可验收的教学结果，不是固定页面布局；不同主题会选择不同课堂组件。": {
      en: "These are acceptable teaching outcomes, not a fixed page layout; different topics pick different classroom components.",
    },
    "为什么从旧方案演进到现在？新增了什么代价？": {
      en: "Why did it evolve from the old approach, and what new costs appeared?",
    },
    "这是用本机 OpenMAIC 实际生成并验收过的可播放课程，不是静态示意页。": {
      en: "A playable course actually generated and accepted on this machine's OpenMAIC, not a static mock-up.",
    },
    "五个场景：问题与目标、缓存命中机制、最小 Python/Redis 例子、失效与一致性失败案例、带约束的迁移练习。课堂内容已由模型生成并保存在 OpenMAIC 的课堂存储中。": {
      en: "Five scenes: problem and goal, cache-hit mechanics, a minimal Python/Redis example, invalidation and consistency failure cases, and a constraint-bearing transfer exercise. The content was model-generated and lives in OpenMAIC's classroom store.",
    },
    "生成后花一分钟扫一遍；缺项就回到大纲或主题继续编辑。": {
      en: "Spend a minute scanning after generation; for anything missing, go back to the outline or topic and keep editing.",
    },
    "每个做法都解释了要解决的约束、机制和收益。": {
      en: "Every practice explains the constraint it solves, the mechanism and the payoff.",
    },
    "明确何时不适用、成本在哪里、替代方案是什么。": {
      en: "Make clear when it does not apply, where the cost sits, and what the alternatives are.",
    },
    "你需要先做判断，系统再解释答案和错误原因。": {
      en: "You judge first; the system then explains the answer and why the error happened.",
    },
    "能用一段代码、一个配置或一个小数据集复现核心现象。": {
      en: "The core phenomenon can be reproduced with a snippet, a config or a small dataset.",
    },
    "改变输入、规模或失败条件后仍然能重新做决策。": {
      en: "You can still re-decide after the input, scale or failure conditions change.",
    },
    "这通常是直接打开了 3100，绕过了本知识库的启动入口。关闭该标签，回到本页点击“开始课堂”；入口会先完成授权，再把主题带入课堂。": {
      en: "This usually means port 3100 was opened directly, bypassing this knowledge base's launch entry. Close that tab, come back and click “Start classroom”; the entry authorises first, then carries the topic into the classroom.",
    },
    "不要使用旧的 /workbench/new 路径。回到本页确认“课堂服务”状态，再重新点击启动；若服务刚重启，刷新本页后再试。": {
      en: "Do not use the stale /workbench/new path. Come back, check the “classroom service” status, then click launch again; if the service just restarted, reload this page and retry.",
    },
    "页面本身不会要求你输入 Key。先缩小主题、减少附件并重试；如果仍失败，查看课堂服务状态和错误提示，不要把“生成失败”当成知识结论。": {
      en: "The page itself will never ask for your key. Narrow the topic, drop attachments and retry; if it still fails, check the service status and the error message — a failed generation is not a knowledge conclusion.",
    },
    "知识库页面可以直接阅读；启动会使用模型凭据，因此远程设备会先要求知识库密码。本机浏览器通过受信来源自动放行，密码不会出现在 URL 或页面源码中。": {
      en: "Knowledge-base pages read fine as they are; launching uses model credentials, so remote devices are asked for the knowledge-base password first. The local browser is let through as a trusted origin, and the password never appears in the URL or page source.",
    },
    "课堂不是第二套分类。先从稳定知识页建立背景，再用课堂把一个主题练成能力；课堂结束后，把经过核对的结论整理回 Markdown。": {
      en: "The classroom is not a second taxonomy. Build background from settled knowledge pages first, then drill a topic into skill in the classroom; afterwards, fold the verified conclusions back into Markdown.",
    },
    "推荐顺序：读概览 → 选择一个具体问题 → 启动课堂 → 通过迁移题 → 将经过来源核对的结论收录。": {
      en: "Suggested order: read an overview → pick one concrete problem → launch a classroom → pass the transfer task → file the source-checked conclusion.",
    },
    "本页是 OpenMAIC 的教学入口；项目页是源码、版本和能力索引；知识库是长期事实来源。三者职责不同，但都从本页的安全启动链接进入课堂。": {
      en: "This page is OpenMAIC's teaching entry; the project page indexes source, versions and capabilities; the knowledge base is the long-term source of fact. Three different jobs, all entering the classroom through this page's safe launch links.",
    },
    "先写下你要掌握的主题": { en: "Start with the topic you want to master" },
    "开始课堂 ↗": { en: "Start classroom ↗" },
    "课堂服务可用": { en: "Classroom service up" },
    "课堂服务未启动": { en: "Classroom service not running" },
    "课堂服务状态未知": { en: "Classroom service status unknown" },

    // ── apps/learning/intuition.html ──
    "Agent 状态": { en: "Agent state" },
    "RAG 召回": { en: "RAG recall" },
    "形成直觉的产出": { en: "What this builds" },
    "打开 OpenMAIC": { en: "Open OpenMAIC" },
    /* 2026-09-22：「打开课堂 ↗」已删——history 页 job-cta 改用无箭头 key
       「打开课堂」（L1424 已有词条）。↗ 语义只给出站链接，本机 /launch
       服务不是出站。 */
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
    /* 【rt20】intuition 页正文句：EN 态 DOM 实测残留 12 条
       （10 长句 + 2 句中断行已改单行）。短词条（课堂会做什么/
       开始前知道/会消耗什么等）此前已有。 */
    "用预测、对比、反馈和迁移，把抽象机制变成可判断的心智模型。适合 RAG、缓存、一致性、Agent 状态这类“读懂了但还不会用”的主题。": {
      en: "Use prediction, comparison, feedback and transfer to turn abstract mechanisms into a working mental model. Fits topics like RAG, caching, consistency and agent state — the “read it but cannot use it” kind.",
    },
    "你要先预测结果，再说清变量变化为什么改变结论。看解释不算产出。": {
      en: "You predict the outcome first, then explain why a changed variable flips the conclusion. Reading an explanation does not count.",
    },
    "当你已经读过概念，但面对新数据、新约束或失败案例还不能预测结果时，先用互动课堂把判断过程练出来。": {
      en: "When you have read the concepts but still cannot predict outcomes facing new data, constraints or failure cases, drill the judgement itself in an interactive classroom first.",
    },
    "OpenMAIC 会把主题组织成连续的学习动作，而不是只给一段摘要。": {
      en: "OpenMAIC organises the topic into a sequence of learning actions instead of a single summary.",
    },
    "用一个最小例子说明变量、目标和约束，先让你说出预期。": {
      en: "A minimal example lays out the variables, goal and constraints, and you state your expectation first.",
    },
    "改变数据规模、查询、权限、负载或故障，观察原判断在哪一步失效。": {
      en: "Change data scale, queries, permissions, load or faults, and watch which step your original judgement breaks on.",
    },
    "教师和助教把结果连接回机制、边界和工程取舍。": {
      en: "Teacher and assistant tie the outcome back to mechanisms, boundaries and engineering trade-offs.",
    },
    "换一个真实场景重新选择方案，确认直觉不是只记住案例。": {
      en: "Pick the approach again in a different real scenario, to confirm it is intuition rather than memorising a case.",
    },
    "打开课堂不会调用模型；点击生成课堂后才会产生模型请求。主题会预填，提交前可以修改。": {
      en: "Opening the classroom calls no model; the request happens only after you click generate. The topic is prefilled and editable before you submit.",
    },
    "生成后的课堂由 OpenMAIC 自己保存到它的课堂库/浏览器存储。它不会自动写入本知识库 Markdown；需要正式收录时，应把经过核对的稳定结论整理成知识页，并保留课堂作为来源。": {
      en: "The generated classroom is kept in OpenMAIC's own classroom store / browser storage. It never writes into this knowledge base's Markdown on its own; to file it properly, distil the verified conclusions into a knowledge page and keep the classroom as its source.",
    },
    "先预测查询改写、混合检索和重排分别会改变什么结果。": {
      en: "Predict what query rewriting, hybrid retrieval and reranking each change about the result.",
    },
    "换 TTL、写入路径和并发条件，观察一致性问题从哪里出现。": {
      en: "Vary TTL, write paths and concurrency, and watch where consistency problems first appear.",
    },
    "改变工具失败、预算和人工审批，判断循环是否还能安全结束。": {
      en: "Change tool failures, budgets and human approvals, and judge whether the loop can still end safely.",
    },
    "这次验证要产出什么": { en: "What this validation should produce" },
    "适合什么时候用": { en: "When to use it" },
    "适合迁移验证的主题示例": { en: "Example topics for transfer validation" },
    "适用边界": { en: "Where it applies" },
    "验证看什么": { en: "What validation looks at" },
    /* 【rt20】transfer 页正文句：EN 态 DOM 实测残留 12 条
       （11 长句 + 1 句中断行已改单行）。短词条（换场景/换约束/
       给反例/说证据等）此前已有。 */
    "用换场景、换约束和反例，检查一个方案是否真的掌握。能在条件变化后重新选择，并说出证据，才算从“看懂”进入“会用”。": {
      en: "Use changed scenarios, changed constraints and counterexamples to test whether an approach is truly mastered. Only when you can re-choose under new conditions and state your evidence have you moved from “read it” to “can use it”.",
    },
    "一组可被追问的选择：为什么仍然成立、何时失效、用什么指标证明。": {
      en: "A set of choices that survive questioning: why it still holds, when it breaks, and which metric proves it.",
    },
    "当你能复述一个方案，却不确定换数据、权限、规模或故障后是否仍然成立时，用迁移任务验证真正的掌握。": {
      en: "When you can recite an approach but are not sure it survives new data, permissions, scale or faults, use transfer tasks to validate real mastery.",
    },
    "有意改变决定方案的关键变量，再做一次 —— 同样的题做第二遍不算迁移。": {
      en: "Deliberately change the variables the approach hinges on, then do it again — doing the same task twice is not transfer.",
    },
    "客服知识库、代码仓库、长报告或实时事件，检查方案是否依赖特定案例。": {
      en: "Support knowledge bases, code repositories, long reports or live events — check whether the approach depends on one specific case.",
    },
    "改变时延、成本、权限、数据新鲜度或可用资源，重新排序取舍。": {
      en: "Change latency, cost, permissions, data freshness or available resources, and re-rank the trade-offs.",
    },
    "引入召回为空、引用冲突、下游超时或工具失败，检查是否知道如何拒答和恢复。": {
      en: "Introduce empty recall, citation conflicts, downstream timeouts or tool failures, and check whether you know how to refuse and recover.",
    },
    "每个判断都要指出可观察指标、实验或产物，避免凭感觉宣布成功。": {
      en: "Every judgement must point at an observable metric, experiment or artefact — no declaring success on a feeling.",
    },
    "打开导师只建立会话，不自动发送；点击发送问题、研究或生成练习后才调用模型。复杂研究会产生更多请求。": {
      en: "Opening the tutor only starts a session and sends nothing; the model is called only after you send a question, research or exercise request. Complex research makes more requests.",
    },
    "导师的回答和复习记录属于 DeepTutor 工作区。确认稳定结论后，再把它整理成知识库页面；不要把一次回答直接当成事实来源。": {
      en: "The tutor's answers and review records live in the DeepTutor workspace. Only after a conclusion has settled should it become a knowledge-base page; a single answer is never a source of fact on its own.",
    },
    "客服、代码库和长报告分别选择不同检索、重排和引用策略。": {
      en: "Support desks, code repositories and long reports each call for different retrieval, reranking and citation strategies.",
    },
    "同一接口在低延迟、高并发和弱一致条件下重新设计边界。": {
      en: "Redesign the same interface's boundaries under low latency, high concurrency and weak consistency.",
    },
    "加入工具超时、权限不足和预算耗尽，检查恢复策略是否完整。": {
      en: "Add tool timeouts, missing permissions and exhausted budgets, and check whether the recovery strategy is complete.",
    },

    // ── apps/agent-evaluation/index.html ──
    "Agent 画像": { en: "Agent profile" },
    "Agent 自己说“改好了”不算数。这个原型先把任务和证据定义清楚，再据此开发隔离执行、Trace、回归与报告。评分器本身尚未上线。": {
      en: "An agent saying “done” does not count. This prototype pins down tasks and evidence first, then builds isolated execution, traces, regression and reporting on top. The scorer itself is not online yet.",
    },
    "SLO + 运营": { en: "SLO and operations" },
    "下一步实现顺序": { en: "What gets built next, in order" },
    "下面是实现时的最小数据约定，先固定证据形状，再接入具体 Agent、仓库和任务夹具": {
      en: "The minimal data conventions for implementation: pin down the evidence shape first, then wire up specific agents, repos and task fixtures",
    },
    "不能把模型文本当作命令已执行": { en: "Model text is not evidence that a command ran" },
    "不能替代": { en: "Does not replace" },
    "不能用模糊“看起来完成”作断言": { en: "“Looks done” is not an assertion" },
    "不能由 README 单独证明运行行为": { en: "A README alone cannot prove runtime behaviour" },
    "不能脱离证据编造性能或适用性": {
      en: "Performance and applicability cannot be asserted without evidence",
    },
    "不能隐去失败、重试或后一次覆盖前一次成功": {
      en: "Failures and retries must stay visible; a later run must not overwrite an earlier success",
    },
    "业务操作": { en: "Business operations" },
    "产物": { en: "Artefacts" },
    "产物、测试、数据库状态、引用、用户目标和可复现记录": {
      en: "Artefacts, tests, database state, citations, user goals and reproducible records",
    },
    "任务夹具": { en: "Task fixture" },
    "任务约定": { en: "Task conventions" },
    "任务类型、模型、工具、状态、权限、依赖和版本": {
      en: "Task types, models, tools, state, permissions, dependencies and versions",
    },
    "判断": { en: "Judgement" },
    "功能交付": { en: "Feature delivery" },
    "协作 + 责任": { en: "Collaboration and responsibility" },
    "召回、重排、引用、拒答、时效和权限过滤是否分别可测": {
      en: "Whether recall, reranking, citations, refusals, freshness and permission filters are each measurable",
    },
    "命令记录": { en: "Commands" },
    "回归": { en: "Regression" },
    "工具权限、审批、幂等、副作用和失败恢复是否在边界内": {
      en: "Whether tool permissions, approvals, idempotency, side effects and failure recovery stay within bounds",
    },
    "声明": { en: "Claim" },
    "复现": { en: "Reproduce" },
    "复现 + 因果": { en: "Reproduction and causation" },
    "委托协议、任务所有权、交接状态和跨系统失败是否可追踪": {
      en: "Whether delegation protocols, task ownership, handover state and cross-system failures stay traceable",
    },
    "多 Agent 协作": { en: "Multi-agent collaboration" },
    "安全 + 状态": { en: "Safety and state" },
    "当前已经明确任务约定、证据边界、评估维度和实现顺序；尚未接入真实仓库执行、Trace 采集与证据投影，因此页面不会生成或展示虚假的运行评分": {
      en: "The task conventions, evidence boundaries, evaluation dimensions and build order are settled; real repo execution, trace capture and evidence projection are not wired up yet, so this page shows no fabricated scores",
    },
    "当前：设计约定与静态原型": { en: "Now: design conventions and a static prototype" },
    "先做任务夹具与 Trace schema，再做执行隔离和证据投影，最后接入模型评审与可视化。每一步都能独立测试和回滚": {
      en: "Task fixtures and the trace schema first, then execution isolation and evidence projection, and finally model review and visualisation. Each step can be tested and rolled back on its own",
    },
    "先建立被评测 Agent 的画像，再选择与任务相称的证据。不同任务不共享一张“万能评分表”": {
      en: "Profile the agent under test first, then pick evidence proportionate to the task. No two tasks share one “universal scorecard”",
    },
    /* 【rt19】agenteval 页 5 条界面引导句带句号版：三条旧键无句号
       没命中（页面句带句号），两条 hero 句从未有条目。EN 态 DOM
       实测残留 5 条，补齐后全页清零。 */
    "先建立被评测 Agent 的画像，再选择与任务相称的证据。不同任务不共享一张“万能评分表”。": {
      en: "Profile the agent under test first, then pick evidence proportionate to the task. No two tasks share one “universal scorecard”.",
    },
    "这是一个用来评估 Agent 的原型：它把 Agent 的输出判断绑定到命令、日志、产物和测试，让“有没有变好”变成可核验证据，而不是一句主观结论。": {
      en: "A prototype for evaluating agents: it ties an agent's output claims to commands, logs, artefacts and tests, so “did it get better” becomes checkable evidence instead of a subjective verdict.",
    },
    "当前已经明确任务约定、证据边界、评估维度和实现顺序；尚未接入真实仓库执行、Trace 采集与证据投影，因此页面不会生成或展示虚假的运行评分。": {
      en: "The task conventions, evidence boundaries, evaluation dimensions and build order are settled; real repo execution, trace capture and evidence projection are not wired up yet, so this page shows no fabricated scores.",
    },
    "下面是实现时的最小数据约定，先固定证据形状，再接入具体 Agent、仓库和任务夹具。": {
      en: "The minimal data conventions for implementation: pin down the evidence shape first, then wire up specific agents, repos and task fixtures.",
    },
    "先做任务夹具与 Trace schema，再做执行隔离和证据投影，最后接入模型评审与可视化。每一步都能独立测试和回滚。": {
      en: "Task fixtures and the trace schema first, then execution isolation and evidence projection, and finally model review and visualisation. Each step can be tested and rolled back on its own.",
    },
    "待开发：Trace 与证据投影": { en: "To build: trace capture and evidence projection" },
    "待开发：任务接入与隔离执行": { en: "To build: task intake and isolated execution" },
    "必须回答": { en: "Must answer" },
    "成本、延迟、漂移、告警、回滚和人工接管是否持续可见": {
      en: "Whether cost, latency, drift, alerts, rollback and human takeover stay visible over time",
    },
    "执行轨迹": { en: "Execution trace" },
    "把 Agent 的判断变成可验证证据": { en: "Turn an agent’s judgement into verifiable evidence" },
    "把改进写回固定任务集，比较前后结果与失败类型": {
      en: "Write improvements back to a fixed task set and compare outcomes and failure types before and after",
    },
    "把观察到的事实映射到任务特定的质量标准": { en: "Map observed facts onto task-specific quality criteria" },
    "持续层": { en: "Continuous layer" },
    "按任务选择评估维度": { en: "Choose evaluation dimensions per task" },
    "改进": { en: "Improvement" },
    "改进报告": { en: "Improvement report" },
    "是否先复现、定位根因、保持最小改动，并证明没有覆盖旧事实": {
      en: "Whether it reproduces first, finds the root cause, keeps the change minimal, and proves no old fact was buried",
    },
    "日志、退出码、diff、测试、产物、引用和环境摘要": {
      en: "Logs, exit codes, diffs, tests, artefacts, citations and an environment summary",
    },
    "框架只守住事实边界，语义判断由 Agent 或评审者完成": {
      en: "The framework only guards factual boundaries; semantic judgement stays with agents or reviewers",
    },
    "检索与问答": { en: "Retrieval and question answering" },
    "模型调用、工具参数、状态迁移、重试、权限和时间线": {
      en: "Model calls, tool arguments, state transitions, retries, permissions and a timeline",
    },
    "每次决策、工具调用、参数、返回、状态和时间": {
      en: "Every decision, tool call, argument, return, state change and timestamp",
    },
    "没有独立日志、任务上下文和可检查产物，就只能标为“未证实”，不能标为成功": {
      en: "Without independent logs, task context and inspectable artefacts, an outcome is “unverified”, not a success",
    },
    /* 【rt19】页面 .rule 里该句带句号（HTML 源里换行缩进在 trim 后
       仍留尾空格由 sourceOf 处理），词典键无句号版没命中 EN 态整句
       文本节点，补带句号版。 */
    "没有独立日志、任务上下文和可检查产物，就只能标为“未证实”，不能标为成功。": {
      en: "Without independent logs, task context and inspectable artefacts, an outcome is “unverified”, not a success.",
    },
    "目标、输入、允许副作用、成功条件、失败条件与预算": {
      en: "Goal, inputs, allowed side effects, success and failure conditions, and budget",
    },
    "结果 + 回归": { en: "Outcome and regression" },
    "结果事实": { en: "Outcome facts" },
    "结果证据": { en: "Outcome evidence" },
    "维度是可组合的观察面，不是并列的产品排名": {
      en: "Dimensions are composable lenses, not a leaderboard",
    },
    "给出最小改变、作用机制、成本、风险和回归方案": {
      en: "State the minimal change, its mechanism, cost, risks and a regression plan",
    },
    "缺陷修复": { en: "Defect fix" },
    "行动层": { en: "Action layer" },
    "解释层": { en: "Explanation layer" },
    "计划接入的评估产物": { en: "Evaluation artefacts planned" },
    "证据 + 质量": { en: "Evidence and quality" },
    "证据包": { en: "Evidence bundle" },
    "证据链": { en: "Evidence chain" },
    "评估约定": { en: "Evaluation conventions" },
    "输入、环境、成功/失败条件、预算和可重放步骤": {
      en: "Inputs, environment, success/failure conditions, budget and replayable steps",
    },
    "输入事实": { en: "Input facts" },
    "过程事实": { en: "Process facts" },
    "退出码": { en: "Exit code" },
    "这是一个用来评估 Agent 的原型：它把 Agent 的输出判断绑定到命令、日志、产物和测试，让“有没有变好”变成可核验证据，而不是一句主观结论": {
      en: "A prototype for evaluating agents: it ties output claims to commands, logs, artefacts and tests, so “did it get better” becomes checkable evidence instead of a subjective verdict",
    },
    "长期运行": { en: "Long-running" },
    "已有：agent-foundation 基础包": { en: "Shipped: the agent-foundation package" },
    "门禁：": { en: "Gate:" },
    "问题、作用机制、最小改动、反例、成本、置信度和回归": {
      en: "Problem, mechanism, minimal change, counterexamples, cost, confidence and regression",
    },
    "验收条件、代码差异、测试、构建与部署结果是否真实完成": {
      en: "Whether acceptance criteria, code diffs, tests, build and deploy results actually happened",
    },

    // ── 【反复迭代后结果·rt14】知识主题词条（41 个）。
    //    依据：EN 态实测（DOM 采集）发现首页领域卡的主题 chip（模型基础与训练、
    //    正确性、并发…）与知识地形主题点全部裸奔中文，translateDOM 机制本身
    //    覆盖这些节点，缺的只是词条。python 静态比对：41 个主题词无 EN 词条。
    //    译文风格对齐已有「概览→Summary」的简短名词式。专有领域名
    //    （AI 系统工程等六领域长名）保持中文，与 rt13 决策一致。 ──
    "模型基础与训练": { en: "Models & training" },
    "模型与上下文": { en: "Models & context" },
    "知识与检索": { en: "Knowledge & retrieval" },
    "Agent与工作流": { en: "Agents & workflows" },
    "推理服务与平台": { en: "Inference serving" },
    "数据与MLOps": { en: "Data & MLOps" },
    "质量与运营": { en: "Quality & operations" },
    "安全与治理": { en: "Safety & governance" },
    "生态与选型": { en: "Ecosystem & choices" },
    "服务设计": { en: "Service design" },
    "任务与并发": { en: "Tasks & concurrency" },
    "分布式可靠性": { en: "Distributed reliability" },
    "基础设施": { en: "Infrastructure" },
    "数据建模与SQL": { en: "Modelling & SQL" },
    "事务与存储": { en: "Transactions & storage" },
    "查询与索引": { en: "Queries & indexing" },
    "数据管道与流处理": { en: "Pipelines & streaming" },
    "数据治理": { en: "Data governance" },
    "可靠性与运维": { en: "Reliability & ops" },
    "操作系统与运行时": { en: "OS & runtimes" },
    "处理器与内存": { en: "CPU & memory" },
    "存储与网络": { en: "Storage & network" },
    "观测与诊断": { en: "Observability" },
    "性能工程": { en: "Performance engineering" },
    "语言与运行时": { en: "Languages & runtimes" },
    "算法与数据结构": { en: "Algorithms & data structures" },
    "架构与代码": { en: "Architecture & code" },
    "开发工具": { en: "Developer tools" },
    "测试与交付": { en: "Testing & delivery" },
    "影响判断": { en: "Impact judgement" },
    "复现与回归": { en: "Repro & regression" },
    "稳定性": { en: "Stability" },
    "正确性": { en: "Correctness" },
    "并发": { en: "Concurrency" },
    "配置与可操作": { en: "Config & operability" },
    "安全": { en: "Security" },
    "资源与容量": { en: "Capacity & resources" },
    "兼容与升级": { en: "Compat & upgrades" },
    "硬件故障": { en: "Hardware failures" },
    "剪藏": { en: "Clippings" },
  };

  /* ── Current language ─────────────────────────────────────────────────── */
  const stored = () => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (err) {
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
    /* 【rt23b】root.querySelectorAll("*") 只返回后代，不包含 root 自己的
       属性。侧栏根节点（aside[aria-label=站点导航]）与控件组根节点
       （div[aria-label=显示设置]）都把可译属性写在自身上，此前从未被翻
       译过。把 root 并入待处理列表。 */
    const attrTargets = [root, ...root.querySelectorAll("*")].filter(
      (el) => el && el.nodeType === 1,
    );
    attrTargets.forEach((el) => {
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
    } catch (err) {
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
    /* 显示**当前语言**，和右上角的日夜按钮同一条约定（那里的注释写明
       "显示的是当前状态而不是将要切到什么"）。之前这里显示的是"点了会切
       成什么"，于是中文页面挂着一个 EN —— 两个按钮读的是相反的语义。
       aria 才是读屏需要的"点下去会发生什么"，所以它保持动作描述。 */
    const label = current === "en" ? "EN" : "中文";
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
