---
title: Matt Skills：让 AI 先理解再修改
type: project
exclude_from_graph: true
status: active
updated: 2026-09-04
review_after: 2026-10-04
change_rate: fast
confidence: high
sources:
  - "https://github.com/mattpocock/skills"
  - "https://skills.sh/mattpocock/skills"
tags:
  - agent-skills
  - software-engineering
  - workflow
---

# Matt Skills：让 AI 先理解再修改

Matt Pocock 的 Skills 仓库把软件工程中最容易被 Agent 跳过的环节，整理成可复用的调用入口：先对齐问题和术语，再形成规格，按小步反馈实施，最后用测试和审查确认结果。它不是一个新的 AI 框架，而是一套约束 Agent 工作方式的工程方法。

## 值得保留的能力

| 能力 | 解决的失控点 | 适合什么时候用 |
| --- | --- | --- |
| `ask-matt` | 不知道该走哪条工程流程 | 刚接到一个不清楚的改动请求 |
| `grill-with-docs` | 需求、术语和边界没有对齐 | 复杂功能或多人协作前 |
| `to-spec` / `to-tickets` | 讨论无法落成可执行任务 | 需要拆分范围和依赖时 |
| `tdd` / `implement` | 一次改太多，反馈太晚 | 需要稳定迭代和回归证据时 |
| `code-review` | 只看“能不能跑”，不看风险与规格 | 合并或交付前 |
| `improve-codebase-architecture` | Agent 让代码熵持续上升 | 定期寻找可深化的模块边界 |

## 在本知识库中的位置

这些技能属于“工程工作方式”，不应取代 AI 系统、后端、数据或性能等知识主题。它们的抽象价值是：把 Agent 的语义决策放在清楚的上下文中，把测试、运行结果和审查保留为外部证据。相关原则见 [[工程知识/AI系统/安全与治理/AI可以做语义决策，系统必须守住事实边界]]。

## 本地安装

本机副本：`/Users/leoqqian/Developer/knowledge-tools/mattpocock-skills`  
上游：<https://github.com/mattpocock/skills>  
当前版本以仓库 `main` 的提交为准，Codex/Agent Skills 使用 `~/.agents/skills` 与 `~/.codex/skills`，Cursor 使用 `~/.cursor/skills`。

更新时先检查上游变更，再运行安装脚本同步技能目录；不要把技能正文复制进知识笔记，保留仓库链接和当前版本即可。

## 关联

- [[知识库管理/归档/学习工具使用与调用成本.md]]
- [[知识库管理/归档/来源注册表.md]]
- [[工程知识/软件构建与质量/架构与代码/架构组织高成本决策与演进边界]]
