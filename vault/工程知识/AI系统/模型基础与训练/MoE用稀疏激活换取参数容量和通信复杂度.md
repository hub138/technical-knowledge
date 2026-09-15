---
title: MoE 用稀疏激活换取参数容量和通信复杂度
type: concept
status: active
updated: 2026-09-03
review_after: 2026-12-03
change_rate: medium
confidence: high
tags:
  - ai/models
  - ai/moe
  - ai/distributed
sources:
  - "https://arxiv.org/abs/1701.06538"
  - "https://arxiv.org/abs/2101.03961"
  - "https://arxiv.org/abs/2401.04088"
---

# MoE 用稀疏激活换取参数容量和通信复杂度

MoE 解决的是在每 token 计算预算有限时扩大参数容量，但把成本转移到 router、专家负载平衡和跨设备通信。最小对照是固定 batch 和质量目标，比较 dense 与 MoE 在单卡、同机多卡和跨节点的每 token 成本。
MoE 解决的是在每 token 计算预算有限时扩大参数容量，但它把成本转移到 router、专家负载平衡和跨设备通信。只有当稀疏计算节省的时间大于 dispatch、all-to-all 和权重驻留成本时，参数规模优势才会变成服务吞吐。

Mixture-of-Experts 在每层放置多个专家，由 router 为每个 token 选择少数专家。总参数可以增加而每个 token 只激活一部分，但 token dispatch、专家负载、容量限制和跨卡 all-to-all 通信成为新的瓶颈。

## 关键机制

- router logits 选择 top-k 专家；capacity factor 限制单专家可接收 token 数。
- load-balancing loss 防止少数专家过热；token overflow 可能被丢弃或转发，影响质量。
- expert parallel 把专家分布到设备；网络拓扑和 batch 形状决定通信效率。
- 训练和推理的路由、缓存、量化与故障处理不完全相同。

## 常见误判

激活参数少不等于显存少：权重可能仍需驻留或频繁加载；FLOPs 少不等于延迟低：all-to-all、负载倾斜和小 batch 会吞掉收益。专家专门化也不保证解释性或领域隔离。

## 验证

按 token 统计 expert load、overflow/drop、通信量、GPU 利用率、p99、质量和成本；注入热点路由、节点故障、不同 batch/序列长度和拓扑变化。比较 dense 基线时固定模型质量和推理服务 SLO。

最小对照：固定模型质量目标和总 batch，比较 dense 与 MoE 在单卡、同机多卡、跨节点部署下的每 token 成本。若跨节点通信吞掉稀疏收益，应优先改变专家放置或并行度，而不是继续增加专家数量。

关系：[[工程知识/AI系统/模型基础与训练/分布式训练与并行策略如何切分模型]] · [[工程知识/AI系统/推理服务与平台/模型服务架构从单进程到分布式副本]]
