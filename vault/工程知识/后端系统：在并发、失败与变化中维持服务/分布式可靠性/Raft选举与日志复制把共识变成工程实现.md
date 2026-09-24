---
title: Raft选举与日志复制把共识变成工程实现
type: concept
status: active
updated: 2026-09-25
review_after: 2027-09-21
change_rate: low
confidence: high
sources:
  - "https://raft.github.io/raft.pdf"
  - "https://raft.github.io/"
  - "https://github.com/etcd-io/raft"
tags:
  - "distributed-systems/consensus"
  - "distributed-systems/consensus"
  - "distributed-systems"
editorial_pass: 1
editorial_at: 2026-09-25
editorial_by: agent-A
editorial_note: "现状核对：SELFCHECK PASS密度0.88达标0命中，两幅etcd官方与论文Figure2外链图带来源齐全，六维信号词与就地上链完整，本轮零改动仅标记"
---

# Raft选举与日志复制把共识变成工程实现

共识要解决的问题：一组节点对"下一个值是什么"达成一致，即使部分节点宕机、网络分区。上层是抽象承诺（linearizability），实现起来是两个具体机制：leader 选举与日志复制。Raft 把 Paxos 难以工程化的部分分成两个相对独立的过程，共识从论文走进了 etcd、Consul、TiKV 的生产实现。

## 机制一：选举

任期（term）是逻辑时钟：每个 term 至多一个 leader，term 单调递增。节点随机超时（150-300ms）触发选举：自增 term、投自己一票、广播 RequestVote。获得多数票即任 leader。随机超时把竞选者错开，避免选票分裂的活锁；term 单调保证旧 leader 复辟不可能——它的 term 落后，任何节点见了都拒绝。

leader 被隔离、失去多数派、新 leader 在多数派侧当选的完整过程，etcd 官方文档画成两幅对照：

![etcd 官方文档 Figure 3：leader 被隔离后新 leader 当选](https://etcd.io/docs/v3.5/learning/img/server-learner-figure-03.png)

上图取自 [etcd 官方文档的学习设计页](https://etcd.io/docs/v3.5/learning/design-learner/)：上幅旧 leader 失去 quorum 停止推进，下幅多数派侧选出新 leader，旧 leader 见到更高 term 自动降级，与上文 term 单调的叙述逐条对应。

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

Raft 论文 Figure 2 把状态字段、两个 RPC 与服务器规则浓缩成一张规范卡，实现时逐条核对用：

![Raft 论文 Figure 2：状态字段、RequestVote 与 AppendEntries 规则浓缩卡](https://cdn.jsdelivr.net/gh/maemual/raft-zh_cn@master/images/raft-图2.png)

上图是 [Raft 论文中文版仓库](https://github.com/maemual/raft-zh_cn)收录的论文 Figure 2，与本地伪代码逐条对应，nextIndex 回退在图的 Followers 规则里。

违反任一不变量的实现 bug 都表现为脑裂或丢数据——这正是 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]] 讲的"共识解决什么"的实现面。

## 验证

验证的锚点：共识实现要与注入对账——预写网络分区与时钟漂移下已提交数据不丢、脑裂不出现，实测出现双主或已提交记录回退，与预期对不上。

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
