---
title: AI 技术动态
status: active
type: radar
updated: 2026-09-23
review_after: 2026-10-23
change_rate: fast
confidence: high
tags:
  - ai/radar
  - ai/serving
  - ai/agents
sources:
  - "Agent应用工程技术核验（来源层档案，已脱敏）]"
  - "https://developers.openai.com/api/docs/deprecations"
  - "https://developers.openai.com/api/docs/assistants/migration"
  - "https://modelcontextprotocol.io/specification/2026-07-28"
  - "https://blog.modelcontextprotocol.io/posts/2026-07-28"
  - "https://a2a-protocol.org/latest/"
  - "https://docs.langchain.com/oss/python/langgraph/overview"
  - "https://learn.microsoft.com/en-us/agent-framework/"
  - "https://github.com/vllm-project/vllm/releases/tag/v0.29.0"
  - "https://github.com/vllm-project/vllm/releases/tag/v0.30.0"
  - "https://docs.vllm.ai/en/latest/"
  - "https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/"
  - "https://opentelemetry.io/docs/specs/semconv/how-to-write-conventions/"
---

# AI 技术动态

> 当前快照：**2026-09-23**。这里放会影响近期工程选择的实现事实；原理和判断方法留在主题页。

本页记录会快速失效、且已经影响工程选择的实现状态。稳定原理留在对应主题页；模型、框架和推理引擎的宣传性能不能直接外推到自己的数据、硬件与流量。下一批已公布的硬时间点：**10 月 23 日**（OpenAI 最大一批模型下线）、**11 月 30 日**（Evals/Agent Builder/可复用提示词下线）、vLLM 计划在 **v0.32** 移除 Model Runner V1。

## Agent 与互操作

| 对象 | 截至 2026-09-23 的状态 | 工程动作 |
| --- | --- | --- |
| OpenAI Responses API | 当前新集成主接口；Conversations API 承接会话状态 | 记录实际模型快照；Provider 状态不作为唯一业务状态 |
| OpenAI Assistants API | 2026-08-26 已下线，端点返回 404；Threads 历史读取同时失效 | 删除残留依赖；提示词、instructions 和工具定义必须有平台外的副本 |
| OpenAI 弃用时间表 | 09-24 sora-2/Videos API 下线（无官方替代）；09-28 遗留 instruct/completions 模型 → gpt-5.6-terra；10-23 gpt-4/gpt-3.5-turbo/o1/o3-mini/o4-mini/gpt-image-1 及其微调版本 → gpt-5.6 系列；11-30 Evals 平台、Agent Builder、v1/prompts；12-11 gpt-5-2025-08-07 快照与 o3/o3-pro → gpt-5.6 系列 | 清点仓库与配置里写死的模型字符串；10-23 这批波及 2023-2025 年教程代码和全部基于 gpt-4 的微调资产，迁移是重训项目，改字符串解决不了 |
| OpenAI Agents SDK Python | 0.x 快速演进；官方文档持续覆盖 Runner、tools、guardrails、handoffs、sessions、sandbox、tracing 与 testing | 锁定实际版本，回归工具、状态序列化、guardrail、trace 和测试夹具 |
| MCP | 规范 2026-07-28：无状态核心、MRTR、Mcp-Method/Mcp-Name 路由头；EMA（企业统一授权）扩展已稳定；Roots/Sampling/Logging 弃用，保底 12 个月窗口 | 新实现采用无状态核心；确认错误码变化（缺失资源从 -32002 改为标准 -32602）；不要再在 Roots/Sampling/Logging 上建新功能 |
| A2A | 已发布规范 1.0.0；协议兼容性使用 1.0，仓库 patch 修订另行核验 | 回归 Agent Card、任务状态、认证、取消与协议绑定 |
| LangGraph Python | 官方文档持续维护，版本快速迭代 | 锁定仓库实际版本，重点验证 checkpoint 重放、副作用和状态迁移 |
| Google ADK Python | 官方文档与 SDK 持续迭代 | 锁定仓库实际版本，评估 workflow、memory、MCP/A2A 与部署耦合 |
| Microsoft Agent Framework Python | 官方提供从 AutoGen 迁移的路径，仍在快速迭代 | 新项目先做能力与兼容性评估；旧 AutoGen 先建立迁移回归集 |
| OpenTelemetry GenAI 约定 | Development | 内部 schema 保持稳定，在适配层映射实验字段 |

