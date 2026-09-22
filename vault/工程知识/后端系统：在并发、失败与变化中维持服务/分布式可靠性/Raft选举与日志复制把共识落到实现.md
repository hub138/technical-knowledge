---
title: Raft选举与日志复制把共识落到实现
type: concept
status: active
updated: 2026-09-21
review_after: 2027-09-21
change_rate: low
confidence: high
sources:
  - "https://raft.github.io/raft.pdf"
  - "https://raft.github.io/"
  - "https://github.com/etcd-io/raft"
tags:
  - distributed-systems/consensus
  - consensus
  - reliability
---

# Raft选举与日志复制把共识落到实现

共识要解决的问题：一组节点对"下一个值是什么"达成一致，即使部分节点宕机、网络分区。上层是抽象承诺（linearizability），落地是两个具体机制：leader 选举与日志复制。Raft 把 Paxos 难以工程化的部分拆成两个相对独立的过程，共识从论文走进了 etcd、Consul、TiKV 的生产实现。

## 机制一：选举

任期（term）是逻辑时钟：每个 term 至多一个 leader，term 单调递增。节点随机超时（150-300ms）触发选举：自增 term、投自己一票、广播 RequestVote。获得多数票即任 leader。随机超时把竞选者错开，避免选票分裂的活锁；term 单调保证旧 leader 复辟不可能——它的 term 落后，任何节点见了都拒绝。

## 机制二：日志复制

leader 接收客户端写，本地追加日志，并行发给所有 follower；收到多数派确认后 commit 并应用，随后通知 follower commit。两阶段里 commit 点是关键：日志被多数派持久化才算 committed，leader 崩溃后新 leader 必然包含所有 committed 日志（选举限制：只有最新日志的候选人能赢），这就是已提交数据不丢的机制保证。

```text
client -> leader: 写 X
leader: 本地 append (term=3, idx=7)
leader -> followers: AppendEntries(term=3, prevLogIndex=6)
多数派持久化 -> leader commit idx=7 -> apply -> 响应客户端
```

## 安全性靠两个不变量

- Election Safety：每个 term 至多一个 leader（一票制 + term 单调）。
- Leader Completeness：新 leader 拥有所有 committed 日志（投票时比较日志新旧，只投给不比自己旧的候选人）。

违反任一不变量的实现 bug 都表现为脑裂或丢数据——这正是 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]] 讲的"共识解决什么"的实现面。

## 验证

- etcd 可用 learner/预投票（pre-vote）降低大集群扰动；观察 term 飘升是网络分区的指纹。
- Jepsen 类测试：注入分区、时钟漂移、磁盘满，验证 committed 数据不丢、脑裂不出现。
- 生产验证：leader 变更次数 SLI、选举超时分布（频繁选举=心跳超时不合理）、commit 延迟 p99。

## 边界

- Raft 不解决成员变更与快照的复杂性：成员变更（joint consensus 或单步变更）是独立章节，快照/日志压缩是日志无限增长的解药，两者都超出本文。
- 共识的代价是写延迟与可用性下限：多数派不可达则不可写，与 [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]] 的按冲突类型选一致性的思路衔接。
- 日志复制的批量与流水线优化（CheckQuorum、ReadIndex、LeaseRead）是性能章节，改变的是延迟数字，不改变安全边界。

## 相关

- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]]：共识的位置（一致性层级里共识在哪一层），本文展开 Raft 实现
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/复制分片与再平衡改变数据归属]]：Raft 组之上的分片拓扑
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]]：共识不可用时的降级选择
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/共识的实现深度：日志复制协议要处理平衡括号之外的事]]：本篇讲主流程机制，完成度清单篇讲快照、成员变更与崩溃注入的实现面
