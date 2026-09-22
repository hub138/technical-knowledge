# apps/ 子页面新语法清理：可选链与空值合并改写为等价旧语法。
# 这些页面在旧手机 WebView 上同样会整块脚本失效，与主站同病同修。
BASE = "/data/code/AIagent/skills/knowledge-site/technical-knowledge/"

CTX = [
    "apps/agent-evaluation/index.html",
    "apps/learning/history.html",
    "apps/learning/index.html",
    "apps/learning/intuition.html",
    "apps/learning/openmaic.html",
    "apps/learning/transfer.html",
]

CONTEXT_PAIR = (
    """        where: () => '当前页面：<b>' + (document.querySelector('.tk-context h2')?.textContent.trim() || document.title) + '</b>',
        title: () => document.querySelector('.tk-context h2')?.textContent.trim() || document.title,""",
    """        where: () => '当前页面：<b>' + (((document.querySelector('.tk-context h2') || {}).textContent || '').trim() || document.title) + '</b>',
        title: () => ((document.querySelector('.tk-context h2') || {}).textContent || '').trim() || document.title,""",
)

# 每个 (path, [(old, new), ...])，old 必须在文件中存在；计数先行打印。
REPLACEMENTS = {
    "apps/learning/history.html": [
        ('          String(value ?? "").replace(/[&<>"\']/g, (char) => ({',
         '          String(value == null ? "" : value).replace(/[&<>"\']/g, (char) => ({'),
        ('              ? `${tr("场景")} ${job.scenesGenerated ?? 0}/${job.totalScenes}`',
         '              ? `${tr("场景")} ${(job.scenesGenerated != null ? job.scenesGenerated : 0)}/${job.totalScenes}`'),
    ],
    "apps/learning/index.html": [
        ('          event.detail?.lang === "en" &&',
         '          event.detail && event.detail.lang === "en" &&'),
        ('          event.detail?.lang === "zh" &&',
         '          event.detail && event.detail.lang === "zh" &&'),
        ('          document.querySelector(".topic-box")?.append(error);',
         '          { const topicBox = document.querySelector(".topic-box"); if (topicBox) topicBox.append(error); }'),
        ('      if (requestedTopic?.trim()) topic.value = requestedTopic.trim();',
         '      if (requestedTopic && requestedTopic.trim()) topic.value = requestedTopic.trim();'),
        ('          maic.textContent = status.openmaic?.online ? tr("运行中") : tr("未启动");',
         '          maic.textContent = status.openmaic && status.openmaic.online ? tr("运行中") : tr("未启动");'),
        ('          maic.classList.toggle("warn", !status.openmaic?.online);',
         '          maic.classList.toggle("warn", !(status.openmaic && status.openmaic.online));'),
        ('            status.deeptutor?.online && status.deeptutor?.llm',
         '            status.deeptutor && status.deeptutor.online && status.deeptutor.llm'),
        ('            !(status.deeptutor?.online && status.deeptutor?.llm),',
         '            !(status.deeptutor && status.deeptutor.online && status.deeptutor.llm),'),
        ('          limit.textContent = status.deeptutor?.embedding',
         '          limit.textContent = status.deeptutor && status.deeptutor.embedding'),
        ('          limit.classList.toggle("error", !status.deeptutor?.embedding);',
         '          limit.classList.toggle("error", !(status.deeptutor && status.deeptutor.embedding));'),
    ],
    "apps/learning/openmaic.html": [
        ('          const online = Boolean(status.openmaic?.online);',
         '          const online = Boolean(status.openmaic && status.openmaic.online);'),
    ],
}

for path in CTX:
    with open(BASE + path, encoding="utf-8") as f:
        text = f.read()
    pairs = []
    if CONTEXT_PAIR[0] in text:
        pairs.append(CONTEXT_PAIR)
    pairs.extend(REPLACEMENTS.get(path, []))
    for old, new in pairs:
        n = text.count(old)
        print(path, "count=", n, repr(old[:50]))
        text = text.replace(old, new)
    with open(BASE + path, "w", encoding="utf-8") as f:
        f.write(text)
print("done")
