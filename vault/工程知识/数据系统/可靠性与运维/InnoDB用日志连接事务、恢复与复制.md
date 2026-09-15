---
title: InnoDB 用日志连接事务、恢复与复制
type: playbook
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: high
sources:
  - "https://dev.mysql.com/doc/refman/8.4/en/innodb-recovery.html"
  - "https://dev.mysql.com/doc/refman/8.4/en/replication.html"
  - "https://time.geekbang.org/column/intro/100020801"
tags:
  - database/mysql
  - database/reliability
  - database/ha
---

# InnoDB 用日志连接事务、恢复与复制

## 三类日志各自解决什么问题

| 日志 | 主要职责 | 不能替代 |
| --- | --- | --- |
| `redo log` | WAL；崩溃后把已提交修改重做到数据页 | 逻辑审计、跨库复制 |
| `undo log` | 回滚、MVCC 旧版本和一致性读 | 崩溃后的完整备份 |
| `binlog` | Server 层逻辑变更记录；复制、PITR、审计 | 代替 redo 的页级恢复 |

更新通常先改 Buffer Pool、写 redo；提交时通过两阶段提交协调 redo 和 binlog，避免“binlog 有记录但 InnoDB 未提交”或反过来的不一致。`binlog_format=ROW` 通常比 statement 更适合可靠复制和按行恢复，但要结合版本、工具和合规要求验证。

## 持久性和抖动

`innodb_flush_log_at_trx_commit=1` 与 `sync_binlog=1` 常被称为“双 1”，可提供更强的提交持久性，代价是更多刷盘。具体取值必须根据 RPO、磁盘能力和复制架构决定，不能把参数名当作绝对保证。

平时更新快、偶尔整体变慢，常见原因是刷脏页：redo 写满、Buffer Pool 淘汰脏页、后台空闲刷盘或正常关闭。重点观察 redo 使用率、checkpoint age、脏页比例、I/O 延迟和 `innodb_io_capacity` 是否与真实磁盘能力匹配。redo 太小会造成写入堵塞，参数过大则增加崩溃恢复时间和空间占用。

## 复制、高可用和读写分离

复制链路至少要监控：主库写入、日志生成、网络传输、从库 relay 应用和 SQL 应用。延迟可能来自大事务、单线程应用、热点锁、磁盘或网络；只看一个 `Seconds_Behind_Master` 不足以定位原因。

高可用切换必须回答：

- 谁判定主库故障，如何防止脑裂？
- 候选从库是否追平，缺失事务如何处理？
- 客户端如何刷新连接和路由，正在执行的请求如何重试？
- 切换后的写入点、读后写一致性和数据丢失窗口是多少？

读写分离要显式定义一致性策略：关键读走主库、等待从库位点追平、或携带会话粘性；不能假设“写完立刻读”一定能在从库看到。

## 备份与误删恢复

推荐把恢复目标写成可测试的 RPO/RTO，并至少演练：全量备份校验、binlog 连续性、时间点恢复、恢复到隔离实例、业务数据抽样校验和切换回滚。误删后先停止进一步写入或保护现场，保存 binlog/备份，再恢复到临时实例核对，最后用幂等方式回灌；不要直接在生产库“凭记忆反向操作”。

```text
发现 -> 保护现场 -> 确认时间点/影响范围 -> 临时恢复
      -> 校验行数和业务不变量 -> 小批量回灌 -> 对账 -> 复盘
```

## 变更安全

- 大表 DDL 要检查 MDL、执行时间、复制影响和回滚方案。
- `ALTER TABLE ... ENGINE=InnoDB`/`OPTIMIZE TABLE` 可能重建表；`ANALYZE TABLE` 主要更新统计信息，不等同于收缩数据文件。
- 在线 DDL 或 gh-ost 等工具也需要变更窗口、限速、监控和终止条件。

## 关联页面

- [[工程知识/数据系统/事务与存储/事务隔离决定并发读写能观察到什么]]
- [[工程知识/数据系统/查询与索引/一条SQL如何穿过优化器与存储引擎]]
- [[工程知识/数据系统/可靠性与运维/MySQL空间、容量与在线运维]]
- [[工程知识/计算机系统与性能/观测与诊断/性能问题定位]]
