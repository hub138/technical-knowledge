---
title: 租约必须配合 Fencing Token 阻止过期持有者
type: concept
status: active
updated: 2026-09-16
review_after: 2027-02-28
change_rate: stable
confidence: high
tags:
  - operating-systems/locking
  - concurrency
  - reliability/lease
sources:
  - "https://man7.org/linux/man-pages/man2/flock.2.html"
  - "https://man7.org/linux/man-pages/man2/fcntl.2.html"
  - "https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html"
  - "[[工程知识/后端与分布式系统/分布式可靠性/部分失败决定分布式系统的设计]]"
---

# 租约必须配合 Fencing Token 阻止过期持有者

它解决的是租约过期后旧持有者因网络暂停而继续写入的陈旧执行问题。核心做法是协调器为每次取得租约发放单调 token，并让下游拒绝更小 token；收益是把“谁现在持有”变成下游可验证的事实，代价是所有写入点都必须传递并检查 token。用暂停、时钟漂移、续租失败和主备切换验证旧 owner 永远不能覆盖新 owner。

锁只解决“此刻谁可以进入临界区”，不自动解决资源归属、进程死亡、跨主机一致性和陈旧持有者问题。

## 先区分机制

| 机制 | 作用域/语义 | 适用 | 边界 |
| --- | --- | --- | --- |
| `flock` | 通常绑定打开文件描述与文件；共享/排他、阻塞/非阻塞 | 单机进程协调、脚本互斥 | 网络文件系统语义可能不同；advisory lock 要求参与者合作 |
| POSIX record lock (`fcntl`) | 可对字节范围加锁，语义与进程/文件关闭有关 | 需要区间锁的单机程序 | 继承与关闭语义容易误用；不等同于分布式锁 |
| 原子创建/rename | 依赖文件系统原子操作 | 发布文件、简单 leader 标记 | 无 TTL；崩溃后需清理策略 |
| 数据库条件更新 | 用事务和版本号竞争状态 | 业务任务、跨进程协调 | 依赖数据库可用性和隔离级别 |
| 分布式租约 | owner + TTL + renew + fencing token | 跨主机长期任务 | 需处理时钟、网络分区和陈旧持有者 |

## 正确的锁使用

先判断是否真的需要分布式锁。创建唯一业务对象优先用数据库唯一约束，状态更新优先用版本号/CAS，任务分片优先用稳定 owner；这些机制直接保护业务不变量，通常比“先拿锁再写”更容易验证。只有多个进程必须独占一个无法原子更新的外部资源时，才进入租约设计。

最常见的错误是把“锁还在”当作“旧持有者已经停止”。实例 A 暂停超过 TTL 后，实例 B 会取得新租约；A 恢复时仍可能继续写。因此续租只能降低过期概率，不能阻止旧 owner，最终必须由资源侧检查单调递增的 fencing token。

```python
with open(lock_path, "a+") as handle:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    # 临界区：短、可恢复，不调用不受控的长网络操作
```

- 锁对象的生命周期必须覆盖临界区；关闭 fd 通常会释放相应锁。
- 非阻塞获取失败是正常状态，调用者需选择跳过、排队、退避或返回冲突。
- 把 owner、task generation、revision 写入受保护元数据，便于诊断；不要把文件存在本身当成锁仍有效。
- 锁内操作尽量短；长任务使用租约，并让外部协调者续租和检测过期。

## 为什么任务系统需要 fencing token

仅有 TTL 的租约可能在网络暂停后出现旧持有者“复活”：新任务已经取得租约，旧任务仍向下游写入。每次成功取得租约生成单调递增的 fencing token，下游拒绝小于当前 token 的写入，才能阻止陈旧执行者。

```text
lease owner=A token=41  --暂停/过期-->
lease owner=B token=42  -> 下游接受 token=42
A 恢复并写 token=41    -> 下游拒绝
```

## 清理不是拿到锁就删除

删除 worktree、缓存或运行目录前检查资源 owner、generation、活跃租约、进程树和引用计数。锁只能保护检查与状态更新的原子区间；真正删除还要绑定明确资源标识，不能使用宽泛路径或未解析的 glob。

关联：[[工程知识/AI系统/安全与治理/执行证据必须独立于AI结论]]、[[工程知识/后端与分布式系统/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理]]、[[工程知识/后端与分布式系统/分布式可靠性/部分失败决定分布式系统的设计]]。
