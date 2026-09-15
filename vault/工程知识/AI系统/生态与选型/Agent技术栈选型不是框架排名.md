---
title: Agent 技术栈选型不是框架排名
type: decision
updated: 2026-09-03
change_rate: fast
confidence: high
review_after: 2026-10-03
tags:
  - agent-engineering/frameworks
  - agent-engineering/architecture
sources:
  - "https://github.com/openai/openai-agents-python"
  - "https://github.com/langchain-ai/langgraph"
  - "https://github.com/google/adk-python"
  - "https://github.com/microsoft/agent-framework"
---

# Agent 技术栈选型不是框架排名

“哪个 Agent 框架最好”没有脱离任务的答案。不同工具覆盖 Provider 接口、Agent 循环、图式编排、知识接入、持久执行和观测中的不同部分。选型应从自己必须拥有的运行语义开始，再判断哪些实现值得外包。

## 先画系统，再看框架

在比较产品前写出：任务状态、控制流、工具契约、持久化边界、人工审批、失败模型、评测和部署约束。框架只能降低这些能力的实现成本，不能替你定义正确语义。

| 层 | 常见实现 | 采用时重点比较 |
| --- | --- | --- |
| 模型接入 | Provider SDK、统一适配层 | 错误、流式、工具、结构输出、状态接口 |
| Agent loop | Agents SDK、轻量自研循环 | 最大轮次、工具执行、handoff、guardrail |
| 编排 | 图/事件工作流 | checkpoint、暂停、并发、恢复和版本迁移 |
| 数据与检索 | RAG 框架、搜索与数据库 | 解析、索引、ACL、重排和引用 |
| 持久任务 | workflow engine、队列 | exactly-once 假设、幂等、补偿、长等待 |
| 观测评测 | trace/eval 平台 | 数据所有权、开放格式、回放和 grader |

一套框架覆盖的层越多，初期集成越快，迁移和隐式语义风险也越大。

## 三种常见起点

### 薄 SDK + 自有应用层

适合流程较短、团队已有成熟后端基础设施、希望保持 Provider 或框架可替换。模型、工具和 trace 用 SDK，状态、权限和业务流留在自己的代码。代价是需要自己实现循环和适配。

### Agent SDK

适合需要现成工具循环、handoff、guardrail、session 和 tracing，但任务仍主要在单次服务或较短运行内。必须确认 SDK 的 session 不被误用为业务状态，tool guardrail 是否覆盖所有调用路径，以及 provider 绑定程度。

### 图式或持久编排运行时

适合长任务、显式分支、暂停恢复、人工介入和并发。重点验证 checkpoint 的重放语义、节点副作用、状态 schema 迁移和生产运维，而不是只看节点 API 是否易写。

## 比较框架的十个问题

1. 状态由谁定义，能否使用业务类型而不是框架消息对象？
2. 中断后从节点前、节点内还是节点后恢复？副作用会不会重放？
3. 工具执行、审批和错误是否能替换成自己的实现？
4. 能否锁定模型、提示词、工具 schema 和工作流版本？
5. trace 是否覆盖模型、检索、工具、状态和人工步骤？
6. 测试时能否使用确定性模型和内存执行器？
7. provider、存储和观测能否替换，迁移出口是什么？
8. 序列化格式升级后，旧 checkpoint 如何恢复？
9. 依赖失败、取消、限流和部分成功如何表达？
10. 许可证、维护状态、安全公告和 release cadence 是否符合团队能力？

## 当前实现层

截至 2026-09-03，OpenAI Agents SDK、LangGraph、Google ADK 和 Microsoft Agent Framework 都在活跃演进，但定位不同。当前版本与迁移状态见 [[工程知识/AI系统/生态与选型/AI技术动态]]，不在本页做永久排名。

已经停服、被替代或进入维护状态的产品不能继续作为新架构默认项：Assistants API 已下线，OpenAI Swarm 已被 Agents SDK 取代，Microsoft AutoGen 进入维护模式。历史代码需要迁移，但它们仍可作为设计演进证据。

## 最小采用实验

选两个真实任务实现纵向切片：一个普通成功路径，一个包含工具超时、人工暂停和恢复的失败路径。测量代码复杂度、状态可见性、故障定位、恢复正确性、测试难度和迁移出口。框架减少的样板代码如果换来了无法解释的状态语义，不是净收益。

相关：[[工程知识/AI系统/Agent与工作流/模型负责判断，运行时负责执行语义]] · [[工程知识/AI系统/生态与选型/MCP连接能力，A2A委托任务]]
