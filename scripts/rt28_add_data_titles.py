# -*- coding: utf-8 -*-
"""rt28: 数据系统域 41 篇文章标题的英文词条插入 i18n.js（标题批 5/7）。

背景：EN 态全站标题翻译。批 1（AI 系统工程 94 篇）、批 2（缺陷分析 60 篇）、
批 3（后端系统 59 篇）、批 4（软件构建 56 篇）已完成。本批覆盖数据系统域
全部 41 篇，其中域总览 1 篇已在 rt24 领域批译出（查重核实），故插入其余
40 条。句式多为方法论断言，按原句语义直译、保留冒号骨架。
幂等：已有 rt28 标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt28.json")

TITLES = {
    "LSM 树用写放大换取顺序写和可扩展性": "LSM-trees trade write amplification for sequential writes and scalability",
    "SQLite 与 MySQL 代表不同的并发与运维边界": "SQLite and MySQL represent different concurrency and operations boundaries",
    "SSD与HDD的IO特性差异：随机写与写放大": "SSD versus HDD IO characteristics: random writes and write amplification",
    "一致性哈希把再平衡的数据移动量压到平均槽位": "Consistent hashing compresses rebalancing data movement to the average slot",
    "事务边界应覆盖完整业务用例": "Transaction boundaries should cover complete business use cases",
    "事务隔离决定并发读写能观察到什么": "Transaction isolation decides what concurrent reads and writes can observe",
    "分库分表只在单库成为瓶颈后使用": "Sharding is used only after a single database becomes the bottleneck",
    "分片键设计以查询与均衡为双重约束": "Shard key design is doubly constrained by queries and balance",
    "复制滞后的一致性补救：读己之写与会话保证": "Consistency remedies for replication lag: read-your-writes and session guarantees",
    "存储引擎的两大路线：B树与LSM的写读取舍": "The two routes of storage engines: the write-read trade-off between B-trees and LSM",
    "崩溃一致性给文件系统补上POSIX未定义部分": "Crash consistency fills in the parts POSIX leaves undefined for file systems",
    "数据分布不均是分片集群的第一大故障源": "Uneven data distribution is the top failure source of sharded clusters",
    "读写三放大是存储引擎的中央权衡": "The three amplifications—read, write, space—are the central trade-off of storage engines",
    "非关系数据库按访问模式选择数据模型": "Non-relational databases choose data models by access pattern",
    "InnoDB 用日志连接事务、恢复与复制": "InnoDB uses logs to connect transactions, recovery and replication",
    "MySQL 空间、容量与在线运维": "MySQL space, capacity and online operations",
    "RAID等级与数据可靠性：镜像与纠删的数学": "RAID levels and data reliability: the math of mirroring and erasure coding",
    "分区再平衡的三种策略：固定取模与一致性哈希": "Three rebalancing strategies for partitions: fixed modulo and consistent hashing",
    "在线schema变更走expand与contract，不锁表是底线": "Online schema changes go through expand and contract; no table locks are the floor",
    "备份恢复是可验证的时间边界": "Backup and restore is a verifiable time boundary",
    "备份的价值由恢复演练来验证": "The value of backups is verified by restore drills",
    "复制的三种模式：主从、多主与无主的失败形态": "Three replication modes: the failure shapes of leader-follower, multi-leader and leaderless",
    "多活架构按冲突类型选择一致性策略，而不是按距离": "Active-active architectures choose consistency strategies by conflict type, not by distance",
    "数据库基准必须描述负载与资源边界": "Database benchmarks must describe workload and resource boundaries",
    "SQL 语义由关系、集合和窗口共同决定": "SQL semantics are jointly decided by relations, sets and windows",
    "关系模型用约束表达业务事实": "The relational model expresses business facts through constraints",
    "消失的数值：浮点格式与精度陷阱": "Vanishing values: floating-point formats and precision traps",
    "聚合边界由业务不变量而不是 ER 图决定": "Aggregate boundaries are decided by business invariants, not ER diagrams",
    "数据治理把质量责任放到写路径上": "Data governance puts quality responsibility on the write path",
    "数据质量与血缘让指标可以被解释": "Data quality and lineage make metrics explainable",
    "数据质量的三重校验：完整性时效与一致性": "The triple check of data quality: completeness, timeliness and consistency",
    "CDC 把数据库变化传播为可重放事实": "CDC propagates database changes as replayable facts",
    "批处理与流处理共享逻辑但不共享时间语义": "Batch and stream processing share logic but not time semantics",
    "数据编排要保证依赖、重试与幂等": "Data orchestration must guarantee dependencies, retries and idempotency",
    "物化视图把重复计算变成增量维护": "Materialised views turn repeated computation into incremental maintenance",
    "B+Tree 索引为访问路径服务": "B+Tree indexes serve access paths",
    "一条 SQL 如何穿过优化器与存储引擎": "How a SQL statement travels through the optimiser and the storage engine",
    "列存与向量化执行：OLAP引擎快的两个来源": "Columnar storage and vectorised execution: the two sources of OLAP engine speed",
    "列式存储把扫描与压缩交给分析路径": "Columnar storage hands scanning and compression to the analytical path",
    "慢查询治理从发现到索引闭环": "Slow query governance: from discovery to index closure",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt28·标题批 5/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    ds_titles = {n["title"] for n in notes if n["category"].startswith("数据系统")}
    missing = ds_titles - set(TITLES) - {"数据系统：在并发与故障中保存事实"}
    extra = set(TITLES) - ds_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in extra:
            print("  extra:", t)
        sys.exit(1)

    lines = [
        "    /* 【rt28·标题批 5/7】数据系统域 41 篇（域总览已于 rt24 领域批译出，",
        "       本批插入其余 40 条）。方法论句式直译，保留冒号骨架。 */",
    ]
    for zh, en in TITLES.items():
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 4（软件构建）尾部最后一行。
    anchor = '    "跨语言并发模型必须同时比较抽象与运行机制": { en: "Cross-language concurrency models must compare abstraction and runtime mechanics together" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
