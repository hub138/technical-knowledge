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
  - "distributed-systems"
editorial_pass: 1
editorial_at: 2026-09-25
editorial_by: agent-A
editorial_note: "现状核对：SELFCHECK PASS密度0.88达标0命中，两幅etcd官方与论文Figure2外链图带来源齐全，六维信号词与就地上链完整，补心跳与超时因果、Jepsen 与活性定义、CheckQuorum 归到活性；两幅外链图图注按原图结构改写并补来源许可，去重 tags"
---

# Raft选举与日志复制把共识变成工程实现

共识要解决的问题：一组节点对"下一个值是什么"达成一致，部分节点宕机、网络分区时也不例外。上层是抽象承诺（线性一致，linearizability：所有操作看起来像在某个瞬间依次发生），实现起来是两个具体机制：leader 选举与日志复制。Raft 把 Paxos 难以工程化的部分分成两个相对独立的过程，共识从论文走进了 etcd、Consul、TiKV 的生产实现。

## 机制一：选举

任期（term）是逻辑时钟：每个 term 至多一个 leader，term 单调递增。follower 在超时窗口内收不到 leader 的心跳（leader 定期发出的空 AppendEntries），就自增 term 发起选举：投自己一票、广播 RequestVote。获得多数票即任 leader。随机超时把竞选者错开，避免选票分裂的活锁；term 单调保证旧 leader 复辟不可能——它的 term 落后，任何节点见了都拒绝。

leader 被隔离之后会发生什么，etcd 官方文档画成了前后两个时刻：

![etcd 官方文档 Figure 3：leader 被隔离后新 leader 当选](/static/figures/server-learner-figure-03.png)

时刻 1，三节点集群里 leader 与两个 follower 之间被网络分区隔开，它的分区里凑不出 2 个节点的多数派（quorum），停止推进；时刻 2，另一侧的两个 follower 选出新 leader，旧 leader 一旦收到更高 term 的消息就自动降级为 follower。图取自 [etcd 官方文档的 learner 设计页](https://etcd.io/docs/v3.5/learning/design-learner/)，Apache 2.0。

## 机制二：日志复制

leader 接收客户端写，本地追加日志，并行发给所有 follower；收到多数派确认后 commit 并应用，随后通知 follower commit。两步里 commit 点是关键：日志被多数派持久化才算 committed，leader 崩溃后新 leader 必然包含所有 committed 日志（选举限制：候选人的日志至少要与投票者一样新，否则拿不到票），这就是已提交数据不丢的机制保证。

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

![Raft 论文 Figure 2：状态字段、RequestVote 与 AppendEntries 规则浓缩卡](/static/figures/raft-2.png)

上面伪代码里的每一步都能在卡上找到出处：`prevLogIndex` 校验在 AppendEntries 的接收方规则第 2 条；日志不一致时 leader 把该 follower 的 `nextIndex` 减一重发，在右下 Leaders 规则里；commit 点的推进条件（多数派 `matchIndex ≥ N` 且该条日志属于当前 term）是 Leaders 规则最后一条。图为 Ongaro 与 Ousterhout 论文《In Search of an Understandable Consensus Algorithm》的 Figure 2，经 [Raft 论文中文翻译仓库](https://github.com/maemual/raft-zh_cn) 转载。

违反任一不变量的实现 bug 都表现为脑裂或丢数据——这正是 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]] 讲的"共识解决什么"的实现面。

## 验证

预期是网络分区与时钟漂移下已提交数据不丢、任一 term 里不出现双主；实测若出现双主或已提交记录回退，说明两个不变量之一被实现破坏了。

- Jepsen 类测试（对分布式系统做黑盒故障注入的公开测试系列，曾多次揪出共识实现的脑裂）：注入分区、时钟漂移、磁盘满，验证 committed 数据不丢、脑裂不出现。
- 生产验证：leader 变更次数作为 SLI（服务等级指标）、选举超时分布（频繁选举说明心跳超时设得不合理）、commit 延迟 p99。term 短时间内连续飘升是网络分区的指纹。
- etcd 可用 learner（先同步日志、不参与投票的新成员）与预投票（pre-vote：候选人先探询能否拿到多数票，拿不到就不自增 term）降低大集群扰动。

## 边界

- 本篇只讲主流程。成员变更（joint consensus 或单步变更）与快照/日志压缩（日志无限增长的解药）是论文里的独立章节，实现面见 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/共识的实现深度：日志复制协议要处理平衡括号之外的事]]。
- 共识的代价是写延迟与可用性下限：多数派不可达则不可写，与 [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]] 的按冲突类型选一致性的思路衔接。
- 读优化（ReadIndex 让 follower 确认 commit 点后本地读、LeaseRead 靠租约省掉一轮确认）与日志的批量、流水线发送改变的是延迟数字，不改变安全边界；CheckQuorum 让失去多数派的 leader 主动下台，补的是活性（集群总能选出新 leader 并持续提交日志，不会永久停滞）。

## 相关

- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]]：共识的位置（一致性层级里共识在哪一层），本文展开 Raft 实现
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/复制分片与再平衡改变数据归属]]：Raft 组之上的分片拓扑
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]]：共识不可用时的降级选择
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/共识的实现深度：日志复制协议要处理平衡括号之外的事]]：本篇讲主流程机制，完成度清单篇讲快照、成员变更与崩溃注入的实现面
