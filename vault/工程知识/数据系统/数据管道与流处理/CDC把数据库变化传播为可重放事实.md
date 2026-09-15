---
title: CDC 把数据库变化传播为可重放事实
type: concept
status: active
updated: 2026-09-03
review_after: 2027-03-03
change_rate: medium
confidence: high
tags:
  - data/cdc
  - streaming
  - integration
sources:
  - "https://debezium.io/documentation/reference/stable/architecture.html"
  - "https://kafka.apache.org/documentation/#semantics"
---

# CDC 把数据库变化传播为可重放事实

它解决的是下游需要知道数据库状态变化，却不应反复扫描全表或把业务代码复制到每个消费者的问题。核心机制是从提交日志捕获带位点、事务和主键的变更事件，再由消费者幂等投影；收益是可重放、可追踪的增量传播，代价是顺序、删除、schema 演进、延迟和重复处理都要治理。用断点恢复、乱序、重复、删除和 schema 变更验证投影一致性。

Change Data Capture 读取数据库日志或变更流，把 insert/update/delete 转成带位点的事件，供搜索、缓存、数仓和 RAG 索引消费。CDC 事件是数据库提交后的观察，不是跨系统事务自动完成。

## 事件至少需要

```text
source + table/entity + key + operation
before/after（按隐私需要）+ commit position + event time + schema version
```

消费者要保存位点、幂等键和目标版本；重放、乱序、重复、schema 变化、快照与增量衔接都必须有语义。删除和撤权不能被当成“无数据”，需要明确传播和完成证明。

## 常见错误

- 只发送 after，没有 delete 或 before，无法重建和审计。
- 先把位点提交给消息系统，再写目标，崩溃后丢更新；反过来则需要幂等。
- 用处理时间代替源库提交顺序，跨分区后产生错误状态。
- RAG 索引只追加新版本，没有使旧版本停止可见。

## 验证

测试初始快照与增量边界、事务批量、重复/乱序、删除/撤权、消费者重启、目标不可用、schema 演进和从任意位点重放。比较源库事实、事件日志和目标投影的一致性与延迟。

关系：[[工程知识/后端与分布式系统/任务与并发/队列和流系统用时间与容量换取解耦]] · [[工程知识/AI系统/知识与检索/RAG数据管道从文档到可引用证据]]