版本和状态的逐项一手来源见 Agent应用工程技术核验（来源层档案，已脱敏）]。

## 检索与 RAG

| 对象 | 当前工程判断 | 采用时真正要验证 |
| --- | --- | --- |
| 倒排 + 向量混合检索 | 仍是多数知识问答的可解释基线；RRF 可按排名融合不同量纲的结果 | 目标问题分桶、候选召回、重复去除、过滤顺序和 `rank_constant` |
| Cross-Encoder / late interaction | 适合在小候选集上做精排；不是全库检索的替代品 | top-K、批处理、p95 延迟、语言/领域迁移、分数校准与引用覆盖 |
| 查询改写与 Agentic retrieval | 处理多轮、省略、多跳和证据缺口；会增加循环与成本 | 原问题保留、最大轮数、停止条件、来源污染和无答案行为 |
| AutoRAG 类 AutoML | 用自己的问题集自动比较切分、召回、重排、prompt 和生成组合；属于实验优化层 | 训练/保留集隔离、目标函数、成本/安全约束、可复现和回滚 |
| GraphRAG | 适合关系链和语料级全局主题；不应成为所有问题的默认路径 | 实体消歧、图更新、原文回指、构图成本和与 hybrid 基线的分桶收益 |
| 开放表格式（Iceberg/Delta/Hudi） | 为文档/事件摄取提供快照、事务、删除和增量读取；不是检索算法 | `source_version -> index_version -> evidence_id` 绑定、删除传播和多引擎一致性 |

RAG 的演进不是组件名称堆叠，而是证据选择、索引生命周期与自动实验的组合。详细边界见 [[工程知识/AI 系统工程：从模型能力到生产能力/知识与检索/检索从一次查询演进为有状态的证据获取]]。

## 推理后端与分布式服务

| 对象 | 截至 2026-09-23 的状态 | 采用时真正要验证 |
| --- | --- | --- |
| vLLM | v0.30.0（09-22）：Fast Start 权重缓存（`--load-format ipc_cache`，引擎常驻权重跳过冷加载）、引擎初始化提速（H200 上全流程 28.9s→8.2s）、DeepSeek-V4.1-Flash + FlashMLA V4.1（KV 全程 MXFP8）、HiSparse 显存吃紧时把 KV 页挪到主机内存。v0.29.0（09-09）：Model Runner V2 成为全模型默认，MRV1 弃用（目标 v0.32 移除）；入口改用 `vllm serve`（`python -m vllm.entrypoints.openai.api_server` 已弃用）；新增准入控制 `--max-num-queued-reqs` / `--max-num-queued-tokens`，过载时提前返回而不是队列里烂掉；移除十个旧模型架构 | 升级前用 0.28 基准环境跑相同 prompt/并行度/量化对比 TTFT、ITL、OOM 与工具调用正确率；部署脚本里还在用旧入口的先改；MRV1 余量只覆盖少数 ROCm 路径 |
| TensorRT-LLM | 面向 NVIDIA GPU 的编译、kernel、量化、KV cache 与高性能运行时 | 构建时间、硬件绑定、数值质量、可观测性与目标 workload 收益 |
| SGLang | 提供结构化生成、缓存与高吞吐模型服务能力，可接入分离式部署 | 模型兼容、调度、缓存命中、稳定性和团队维护成本 |
| NVIDIA Dynamo | 面向多节点推理的数据中心级编排与路由，覆盖 prefill/decode 分离和 KV 传输 | 互联拓扑、KV 传输、两个 worker 池的扩缩比例和故障恢复 |
| Ray Serve LLM | 在推理引擎之上提供多节点放置、路由、扩缩、模型复用与服务组合 | 队列驱动扩缩是否适合 token workload、冷启动、placement 与控制面复杂度 |
| Kubernetes GPU 调度 | 通过 device plugin 暴露和分配 GPU 等扩展资源 | 设备发现、拓扑、健康、碎片、队列和模型 SLO 仍需上层处理 |

