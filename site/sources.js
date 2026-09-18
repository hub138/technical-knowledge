/* 外部资源清单。
 *
 * 为什么单独一个数据文件：这些站点会增删，改内容不该动页面结构。
 * nav.js 用同样的做法，理由相同。
 *
 * 每条必须写清「它补了什么」——只列链接和浏览器书签没区别。
 * 用户的原话是「我希望我的网站 要能把他们的好处都吸收」，
 * 所以 description 回答的是"这个站做到了我做不到的什么事"。
 *
 * 字段：
 *   name     站名（中文界面显示这个）
 *   url      地址，新标签页打开
 *   kind     一句话性质，灰色小字
 *   gain     它补了什么（这是这一页存在的理由）
 *   tags     能力标签，便于扫
 *   en       英文界面的 name / kind / gain；缺了会回退中文
 */
window.TK_SOURCES = {
  /* 分三层。顺序就是重要性顺序：知识文章 → 论文 → 资讯。
     用户明确说资讯类「不算知识」「放在最后吧」。 */
  groups: [
    {
      key: "reading",
      title: "知识文章",
      note: "成篇的、有人写过的内容。适合慢慢读，适合订阅。",
      items: [
        {
          name: "BestBlogs",
          url: "https://www.bestblogs.dev/reading/follow",
          kind: "中文技术公众号聚合",
          gain:
            "把散在几十个公众号里的优质文章聚到一处，自己选要跟哪些号。有今日更新和特别关注两个视角，标题可以速看——先把值得点开的挑出来，再决定读哪篇。中文技术阅读里目前做得最顺手的一个。",
          tags: ["公众号聚合", "今日更新", "自选订阅", "速看标题"],
          en: {
            name: "BestBlogs",
            kind: "Chinese tech writing, aggregated",
            gain:
              "Pulls good writing out of dozens of WeChat accounts into one place, and you choose which to follow. It has a today view and a highlights view, and the titles are scannable, so you pick what deserves a read before opening anything. The smoothest Chinese tech reading experience around.",
            tags: ["Aggregated", "Daily", "Self-selected", "Skimmable"],
          },
        },
        {
          name: "阮一峰的网络日志",
          url: "https://www.ruanyifeng.com/blog/index.html",
          kind: "个人技术博客",
          gain:
            "中文技术写作里口碑最稳的老站之一，每周一期「科技爱好者周刊」。价值在于长期不断更，而且作者会把一件事讲到他真懂为止，不追热点。",
          tags: ["长期更新", "周刊", "讲透"],
          en: {
            name: "Ruan Yifeng's blog",
            kind: "Personal tech blog",
            gain:
              "One of the most consistently respected long-running Chinese tech blogs, with a weekly digest. Its value is endurance: the author explains a thing until he genuinely understands it, and does not chase trends.",
            tags: ["Long-running", "Weekly", "Explains fully"],
          },
        },
      ],
    },
    {
      key: "papers",
      title: "论文",
      note: "一手研究。比二手解读更可信，但也更需要筛选和结构化。",
      items: [
        {
          name: "PaperNotes",
          url: "https://papernotes.org/",
          kind: "AI 顶会论文解读",
          gain:
            "两万多篇 AI 顶会论文的中文解读，按会议再按子领域组织，更新很快。覆盖面是单个知识库不可能企及的，所以论文的「发现」这一层基本可以交给它，本地只做「已经想明白的那几篇」。",
          tags: ["2.3 万篇", "按会议分类", "更新快"],
          en: {
            name: "PaperNotes",
            kind: "AI conference paper notes",
            gain:
              "Chinese notes on 23,000+ AI conference papers, organised by venue then subfield, updated fast. The coverage is beyond what one knowledge base can reach, so discovery can be left to it while this site keeps only the papers it has actually thought through.",
            tags: ["23k papers", "By venue", "Fast"],
          },
        },
        {
          name: "arXivDaily",
          url: "https://www.arxivdaily.com/",
          kind: "每日 arXiv 速递",
          gain:
            "每天把 arXiv 新提交的论文拉出来，带 AI 生成的中文摘要，可按学科、期刊、机构筛。价值是「不漏」——它不替你判断哪篇重要，但保证你看见今天出了什么。",
          tags: ["每日", "AI 摘要", "按机构筛"],
          en: {
            name: "arXivDaily",
            kind: "Daily arXiv digest",
            gain:
              "Pulls each day's new arXiv submissions with an AI-written Chinese abstract, filterable by field, journal and institution. Its value is completeness: it does not judge importance, but it does make sure you see what came out today.",
            tags: ["Daily", "AI abstracts", "By institution"],
          },
        },
        {
          name: "每日 AI 论文速递（播客）",
          url: "https://www.xiaoyuzhoufm.com/podcast/667d1ecfc13b46d76c3f64b8",
          kind: "播客 · HuggingFace 出品",
          gain:
            "同一批论文的音频版，每期十来分钟。读不了屏幕的时候（通勤、走路）能跟上进度——播客的强项不是精度，是它不占用眼睛，所以能和阅读并行。",
          tags: ["音频", "十分钟", "通勤可用"],
          en: {
            name: "Daily AI Paper Digest (podcast)",
            kind: "Podcast by HuggingFace",
            gain:
              "An audio version of the same stream, about ten minutes an episode. It keeps you current when you cannot look at a screen — its strength is not precision but that it frees your eyes, so it runs in parallel with reading.",
            tags: ["Audio", "10 minutes", "Commute-friendly"],
          },
        },
      ],
    },
    {
      key: "news",
      title: "资讯",
      note: "知道发生了什么。不等同于知识，也不该按知识的用法读。",
      items: [
        {
          name: "ReadHub",
          url: "https://readhub.cn/hot",
          kind: "科技新闻聚合",
          gain:
            "把当天科技圈的大事压成一句话一条，扫一眼就知道发生了什么。定位是「不漏掉大新闻」，不是「读懂一件事」。",
          tags: ["每日热点", "一句话一条"],
          en: {
            name: "ReadHub",
            kind: "Tech news aggregator",
            gain:
              "Compresses the day's tech news to a line each, so a quick scan tells you what happened. It is for not missing the big story, not for understanding one.",
            tags: ["Daily", "One line each"],
          },
        },
        {
          name: "泽丽 zeli",
          url: "https://zeli.app/zh",
          kind: "资讯聚合",
          gain:
            "同类资讯源，偏 Hacker News 一线。和 ReadHub 一起看能覆盖中英文两侧的注意力焦点，差异本身也有信息量。",
          tags: ["HN 一线", "中英对照"],
          en: {
            name: "zeli",
            kind: "News aggregator",
            gain:
              "The same job from the Hacker News side. Reading it alongside ReadHub covers both the Chinese and English attention, and the difference between them is itself informative.",
            tags: ["Hacker News", "EN + ZH"],
          },
        },
      ],
    },
  ],
};
