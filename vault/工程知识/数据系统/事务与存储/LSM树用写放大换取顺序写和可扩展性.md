---
title: LSM 树用写放大换取顺序写和可扩展性
type: concept
status: active
updated: 2026-09-03
review_after: 2027-09-03
change_rate: stable
confidence: high
tags:
  - data/storage
  - lsm
  - databases
sources:
  - "https://www.cs.umb.edu/~poneil/lsmtree.pdf"
  - "https://rocksdb.org/docs/"
---

# LSM 树用写放大换取顺序写和可扩展性

它解决的是随机更新难以维持高写入吞吐的问题。核心机制是先顺序写日志和内存表，再通过 compaction 合并有序文件；收益是写路径更适合高吞吐介质，代价是写放大、空间放大、读放大和后台合并竞争。用不同读写比例、键分布、compaction backlog 和故障恢复压测验证，而不是只看顺序写速度。

LSM 系统先把写入追加到内存结构和日志，再批量刷成不可变有序文件，通过 compaction 合并重叠范围。它把随机写变成顺序写，却引入读放大、空间放大、后台 I/O 和 compaction 尾延迟。

## 读写路径

```text
write -> WAL -> memtable -> immutable table
read  -> memtable + block cache + 多层 SSTable
merge -> compaction -> 新版本文件
```

Bloom filter、索引块和缓存减少无效读取；分层/大小分级 compaction 在写放大、空间和读放大之间取舍。删除通常先写 tombstone，直到 compaction 确认旧版本不可见。

## 适用边界

写密集、顺序追加和横向扩展的工作负载常受益；高比例随机读、严格尾延迟或频繁更新热点可能受 compaction 影响。WAL 刷盘、压缩、文件数量、磁盘带宽和后台线程必须纳入容量计划。

## 验证

按读写比例、key 分布、value 大小、更新/删除比例和磁盘类型压测；观察 p50/p99、写/读/空间放大、compaction backlog、WAL 恢复和重启时间。不要用空数据库 benchmark 推断生产表现。

关系：[[工程知识/数据系统/可靠性与运维/数据库基准必须描述负载与资源边界]] · [[工程知识/计算机系统与性能/存储与网络/存储IO性能取决于访问模式、队列与持久化语义]]