[vLLM v0.30.0 发布说明](https://github.com/vllm-project/vllm/releases/tag/v0.30.0) · [vLLM v0.29.0 发布说明](https://github.com/vllm-project/vllm/releases/tag/v0.29.0) · [vLLM 官方文档](https://docs.vllm.ai/en/latest/) · [TensorRT-LLM 官方文档](https://nvidia.github.io/TensorRT-LLM/) · [NVIDIA Dynamo 分离式服务](https://docs.nvidia.com/dynamo/dev/knowledge-base/concepts/system-architecture/disaggregated-serving) · [Ray Serve LLM](https://docs.ray.io/en/latest/serve/llm/) · [Kubernetes GPU 调度](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)

推理引擎优化单个模型实例，服务框架处理副本、路由和扩缩，Kubernetes 管理资源放置，平台层负责版本、评测与发布。它们可以组合，但不能用后一层掩盖前一层的容量瓶颈。完整关系见 [[工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/AI平台必须统一模型、数据、评测与发布版本]]。

## 已经成立的趋势与仍需证明的选择

| 变化 | 已经成立的工程事实 | 仍需用本地实验回答 |
| --- | --- | --- |
| Continuous batching | 动态填充活动序列比固定批次更适合长度不一的生成请求 | 在目标长度分布下的 TTFT/ITL 与公平性 |
| Prefix/KV cache reuse | 共享前缀可减少重复 prefill，KV 分页可降低碎片 | 实际命中率、租户隔离、失效和显存收益 |
| Prefill/decode 分离 | 两阶段可独立放置和扩缩 | KV 传输成本是否低于隔离收益 |
| 低精度推理 | 权重或 KV 表示可降低容量和带宽压力 | 任务质量、kernel 支持和端到端成本 |
| 多模型/LoRA 复用 | 共享基座可减少大量稀疏模型副本 | 加载抖动、缓存淘汰、路由和隔离 |
| Agentic retrieval | 能按证据缺口继续检索 | 额外循环是否提高真实任务成功率 |
| 推理引擎常驻权重 | vLLM Fast Start 证明重启成本可以压到秒级 | 常驻显存占用与多模型轮换的收益边界 |

## 进入观察而不是默认采用

| 技术 | 为什么有价值 | 为什么不应成为默认架构 |
| --- | --- | --- |
| Agentic retrieval | 能根据证据缺口动态选择查询和来源 | 增加循环、延迟、成本和来源污染风险 |
| GraphRAG | 改善全局主题和关系型查询 | 图构建、更新和实体消歧成本高，非所有问题受益 |
| 多 Agent | 可隔离上下文、权限或并行专业任务 | 通信损失、状态同步和评测面显著增加 |
| 长上下文 | 减少部分预处理和检索步骤 | 容量不等于有效利用、时效、权限与来源治理 |
| 托管 Computer Use | 能覆盖无 API 的界面动作 | 易受界面变化和间接注入影响，验证与沙箱要求高 |
| 全量 prefill/decode 分离 | 能分别优化两阶段 | 短请求、低并发或慢互联下可能更慢、更复杂 |
| 过度张量并行 | 能容纳大模型 | 小批次通信可能超过计算收益，先用最小并行度 |
| 单一综合 AI 指标 | 看似便于比较版本 | 会掩盖质量、延迟、成本、安全和任务切片的冲突 |

这些能力只有在明确问题切片上优于简单基线时才进入生产。

## 需要立即复查的事件

- 模型、SDK、协议或框架发布破坏性版本；
- 正式弃用、下线日期或安全公告；
- 身份、授权、工具调用和数据保留语义改变；
- 状态、checkpoint、取消或恢复行为改变；
- 新评测显示当前方案在核心任务切片上系统性失效。

新模型名、单个 benchmark 提升、GitHub 热度或营销发布本身不足以改变架构。

## 维护方法

每次复查只更新事实行：对象、版本、发布日期、状态、迁移影响和一手链接。影响稳定原理时才修改核心主题页；只影响某个实现时，仅更新本页和对应采用记录。每周例行检查由 AI 定时任务执行，完整提示词见 [[工程知识/知识库管理/方法/AI技术动态每周更新任务]]。
