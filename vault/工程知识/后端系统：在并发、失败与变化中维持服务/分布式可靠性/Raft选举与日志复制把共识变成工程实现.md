---
title: Raft选举与日志复制把共识变成工程实现
type: concept
status: active
updated: 2026-10-02
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
---

# Raft 怎么用选举与日志复制把共识变成工程实现？

Raft 要解决的问题是：一组节点要对"下一个值是什么"**达成一致（即共识，consensus）**，部分节点宕机、网络分区时也不例外。读完这篇你能说清 leader（记账人式的领导者节点）怎么选出、日志怎么复制，以及为什么它比 Paxos（更早的共识算法，以难以理解和实现著称）好实现。

可以把它想成几个人合伙记账：先选出一个记账人（选举），之后每一笔账都由他写进本子再抄给其他人，收到过半数回执才算记下（日志复制）。这个比方到「过半数回执」为止成立；区别在于** Raft 只认过半数节点的持久化回执**，而人工记录容易记错或漏记。此外 Raft 里的角色切换由超时和任期号驱动，跟人的意愿没有关系。

共识（consensus，多个节点对"下一个值是什么"达成一致）是分布式系统的核心承诺，Raft（一种以可理解性为设计目标的共识算法）把共识拆成选举与日志复制两个可分别验证的机制。上层是抽象承诺（**线性一致，linearizability**：所有操作看起来像在某个瞬间依次发生），实现起来是两个具体机制：**leader 选举与日志复制**。Raft 把 Paxos 难以工程化的部分分成两个相对独立的过程，共识从论文走进了 etcd（分布式键值存储，Kubernetes 用它存集群状态）、Consul、TiKV 的生产实现。

## 选举是怎么做到的

**任期（term）是标记轮次的逻辑时钟**，用来判断消息和日志的新旧：**每个 term 至多一个 leader，term 单调递增**。follower 在超时窗口内收不到 leader 的心跳（leader 定期发出的空 AppendEntries），就自增 term 发起选举：投自己一票、广播 RequestVote（请求投票的 RPC，即 Remote Procedure Call 远程过程调用：像调本地函数一样调远端服务，也就是前面说的拉票）。

**获得多数票即任 leader**。每个节点在 **[T, 2T] 之间随机取选举超时**，发起选举的时刻因此错开，避免大家同时竞选、选票被均分后谁都不过半而反复重试的活锁（各方不停动作却谁也进不了目标状态的循环）；term 单调保证旧 leader 复辟不可能——它的 term 落后，任何节点见了都拒绝。leader 被隔离后的降级（主动牺牲部分功能或精度，保住核心链路）过程，etcd 官方文档画成了前后两个时刻：

![etcd 官方文档图：三节点集群 leader 被网络分区隔离——时刻 1 leader 与两侧 follower 均被砖墙隔断失去 quorum，时刻 2 左侧 follower 当选新 leader，原 leader 降级为 follower](/static/figures/etcd-leader-isolation.png)

*图源：etcd 官方文档《Learner design》（server-learner-figure-03），https://etcd.io/docs/v3.5/learning/design-learner/，文章插图。*

leader 被隔离之后会发生什么，etcd 官方文档画成了前后两个时刻：

