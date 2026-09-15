---
title: Python 数据访问必须显式拥有连接与事务
type: concept
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: high
tags:
  - python/database
  - database/transactions
  - software/architecture
sources:
  - "https://peps.python.org/pep-0249/"
  - "https://docs.sqlalchemy.org/en/20/core/connections.html"
  - "https://docs.sqlalchemy.org/en/20/orm/session_basics.html"
  - "[[工程知识/数据系统/数据系统：在并发与故障中保存事实]]"
---

# Python 数据访问必须显式拥有连接与事务

## 核心拆解

| 维度 | 回答 |
| --- | --- |
| 要解决的问题 | Python 服务容易把连接、session、事务和业务逻辑混在一起，导致连接泄漏、隐式提交、长事务、N+1 和错误重试。 |
| 本质 | 连接是有限资源，事务是业务不变量的原子边界；数据访问抽象必须显式表达两者的所有权和生命周期。 |
| 做法 | 由用例层拥有事务，显式借还连接并在异常后 rollback，设置池和超时，参数化查询，并将外部副作用用 outbox/补偿协调。 |
| 效果与代价 | 资源释放、并发语义和错误分类更可预测；代价是边界代码更多，团队必须理解数据库方言、计划和迁移。 |
| 边界 | ORM/查询构造器不能消除 N+1、锁、索引和事务隔离；数据库事务不能覆盖网络、模型调用或人工等待。 |
| 验证 | 测连接池耗尽、异常回滚、并发冲突、死锁、N+1、超时和进程 fork，检查事务状态、SQL 数量、锁等待和最终事实。 |

选择 raw SQL、query builder 或 ORM 的核心不是项目大小，而是查询复杂度、领域映射、事务边界、可观测性和团队维护能力。

同一个请求如果在事务里等待模型或网络，会长时间占用连接、锁和旧版本；如果异常后未 rollback，连接归还池后还可能污染下一个请求。数据访问层必须把资源所有权和失败语义写出来。

因此“能查到数据”只是功能起点；在并发、超时和重试下仍能释放连接、保持事务不变量并解释 SQL 数量，才是生产可用的数据访问层。

## 分层

```text
业务用例/事务边界
  -> Repository/Query service（可选）
  -> ORM / SQL expression / raw SQL
  -> DB-API driver
  -> connection pool
  -> database
```

| 方式 | 优势 | 边界 |
| --- | --- | --- |
| Raw SQL + driver | SQL 行为透明，适合复杂/性能关键查询 | 手动映射、事务和动态拼接风险 |
| SQL expression/query builder | 参数化、组合性和跨驱动接口 | 抽象仍不能消除数据库方言/计划差异 |
| ORM | 聚合映射、unit of work、关系和生命周期 | N+1、隐式 flush/lazy load、对象状态复杂 |

同一系统可以混用：写模型用 ORM，复杂报表或批处理用显式 SQL。不要因为使用 ORM 就不学习索引、事务和执行计划。

## 连接与池

- 连接是有限资源，池大小根据并发、事务时间和数据库上限计算；不是越大越快。
- 连接池返回的是复用连接；每次借出后必须回滚/清理未完成事务和 session state。
- 设置 connect/read/query/transaction timeout，区分网络暂态、死锁、约束冲突和语法/业务错误。
- fork 前创建的连接池不能直接在子进程复用；每个进程拥有自己的池。
- 密钥从 secret/env/provider 注入，示例不写真实密码；日志脱敏参数和 DSN。

## 事务边界

事务围绕一个业务用例，而不是围绕每条 DAO 调用。明确：

- begin/commit/rollback 由哪一层拥有；
- 异常后 session/connection 是否必须 rollback 才可复用；
- 隔离级别、锁顺序、重试条件与幂等键；
- 外部 API/消息不能假装与数据库处在同一本地事务中，必要时使用 outbox/Saga；
- 长事务会持有锁、旧版本和连接，不能跨用户思考/网络等待。

## 安全与性能

- 永远使用参数绑定；表名/列名等标识符只能从允许列表生成。
- 批量写入使用 executemany/bulk/copy 等数据库能力，但确认错误和返回语义。
- 监控池等待、连接数、事务时长、慢查询、行数和 query fingerprint。
- 避免 ORM N+1：用 eager load、显式 join/batch，并通过 trace/SQL 计数测试。
- 性能结论以数据库执行计划和真实数据分布为准，不以 ORM 代码是否简洁为准。

## 最小模式

```python
def transfer(engine, src, dst, amount):
    with engine.begin() as conn:  # success commit; exception rollback
        debit = conn.execute(DEBIT, {"id": src, "amount": amount})
        if debit.rowcount != 1:
            raise InsufficientBalance(src)
        conn.execute(CREDIT, {"id": dst, "amount": amount})
```

示例只表达资源和事务所有权；实际还需幂等、隔离、审计、货币精度和并发测试。

关联：[[工程知识/数据系统/事务与存储/事务隔离决定并发读写能观察到什么]]、[[工程知识/数据系统/查询与索引/B+Tree索引为访问路径服务]]、[[工程知识/软件构建与质量/语言与运行时/Python并发先区分协程、线程、进程与解释器]]。
