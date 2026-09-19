/* 外部资源清单。
 *
 * 为什么单独一个数据文件：这些站点会增删，改内容不该动页面结构。
 * nav.js 用同样的做法，理由相同。
 *
 * 字段：
 *   key         与 site/feeds.py 的 FEEDS[].key 对齐；有 key 才会有「最新几条」窗口。
 *               播客没有可抓的文字列表，所以 key 留空。
 *   name        站名（中文界面显示这个）
 *   url         地址，新标签页打开
 *   kind        一句话性质，灰色小字
 *   gain        读者看它的理由 —— 不是"它比谁强"，是"你能得到什么"
 *   tags        能力标签，便于扫
 *   en          英文界面的字段；缺了会回退中文
 */
window.TK_SOURCES = {
  /* 三组，按用途分。资讯放最后 —— 它是用来看动向的，
     和「读一篇东西」不是一回事。 */
  groups: [
    {
      key: "reading",
      title: "文章",
      note: "写完的完整文章。适合从头读到尾，也适合挑一节查。",
      items: [
        {
          key: "bestblogs",
          name: "BestBlogs",
          url: "https://www.bestblogs.dev/reading/follow",
          kind: "中文技术公众号聚合",
          gain:
            "把散在几十个技术公众号里的文章聚到一处，按方向筛。今天更新了什么、哪几篇值得点开，扫一遍标题就知道。",
          tags: ["公众号聚合", "今日更新", "自选订阅", "速看标题"],
          en: {
            name: "BestBlogs",
            kind: "Chinese tech writing, aggregated",
            gain:
              "Writing from dozens of Chinese tech accounts, gathered by what you follow. A scan of the titles tells you what is new today and what is worth opening, without visiting each one.",
            tags: ["Aggregated", "Daily", "Self-selected", "Skimmable"],
          },
        },
        {
          key: "ruanyifeng",
          name: "阮一峰的网络日志",
          url: "https://www.ruanyifeng.com/blog/index.html",
          kind: "个人技术博客",
          gain:
            "每周一期，把一周里值得看的科技内容挑出来讲。写得慢、讲得透，适合当周末的固定读物。",
          tags: ["周刊", "长期更新", "讲透"],
          en: {
            name: "Ruan Yifeng's blog",
            kind: "Personal tech blog",
            gain:
              "A weekly digest that picks out what was worth reading in tech that week. Written slowly and explained properly — a good standing weekend read.",
            tags: ["Weekly", "Long-running", "Explains fully"],
          },
        },
      ],
    },
    {
      key: "papers",
      title: "论文",
      note: "论文原文。结论最可靠，但得自己判断值不值得信。",
      items: [
        {
          key: "papernotes",
          name: "PaperNotes",
          url: "https://papernotes.org/",
          kind: "AI 顶会论文解读",
          gain:
            "两万多篇 AI 顶会论文的中文解读，每篇五分钟读完核心思想。按会议和子领域组织，找某个方向的工作比翻 arXiv 快。",
          tags: ["2.3 万篇", "五分钟一篇", "按会议分类"],
          en: {
            name: "PaperNotes",
            kind: "AI conference paper notes",
            gain:
              "Chinese write-ups of 23,000+ AI conference papers, five minutes each. Organised by venue then subfield; the latest additions are listed below. Faster than arXiv when you are looking for work in a specific area.",
            tags: ["23k papers", "5 min each", "By venue"],
          },
        },
        {
          key: "arxivdaily",
          name: "arXivDaily",
          url: "https://www.arxivdaily.com/",
          kind: "每日 arXiv 速递",
          gain:
            "每天新提交的 arXiv 论文，带中文摘要和作者机构。它不替你判断哪篇重要，但保证不漏掉今天出了什么。",
          tags: ["每日更新", "中文摘要", "按机构筛"],
          en: {
            name: "arXivDaily",
            kind: "Daily arXiv digest",
            gain:
              "Each day's new arXiv submissions with a Chinese abstract and affiliation, filterable by field and institution. It does not judge what matters, but it does mean you see what came out today.",
            tags: ["Daily", "Chinese abstracts", "By institution"],
          },
        },
        {
          // 播客没有可抓的文字列表，所以不配 feed 槽。
          key: "",
          name: "每日 AI 论文速递（播客）",
          url: "https://www.xiaoyuzhoufm.com/podcast/667d1ecfc13b46d76c3f64b8",
          kind: "播客 · HuggingFace 出品",
          gain:
            "同一批论文的音频版，每期十来分钟。通勤、走路时能跟上进度，不占用眼睛。",
          tags: ["音频", "每期十分钟", "通勤可用"],
          en: {
            name: "Daily AI Paper Digest (podcast)",
            kind: "Podcast by HuggingFace",
            gain:
              "An audio version of the same stream, about ten minutes an episode. Keeps you current while commuting or walking — it frees your eyes, so it runs alongside reading.",
            tags: ["Audio", "10 minutes", "Commute-friendly"],
          },
        },
      ],
    },
    {
      key: "news",
      title: "资讯",
      note: "行业动态。用来看方向，不适合当知识记住。",
      items: [
        {
          key: "readhub",
          name: "ReadHub",
          url: "https://readhub.cn/hot",
          kind: "科技新闻聚合",
          gain:
            "当天科技新闻压成一句话一条，扫一眼就知道发生了什么。用来不漏掉大事。",
          tags: ["24 小时热榜", "一句话一条"],
          en: {
            name: "ReadHub",
            kind: "Tech news aggregator",
            gain:
              "The day's tech news compressed to a line each, so one scan tells you what happened. For not missing the big story, not for understanding one.",
            tags: ["24h hot list", "One line each"],
          },
        },
        {
          key: "zeli",
          name: "泽丽 zeli",
          url: "https://zeli.app/zh",
          kind: "资讯聚合",
          gain:
            "偏 Hacker News 一线的资讯聚合。和 ReadHub 一起看，能同时覆盖中英文两边在关注什么。",
          tags: ["Hacker News", "中英两边"],
          en: {
            name: "zeli",
            kind: "News aggregator",
            gain:
              "Aggregated news from the Hacker News side. Read alongside ReadHub it covers what both the Chinese and English halves of the industry are paying attention to.",
            tags: ["Hacker News", "EN + ZH"],
          },
        },
      ],
    },
  ],
};
