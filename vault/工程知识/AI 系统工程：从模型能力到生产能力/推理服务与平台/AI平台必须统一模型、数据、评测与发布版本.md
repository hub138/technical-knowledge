---
title: AI 平台必须统一模型、数据、评测与发布版本
status: active
type: architecture
updated: 2026-09-03
change_rate: medium
confidence: high
review_after: 2027-03-03
tags:
  - ai/platform
  - mlops
sources:
  - "https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/"
  - "https://docs.ray.io/en/latest/serve/production-guide/index.html"
  - "https://mlflow.org/docs/latest/ml/model-registry/"
---

# AI 平台必须统一模型、数据、评测与发布版本

AI 平台要解决的是模型、索引、prompt、工具和评测各自发布，最后无法解释线上结果来自哪一组输入。核心机制是把这些对象绑定成可重放发布单元，再通过灰度、观测和回滚改变版本；收益是问题可定位、改动可比较，代价是注册、存储和发布门禁复杂度增加。
AI 服务的一个“版本”从来不只是模型文件。实际行为由模型、推理参数、prompt、工具、检索索引、业务代码和安全策略共同决定。只记录镜像 tag，无法解释回归，也无法可靠回滚。

## 可重放发布单元

```yaml
release:
  application_revision: git-sha
  model:
    provider: provider-name
    name: model-name
    snapshot: immutable-id
    serving_runtime: runtime-version
    quantization: format-and-calibration
  context:
    prompt_version: prompt-v7
    tool_schema_version: tools-v4
    retrieval_index: corpus-2026-08-31@embedding-v3
  policy:
    authorization: policy-v5
    guardrails: guardrails-v2
  evaluation:
    suite: support-prod-v12
    result: eval-run-id
```

版本引用必须不可变；“latest”只能用于发现候选，不能用于证明一次线上行为。

## 控制面与数据面

控制面管理模型注册、发布策略、容量、路由、配额和回滚；数据面实际处理请求、检索、模型推理和工具执行。两者分离后，控制面故障不应立刻中断已部署服务，数据面也不能自行改变授权或发布版本。

~~~mermaid
flowchart LR
    R[版本注册与评测结果] --> C[发布控制面]
    C --> G[流量路由与配额]
    G --> D1[推理副本 A]
    G --> D2[推理副本 B]
    D1 --> O[Trace、SLO、质量反馈]
    D2 --> O
    O --> C
~~~

Kubernetes 能调度 GPU、维护副本和执行滚动发布，但不了解模型质量、KV cache 容量、token SLO 或 prompt 兼容性。Ray Serve、vLLM、TensorRT-LLM 等可以承担部分服务与运行时能力，也仍需应用定义版本、评测和回滚门禁。

## 发布流程

1. 离线回归：任务结果、检索、工具、安全、延迟和成本同时过线。
2. 影子流量：新版本处理真实输入但不影响用户，比较分布和资源。
3. 小流量灰度：按稳定主体分桶，避免同一会话跨版本漂移。
4. 逐步放量：每一步都有最短观察窗口和自动停止条件。
5. 回滚：恢复完整发布单元；若索引或数据 schema 不兼容，需要双读/双写或向后兼容期。

## 多模型路由

路由可以按任务、风险、模态、上下文长度、延迟预算和成本选择模型。路由器本身也要版本化和评测。最便宜模型不一定带来最低总成本：更差的工具选择、更长轨迹和更高重试率可能抵消单次 token 价格。

## 容量与故障

- 预热模型和关键 kernel，冷启动不能混入稳态 SLO。
- 扩缩容同时看队列、token 速率、KV cache 和长尾，不只看 GPU 利用率。
- Provider 或集群故障的回退要验证模型能力、数据边界和输出约定是否兼容。
- 取消、限流和 admission control 要在耗尽显存前生效。
- 日志、prompt 和检索内容按敏感度采集，不能为了可观测性复制全部业务数据。

相关：[[工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/推理服务的核心矛盾是延迟、吞吐、显存与质量]] · [[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/发布门禁必须绑定真实证据]]

验证的锚点：发布单元要与版本四元组对账——预写给定一个运行版本应能还原模型、数据、评测与代码四个版本，任一项还原不出，与预期对不上，该发布不算可重放。

## 要解决的问题

模型、索引、提示词、工具与评测集各自独立发布，线上结果出现变化时无法判断是其中哪一项改动的结果，也无法在原条件下重现。本篇回答：这些对象怎样绑定成一次可重放的发布单元、灰度与观测按什么粒度进行、回滚要恢复哪些对象，以及版本注册带来的开销由哪些环节承担。