时刻 1，三节点集群里 leader 与两个 follower 之间被网络分区隔开，它的分区里凑不出 2 个节点的多数派（quorum），停止推进；时刻 2，另一侧的两个 follower 选出新 leader，旧 leader 一旦收到更高 term 的消息就自动降级为 follower。图取自 [etcd 官方文档的 learner 设计页](https://etcd.io/docs/v3.5/learning/design-learner/)，Apache 2.0。

## 日志复制是怎么做到的

leader 接收客户端写，本地追加日志，并行发给所有 follower；收到多数派确认后 commit（提交，标记为可对外生效）并 apply（应用到状态机，真正执行写操作），随后通知 follower 提交。两步里 commit 点是关键：**日志被多数派持久化才算 committed**，**leader 崩溃后新 leader 必然包含所有 committed 日志**（选举限制：候选人的日志至少要与投票者一样新，否则拿不到票），这就是**已提交数据不丢的机制保证**。

```text
client -> leader: 写 X
leader: 本地 append (term=3, idx=7)
leader -> followers: AppendEntries(term=3, prevLogIndex=6)
多数派持久化 -> leader commit idx=7 -> apply -> 响应客户端
```

日志复制要处理的核心场景是 follower 日志与 leader 不一致：论文 Figure 7 列出一个 term 的 leader 上任时各 follower 可能的日志形态——已提交前缀（term 1-3）人人相同，未提交尾部却各有各的样子。leader 逐个对齐的依据就是上一段的 `prevLogIndex` 校验与 `nextIndex` 回退重发；「候选人的日志至少与投票者一样新」这条选举限制则保证带着不一致尾部的节点当不上 leader：

![Raft 论文 Figure 7：同一时刻各 follower 可能的日志形态，最上行是 term 8 的 leader 日志，(a) 到 (f) 是各 follower 缺失或多出的未提交尾部](/static/figures/raft-fig7-log-mismatch.png)

*图源：Raft 论文中文翻译仓库 raft-zh_cn 的 images 目录（raft-图7），https://github.com/maemual/raft-zh_cn（jsDelivr 直链），论文插图。*

![Raft 集群与客户端：请求先到集群，由内部共识后返回结果](/static/figures/raft-cluster-client-and-three-nodes.jpg)

来源：[博客园《解密 Raft 算法》](https://www.cnblogs.com/traditional/p/12588733.html)（CC 4.0 BY-SA）



## 安全性靠哪两个不变量

- **Election Safety**：每个 term 至多一个 leader。若失效，term 3 里两个节点都自认 leader，客户端 A、B 各写一边，**造成脑裂**。
- **Leader Completeness**：新 leader 拥有所有 committed 日志（投票时比较日志新旧，只投给不比自己旧的候选人）。若失效，新 leader 缺少一条已被多数派确认的提交，**客户端之前读到的结果凭空消失**。

Raft 论文 Figure 2 把状态字段、两个 RPC 与服务器规则浓缩成一张规范卡，实现时逐条核对用：

![Raft 论文 Figure 2：状态字段、RequestVote 与 AppendEntries 规则浓缩卡](/static/figures/raft-2.png)

来源：[Raft 一致性算法官方网站](https://raft.github.io/)，Figure 2 规范卡（CC 4.0 BY-SA）

上面伪代码里的每一步都能在卡上找到出处：`prevLogIndex` 校验在 AppendEntries 的接收方规则第 2 条；日志不一致时 leader 把该 follower 的 `nextIndex` 减一重发，在右下 Leaders 规则里；commit 点的推进条件（多数派 `matchIndex ≥ N` 且该条日志属于当前 term）是 Leaders 规则最后一条。图为 Ongaro 与 Ousterhout 论文《In Search of an Understandable Consensus Algorithm》的 Figure 2，经 [Raft 论文中文翻译仓库](https://github.com/maemual/raft-zh_cn) 转载。

**脑裂（同一 term 出现两个 leader，两边都能写入而互相矛盾）与丢数据是违反不变量的两种典型后果**：违反 Election Safety 会冒出双主即脑裂，违反 Leader Completeness 会让新 leader 漏掉已提交日志即丢数据。实现上的 bug 若违反任一不变量，最终都落到这两类现象——这正是 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]] 讲的"共识解决什么"的实现面。

## 怎么自己动手验证

预期是网络分区与时钟漂移下已提交数据不丢、任一 term 里不出现双主；实测若出现双主或已提交记录回退，说明两个不变量之一被实现破坏了。

- Jepsen 类测试（对分布式系统做黑盒故障注入的公开测试系列，曾多次揪出共识实现的脑裂）：注入分区、时钟漂移、磁盘满，验证 committed 数据不丢、脑裂不出现。
- 生产验证：leader 变更次数作为 SLI（服务等级指标）、选举超时分布（频繁选举说明心跳超时设得不合理）、commit延迟 p99（99 分位，即最慢那 1% 请求的耗时）。term 短时间内连续飘升是网络分区的迹象：分区使多个节点各自超时发起选举、term 各自递增，所以 term 连续跳升可以当作分区的信号——这只是类比，分区还有别的表现。
- etcd 可用 learner（先同步日志、不参与投票的新成员）与预投票（pre-vote：候选人先探询能否拿到多数票，拿不到就不自增 term）降低大集群扰动。扩容与分区的叠加风险，etcd 官方文档的 learner 设计页画出了极端场景：

![etcd 官方文档图：3 节点集群（quorum=2）网络分区后，新增节点把集群变为 4 节点（quorum=3），活跃节点不足，leader 失去 quorum 触发选举](/static/figures/etcd-learner-quorum-change-election.png)

*图源：同上（etcd 官方文档《Learner design》），（server-learner-figure-06）。*

## 这套说法在哪儿会失效

- 本篇只讲主流程。成员变更（joint consensus 或单步变更）与快照（某一时刻的完整只读副本）/日志压缩（日志无限增长的解药）是论文里的独立章节，实现面见 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/共识的实现深度：日志复制协议要处理平衡括号之外的事]]。
- 共识的代价是**写延迟与可用性下限：多数派不可达则不可写**，与 [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]] 的按冲突类型选一致性的思路衔接。
- 读优化（ReadIndex 让 follower 确认 commit 点后本地读、LeaseRead 靠租约省掉一轮确认）与日志的批量、流水线发送改变的是延迟数字，不改变安全边界；CheckQuorum（法定人数：多数派确认才算成功的机制） 让失去多数派的 leader 主动下台，补的是活性（集群总能选出新 leader 并持续提交日志，不会永久停滞）。

## 接着读哪几篇：同在后端系统里的相邻问题

- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/一致性模型与共识解决不同问题]]：共识的位置（一致性层级里共识在哪一层），本文展开 Raft 实现
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/复制分片与再平衡改变数据归属]]：Raft 组之上的分片（把数据按规则切开存到不同节点）拓扑
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/多活架构按冲突类型选择一致性策略，而不是按距离]]：共识不可用时的降级选择
- [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/共识的实现深度：日志复制协议要处理平衡括号之外的事]]：本篇讲主流程机制，完成度清单篇讲快照、成员变更与崩溃注入的实现面
