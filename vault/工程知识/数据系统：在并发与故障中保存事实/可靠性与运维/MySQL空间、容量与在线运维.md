---
title: MySQL 空间、容量与在线运维
type: playbook
status: active
updated: 2026-09-03
review_after: 2027-02-28
change_rate: medium
confidence: high
sources:
  - "https://dev.mysql.com/doc/refman/8.4/en/backup-and-recovery.html"
  - "https://dev.mysql.com/doc/refman/8.4/en/server-administration.html"
  - "https://dev.mysql.com/doc/refman/8.4/en/mysql-nutshell.html"
tags:
  - database/mysql
  - database/operations
  - database/capacity
---

# MySQL 空间、容量与在线运维

本文的版本性判断以 MySQL 8.4 官方手册为准；云厂商兼容版、MySQL 9.x 或不同存储引擎的命令和默认值必须单独复测。课程材料只作为历史线索，不作为当前行为的依据。

## 删除、空洞和表空间

InnoDB 的 `DELETE` 通常只把记录或数据页标记为可复用，不会让 `.ibd` 文件立即变小。随机插入、更新和删除还可能产生页分裂和空洞。回收空间需要重建表并评估 MDL、I/O、复制和回滚风险：

- `ANALYZE TABLE`：更新统计信息，不重建数据。
- `ALTER TABLE t ENGINE=InnoDB`：重建表，可能回收空洞。
- `OPTIMIZE TABLE`：通常相当于重建并重新统计，具体行为看引擎和版本。

优先从表设计、删除策略、分区生命周期和归档流程减少空洞；不要把频繁 `OPTIMIZE` 当作常规性能按钮。

## COUNT 和计数模型

InnoDB 需要根据 MVCC 判断当前事务可见的行，因此无条件 `COUNT(*)` 也可能扫描大量数据。`COUNT(*)` 是最明确且通常最优的全行计数写法；`COUNT(col)` 只统计非 NULL 值，不能互换。`SHOW TABLE STATUS` 的估算值不能替代精确计数。

高频展示计数时，选择与一致性要求匹配的方案：异步统计允许近似；强一致计数可在同一事务内维护计数表，但热点行会产生锁竞争，需分片或按桶计数。

## 临时表、引擎和分区

- 内部临时表可能由 `GROUP BY`、`DISTINCT`、复杂排序和中间结果触发，关注内存上限、磁盘落盘和生命周期。
- `Memory` 引擎适合可丢失、结构简单且明确受控的临时数据；不要用它替代 InnoDB 的持久性和事务能力。
- 分区只有在分区键过滤、生命周期管理或单分区维护确实带来收益时才使用；分区不是自动并行和自动索引，先用真实数据验证剪枝效果。

## 容量与自增

自增 ID 不保证连续：回滚、批量预留、冲突和重启都可能造成间隙。业务不要把连续自增当作计数器或无缺口账本。接近类型上限时，提前评估扩容、迁移、无符号范围和下游字段兼容性。

## 现场诊断

```sql
SHOW PROCESSLIST;
SHOW ENGINE INNODB STATUS;
SELECT * FROM performance_schema.events_statements_summary_by_digest;
SELECT * FROM performance_schema.table_lock_waits_summary_by_table;
```

建议先 `FLUSH STATUS` 再做固定窗口采样，区分累计值和本窗口增量；结合慢日志、CPU、内存、磁盘、网络、连接数、锁等待和复制延迟形成证据链。

## 权限和复制

`GRANT` 会更新权限表；现代 MySQL 通常会立即生效，不应把 `FLUSH PRIVILEGES` 当作每次授权后的固定动作。兼容分支与发行版（例如 Percona Server、MariaDB）要用最小复现记录与原版 MySQL 的差异，不能只依据产品宣传或旧笔记。

## 关联页面

- [[工程知识/数据系统：在并发与故障中保存事实/查询与索引/B+Tree索引为访问路径服务]]
- [[工程知识/数据系统：在并发与故障中保存事实/事务与存储/事务隔离决定并发读写能观察到什么]]
- [[工程知识/数据系统：在并发与故障中保存事实/可靠性与运维/InnoDB用日志连接事务、恢复与复制]]
- [[工程知识/数据系统：在并发与故障中保存事实/数据系统：在并发与故障中保存事实]]
