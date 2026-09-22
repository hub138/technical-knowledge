---
title: AI技术动态每周更新任务
status: active
type: workflow
updated: 2026-09-23
review_after: 2027-03-23
change_rate: slow
confidence: high
tags:
  - ai/radar
  - workflow
  - automation
sources:
  - "[[工程知识/AI 系统工程：从模型能力到生产能力/生态与选型/AI技术动态]]"
  - "[[工程知识/知识库管理/方法/一篇知识怎么写]]"
---

# AI技术动态每周更新任务

一个每周执行的 AI 定时任务：扫描一手来源，更新 [[工程知识/AI 系统工程：从模型能力到生产能力/生态与选型/AI技术动态]]，产出一周增量摘要。执行者是任意一个接了联网搜索的 Agent CLI，定时由外部调度器触发，本文档提供完整的调度命令与提示词。

## 为什么是周更

技术动态的实际变化节奏和内容供给是匹配的：协议修订以月计，推理引擎每两三周发一个版本，厂商弃用按季度成批公布。一周里真正影响工程选择的变化通常只有几条，日更会造成噪声，月更会错过下线日期。周更一次，每次更新都会在首页 digest 里露出"新内容"，读者每周都有新东西可看；已经收录的 BestBlogs 好文流负责日级别的及时性，两级互相不重复。

## 调度配置

用系统 crontab 触发（示例为每周一 09:00）：

```
0 9 * * 1 cd /path/to/technical-knowledge && python3 -m agent_foundation.cli_update --prompt-file scripts/radar_weekly_prompt.md >> logs/radar_weekly.log 2>&1
```

不依赖 cron 的环境里，用 `agent_foundation.ProcessSupervisor` 包一层超时与重试：

```python
from agent_foundation import ProcessSpec, ProcessSupervisor

result = ProcessSupervisor().run(
    ProcessSpec(
        ["your-agent-command", "--prompt-file", "scripts/radar_weekly_prompt.md"],
        hard_timeout_seconds=1800,
        idle_timeout_seconds=300,
    )
)
```

`agent_foundation` 只负责进程存活、超时回收、transcript 脱敏和指数退避；提示词在 `scripts/radar_weekly_prompt.md`，由各 Agent 适配器自行读取。

## 完整提示词

以下内容存为 `scripts/radar_weekly_prompt.md`，原样发给执行任务的 Agent：

````markdown
# 任务：更新《AI 技术动态》周度快照

今天是 {date}。你的工作是维护知识库里的雷达页：
vault/工程知识/AI 系统工程：从模型能力到生产能力/生态与选型/AI技术动态.md

## 第一步：检查是否值得更新

先读这篇文章的 frontmatter（updated 字段）和「需要立即复查的事件」清单。

逐项检查以下来源，找自上次快照日期之后的新事实：

1. https://developers.openai.com/api/docs/deprecations —— 是否新增下线日期或迁移条目
2. https://modelcontextprotocol.io/specification/2026-07-28 与 https://blog.modelcontextprotocol.io —— 规范修订、SDK 大版本、扩展状态变化
3. https://a2a-protocol.org/latest/ —— 规范版本变化
4. https://github.com/vllm-project/vllm/releases —— 新版本与破坏性变更
5. https://docs.langchain.com/oss/python/langgraph/overview 与 https://learn.microsoft.com/en-us/agent-framework/ —— 框架重大变化

规则：只记录影响工程选择的事实（版本、日期、状态、迁移影响）。新模型名、benchmark 数字、融资新闻、产品宣传不收录。如果一周内没有任何一条满足收录标准，直接结束，不改动文件——空更新比错误更新更有害。

## 第二步：更新文章

对每条新事实：

1. 只改对应表格里的那一行：对象、版本、发布日期、状态、迁移影响、一手链接。禁止改写稳定原理段落，禁止调整文章结构。
2. 表格列口径必须保持：Agent 表是「对象 / 截至 {date} 的状态 / 工程动作」，推理引擎表是「对象 / 截至 {date} 的状态 / 采用时真正要验证」。快照日期变了，表头里的日期跟着变。
3. frontmatter：`updated` 改为今天，`review_after` 改为今天加 30 天，`sources` 只增不删。
4. 文章开头的快照日期和「下一批已公布的硬时间点」段落同步刷新；已过期的日期从那里移除。
5. 每条新事实必须带一手链接。二手转述（新闻、博客汇总）只能用来发现线索，不能作为行内事实的依据；无法到达一手来源的事实不写入。

## 第三步：产出一周增量摘要

更新完成后，把本周变化压缩成不超过 5 条的摘要，每条一行：

- 对象 + 事实 + 工程动作（例如：「vLLM v0.30.0 发布，Fast Start 权重缓存；升级前对比 TTFT/OOM 基准」）

摘要追加到 vault/知识库管理/归档/更新候选/待核验内容.md 的末尾，标题格式为「## {date} AI技术动态周报」。没有变化就不追加。

## 第四步：自检

提交前逐条确认：

- [ ] 每个改动行都有一手链接
- [ ] 表格列口径与前后行一致
- [ ] frontmatter 的 updated/review_after 已更新
- [ ] 没有改动任何稳定原理段落
- [ ] 待核验内容.md 里追加了周报（或确实无变化）

全部通过后，用一句话报告：更新了几行、新增了哪几条摘要。
````

## 变化少的那几周怎么办

收录标准卡在"影响工程选择"，一周里多数时候确实凑不满五条。摘要允许只写一条，也允许空——首页 digest 展示的是最近更新时间和增量条数，一条真实的变化比五条凑数的更有可信度。日级别的"新内容感"由 BestBlogs 好文流和论文区承担，雷达页只对"该动手了"的事件负责，两级互相不抢。

## 失败处理

- 来源站点不可达：跳过该来源，在周报末尾标注「{来源} 未核验」，禁止凭记忆补写。
- 任务超时：`ProcessSupervisor` 的硬超时回收进程，退避后重试一次；仍失败则本周跳过，下周快照照常滚动。
- 发现需要立即复查的事件（安全公告、破坏性变更）：不等周更，当次任务直接更新并在摘要里标为紧急。
