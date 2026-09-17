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
  const DEFAULT_LANG = "en";
  const SUPPORTED = ["en", "zh"];

  /* ── Dictionary ───────────────────────────────────────────────────────────
   * zh is the source language: the value is what the page already says.
   * Keeping both sides in one object means a missing translation is visible
   * by inspection rather than by switching languages and hunting.
   */
  const DICT = {
    // ── Navigation ──
    "知识库": { en: "Knowledge" },
    "知识图谱": { en: "Graph" },
    "项目与教学": { en: "Projects & Learning" },
    "Agent 评估": { en: "Agent Evaluation" },
    "访问与反馈": { en: "Visits & Feedback" },
    "学习中心": { en: "Learning" },
    "我的课堂": { en: "Classrooms" },
    "学习": { en: "Learning" },
    "当前位置": { en: "Current page" },
    "退出": { en: "Sign out" },
    "目录": { en: "Menu" },

    // ── Brand ──
    "工程知识库": { en: "Engineering Knowledge" },
    "技术知识图谱": { en: "Technical knowledge graph" },
    "返回工程知识库": { en: "Back to the knowledge base" },

    // ── Theme + feedback controls ──
    "夜晚模式": { en: "Dark mode" },
    "白天模式": { en: "Light mode" },
    "提意见": { en: "Feedback" },
    "提意见 / 报告问题": { en: "Send feedback or report a problem" },
    "提意见或报告问题": { en: "Send feedback or report a problem" },
    "提个意见": { en: "Send feedback" },
    "这一页哪里说错了、看不懂、或者缺什么，都可以说。反馈只存在本机。": {
      en: "Say what is wrong, unclear, or missing on this page. Feedback stays on this machine.",
    },
    "反馈类型": { en: "Kind of feedback" },
    "内容有错": { en: "Something is wrong" },
    "看不懂": { en: "Hard to follow" },
    "想加点什么": { en: "Missing something" },
    "这页有用": { en: "This helped" },
    "具体说说": { en: "Details" },
    "怎么称呼你（可不填）": { en: "Your name (optional)" },
    "企微中文名或英文名，方便我回复你": { en: "So I can reply to you" },
    "企微中文名或英文名": { en: "Name or handle" },
    "取消": { en: "Cancel" },
    "发送": { en: "Send" },
    "正在发送…": { en: "Sending…" },
    "请先写点内容。": { en: "Write something first." },
    "收到，谢谢反馈！": { en: "Got it, thanks." },
    "发送失败": { en: "Could not send" },
    "当前页面：首页": { en: "Current page: home" },
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
    "保留资料": { en: "Kept for reference" },
    "查看键盘快捷键": { en: "Keyboard shortcuts" },
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
    "每篇都按这四件事写": { en: "Every note covers four things" },
    "背景": { en: "Context" },
    "方案": { en: "Approach" },
    "效果": { en: "Effect" },
    "优缺点": { en: "Trade-offs" },
    "写作约定": { en: "Writing rules" },
    "来源与更新": { en: "Sources and updates" },
    "知识领域": { en: "Domains" },
    "学习与实践": { en: "Learning and practice" },
    "评估与工程": { en: "Evaluation and engineering" },
    "辅助理解": { en: "Optional aids" },
    "保留资料": { en: "Archive" },
    "写作约定来源与更新": { en: "Writing rules · Sources and updates" },

    // ── Domain descriptions ──
    "AI系统": { en: "AI systems" },
    "后端与分布式系统": { en: "Backend and distributed systems" },
    "数据系统": { en: "Data systems" },
    "计算机系统与性能": { en: "Computer systems and performance" },
    "软件构建与质量": { en: "Software construction and quality" },
    "知识库管理": { en: "Knowledge base upkeep" },
    "总览": { en: "Overview" },
    "篇": { en: "notes" },
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
    "互动课堂可用": { en: "Classroom ready" },
    "学习导师可用": { en: "Tutor ready" },
    "服务运行中": { en: "Service up" },
    "未启动": { en: "Not running" },
    "互动课堂可用": { en: "Classroom ready" },
    "导师可用": { en: "Tutor ready" },
    "配置不完整": { en: "Incomplete setup" },
    "查看": { en: "View" },
    "打开": { en: "Open" },
    "完整使用指南": { en: "Full guide" },
    "实现与边界": { en: "How it works, and its limits" },
    "中文说明": { en: "Chinese README" },
    "查看写作契约": { en: "Writing contract" },
    "查看反馈机制": { en: "Feedback mechanism" },
    "查看自研项目": { en: "Open the project" },
    "创建课堂": { en: "Create a classroom" },
    "进入学习导师": { en: "Open the tutor" },
    "打开学习中心": { en: "Open Learning" },
    "回到知识库": { en: "Back to Knowledge" },
    "查看项目与教学": { en: "Projects and learning" },
    "查看知识图谱": { en: "Open the graph" },
    "打开课堂历史": { en: "Classroom history" },
    "打开项目入口": { en: "Projects" },
    "查看收录方式": { en: "How notes get filed" },
    "先看使用说明": { en: "Read the guide first" },
    "为什么不能只信 Agent 的总结": { en: "Why an agent's summary is not evidence" },
    "为什么不能只信Agent的总结": { en: "Why an agent's summary is not evidence" },

    // ── Projects page ──
    "项目与教学入口": { en: "Projects and learning" },
    "这里解决什么问题": { en: "What this page is for" },
    "访问方式": { en: "How to get in" },
    "怎么用": { en: "How to use it" },
    "学习产品": { en: "Learning tools" },
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
    "从本页「打开课堂」，主题会带过去。": { en: "Use “Open classroom” above; the topic carries over." },
    "从本页「进入学习导师」，会直接进对话界面。": {
      en: "Use “Open the tutor” above; it goes straight to the chat.",
    },
    "读文章、搜索、看图谱都不花钱。只有让工具生成内容时会调用模型 —— 这一步永远由你确认，页面不会自动发送。": {
      en: "Reading, searching and the graph are free. Only generation calls the model, and you confirm it every time.",
    },
    "手机或同事的电脑也能读这些知识，只是启动教学工具时需要密码。地址用 MacBook-Pro-2.local:8787，比记 IP 稳。": {
      en: "Phones and colleagues' machines can read the notes; starting a tool needs the password. Use MacBook-Pro-2.local:8787 — it survives an IP change.",
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
    "迁移验证": { en: "Transfer" },
    "选择主题": { en: "Pick a topic" },
    "检索与复习": { en: "Retrieve and review" },
    "把主题练成能力": { en: "Turn a topic into a capability" },
    "用课堂、追问、练习和迁移检验是否真的会用。": {
      en: "Classrooms, questioning, practice and transfer, to check you can actually use it.",
    },

    // ── Insights ──
    "访问与反馈": { en: "Visits and feedback" },
    "仅本机可见": { en: "This machine only" },
    "谁读过这个知识库、读了什么、提了什么意见。数据只存在本机 data/ 目录，不进版本库、不外发。这一页也只对本机开放 —— 其他设备即使有站点密码也读不到。": {
      en: "Who read this knowledge base, what they read, and what they said. Data stays in the local data/ directory — not committed, not sent anywhere. This page is likewise this machine only.",
    },
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
    "待处理": { en: "Open" },
    "已读": { en: "Read" },
    "已处理": { en: "Done" },
    "本机": { en: "local" },
    "刷新": { en: "Refresh" },
    "回到知识库": { en: "Back to Knowledge" },
    "其他": { en: "Other" },
    "（未指定文章）": { en: "(no article)" },
    "暂无反馈。": { en: "No feedback yet." },
    "暂无访问记录。": { en: "No visits recorded yet." },
    "谁读过、提了什么": { en: "Who read what, and what they said" },
    "本机访问记录与读者反馈，只在这台机器上可见。": {
      en: "Local visit log and reader feedback — visible on this machine only.",
    },
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
    translateDOM();
    document.querySelectorAll("[data-tk-lang-label]").forEach((node) => {
      node.textContent = lang === "en" ? "中文" : "EN";
    });
    document.querySelectorAll("[data-tk-lang-toggle]").forEach((node) => {
      node.setAttribute("aria-label", lang === "en" ? "切换为中文" : "Switch to English");
      node.setAttribute("title", lang === "en" ? "切换为中文" : "Switch to English");
    });
    document.dispatchEvent(new CustomEvent("tk:lang", { detail: { lang } }));
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
    root.querySelectorAll("[data-tk-lang-label]").forEach((node) => {
      node.textContent = current === "en" ? "中文" : "EN";
    });
  };

  window.TKI18N = {
    t,
    sourceOf,
    setLang,
    toggleLang,
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
