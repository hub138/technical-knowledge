---
title: Prefill 与 Decode 决定 LLM 服务如何调度
status: active
type: concept
updated: 2026-09-03
change_rate: medium
confidence: high
review_after: 2027-03-03
tags:
  - ai/serving
  - ai/scheduling
sources:
  - "https://docs.vllm.ai/en/latest/"
  - "https://docs.nvidia.com/dynamo/latest/architecture/disaggregated_serving.html"
---

# Prefill 与 Decode 决定 LLM 服务如何调度

Prefill 处理输入上下文，计算密集且可以批量；Decode 逐 token 生成，反复读取权重和 KV cache，更容易受带宽、显存和调度影响。把两者混在一个队列会让长输入阻塞交互请求，所以调度必须用 TTFT、ITL、token 预算和 KV 占用共同决策。
生成一个响应包含两个不同阶段。Prefill 一次处理输入序列并建立 KV cache，通常具有较高并行度和计算压力；decode 每一步只生成少量 token，却要反复读取已有 KV cache，往往更受显存带宽和调度开销约束。

## 两个阶段为何互相干扰

```text
长 prompt 的 prefill 进入同一批次
          ↓
占用较长 GPU 时间
          ↓
已有 decode 请求等待下一步
          ↓
用户看到 token 间隔突然变长
```

反过来，如果调度器永远优先 decode，新的长输入可能长期拿不到 prefill 机会，TTFT 恶化。因此调度目标不是简单“填满 GPU”，而是在首 token 和连续输出之间分配有限时间、显存与批次位置。

## 连续批处理与分块 prefill

传统静态批处理等整批请求结束后再换批，短请求会被长请求拖住。连续批处理在序列完成时立即替换新序列，使批次随 decode 步动态变化。

分块 prefill 将长输入切分，在同一调度周期内与 decode token 交错。它可以降低长 prompt 对 ITL 的阻塞，但会增加调度复杂度，chunk 大小也会改变 TTFT、吞吐和 kernel 效率。合理参数必须由真实长度分布和 SLO 决定。

## 是否分离 prefill 与 decode

将两个阶段放到独立 worker 池，可以分别扩缩、选择并行策略，并隔离长 prefill 对 decode 的干扰。但 KV cache 必须从 prefill worker 高效传给 decode worker，新增网络、序列化、路由、故障和容量规划成本。

适合考虑分离的条件：

- 输入很长且长度差异大，prefill 明显破坏 ITL；
- prefill 与 decode 需要不同并行度或硬件配置；
- KV 传输足够快，收益大于跨节点开销；
- 流量规模足以让两个池都保持合理利用率。

流量小、请求短或互联慢时，共置通常更简单。分离是针对已测得干扰的架构选择，不是成熟度标签。

## 调度必须显式处理

| 问题 | 需要的策略 |
| --- | --- |
| 请求长度差异 | token 预算、分块 prefill、长度感知队列 |
| 优先级 | 配额与老化，避免低优先级永久饥饿 |
| KV cache 不足 | 拒绝/排队、抢占、换出或重算，并记录代价 |
| 多租户 | 并发、token、费用和显存预算按租户隔离 |
| 超时与取消 | deadline 传播，及时释放队列位置和 KV 块 |
| 流式输出 | 发送背压不能无限占住 decode 状态 |

## 验证方法

用短输入短输出、长输入短输出、短输入长输出、长输入长输出四个象限测试；再混合成真实到达分布。分别比较 TTFT、ITL、吞吐、KV 使用、抢占/重算次数和各优先级等待时间。单一固定长度 benchmark 无法证明调度器在生产流量下有效。

相关：[[工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/推理服务的核心矛盾是延迟、吞吐、显存与质量]] · [[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/调度必须同时处理优先级、公平与背压]]
