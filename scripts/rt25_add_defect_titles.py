# -*- coding: utf-8 -*-
"""rt25: 缺陷分析域 60 篇文章标题的英文词条插入 i18n.js（标题批 2/7）。

背景：用户要求 EN 态全站标题翻译。批 1（AI 系统工程 94 篇）已完成，
本批覆盖缺陷分析域全部 60 篇。标题多为"案例 N：机制——后果"结构，
按 "Case N: mechanism — consequence" 保持骨架。幂等：已有标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt25.json")

TITLES = {
    "案例七：兼容与性能——滞后的依赖与放大的日志": "Case 7: compatibility and performance — lagging dependencies and amplified logs",
    "案例四十三：升级把前提带走了——依赖行为变更引发的下游失效": "Case 43: the upgrade took its premises away — downstream breakage from dependency behaviour changes",
    "从复现到回归——让证据走完一圈": "From reproduction to regression — letting evidence run the full loop",
    "回归风险评估把修复的爆炸半径圈出来": "Regression risk assessment fences off the blast radius of a fix",
    "回归风险评估的通用骨架：从变更面到测试选择": "A general skeleton for regression risk assessment: from change surface to test selection",
    "证据链的够用判据——从孤证到可裁决": "When the evidence chain is enough — from a lone data point to a decidable case",
    "案例二十六：公告栏没查门禁——Redis 的 ACL 键名泄露与解析崩溃": "Case 26: the bulletin board skipped the gate — Redis ACL key-name leaks and parser crashes",
    "案例五：安全两例——认证绕过与带漏洞依赖": "Case 5: two security cases — auth bypass and a vulnerable dependency",
    "案例四十四：投毒不是写错，是写给你看——依赖投毒的三个真实剧本": "Case 44: poisoning is not a bug, it is written for you — three real dependency-poisoning scripts",
    "并发缺陷的复现策略：压力放大与确定性调度": "Reproducing concurrency bugs: stress amplification and deterministic scheduling",
    "时间型缺陷的判定树：过期竞态与时钟依赖": "A decision tree for time-dependent bugs: expiry races and clock dependencies",
    "案例三十一：回收之后还在飞——跨线程复用可回收对象": "Case 31: still flying after recycling — cross-thread reuse of recyclable objects",
    "案例三十二：取到了已经不存在的那个——估算器的读取竞态": "Case 32: fetched the one that no longer exists — a read race in the estimator",
    "案例三：并发两面——写回调卡死与心跳竞态": "Case 3: two faces of concurrency — a stuck write callback and a heartbeat race",
    "案例二十：关闭之后还有人在用——生命周期的时序竞态": "Case 20: someone still using it after close — a lifecycle timing race",
    "案例十九：在回调里改自己——清理路径的重入与回收后复用": "Case 19: mutating itself from a callback — re-entry on the cleanup path and use after recycle",
    "案例十四：一方取消，旁观者陪葬——RocksDB 状态加载的并发陷阱": "Case 14: one side cancels, bystanders go down too — a concurrency trap in RocksDB state loading",
    "案例四十：谁在回答谁——Pulsar 连接复用与去重的键不完整": "Case 40: who is answering whom — Pulsar connection reuse and incomplete dedup keys",
    "修复优先级排序修复顺序的决策框架": "Fix priority: a decision framework for repair order",
    "影响判断——这条修复值不值得跟": "Judging impact — whether this fix is worth following",
    "影响面估算先于修复——从改一行到伤多少服务": "Estimating blast radius before fixing — from one changed line to how many hurt services",
    "案例三十七：锁自己变成了瓶颈——争用背后的临界区错配": "Case 37: the lock became the bottleneck — critical-section mismatch behind the contention",
    "案例二十五：库自带了一支军队——OpenBLAS 的隐式线程": "Case 25: the library shipped an army — OpenBLAS and its hidden threads",
    "案例二十四：并行度被自己折叠——repartition 的 2 的幂倾斜": "Case 24: parallelism folded by itself — power-of-two skew in repartition",
    "案例三十三：估算不等于算术——按大小推条目的错算": "Case 33: estimation is not arithmetic — miscounting entries from sizes",
    "案例三十九：身份在改写中丢失——RLS 子查询与视图 DEFAULT 的静默失真": "Case 39: identity lost in rewriting — silent distortion from RLS subqueries and view DEFAULTs",
    "案例三十四：省下的句柄与多出的删除——一次优化引入的回归": "Case 34: handles saved, deletions gained — a regression introduced by an optimisation",
    "案例三十：中间缺了一块——跨地域复制的 ack 空洞": "Case 30: a hole in the middle — ack gaps in cross-region replication",
    "案例九：数字越过了边界——Redis 里三次截断导致的崩溃": "Case 9: numbers across the boundary — three truncations that crashed Redis",
    "案例二十九：离开的人还占着座位——机架信息的陈旧映射": "Case 29: the departed still hold seats — stale rack-info mappings",
    "案例二：静默错算——Spark SQL Union 的别名陷阱": "Case 2: silent miscalculation — the alias trap in Spark SQL unions",
    "案例十三：键序与列名——Spark SQL 又两种静默错算": "Case 13: key order and column names — two more silent miscounts in Spark SQL",
    "案例十八：空集合被当成了\"全部已确认\"——游标跳过的位置": "Case 18: an empty set read as \"all confirmed\" — positions the cursor skipped",
    "案例十六：数据被自己人删掉——entry log 头里的假账": "Case 16: data deleted by its own side — false books in the entry-log header",
    "案例十：类型说谎时——静默删数据的 TTL 与算错的比较": "Case 10: when types lie — a TTL that silently deletes data and a miscounted comparison",
    "案例四十一：确认了却没确认——Pulsar 消息语义的三种失真": "Case 41: confirmed but not confirmed — three distortions of Pulsar message semantics",
    "案例四十二：备份里的假账——恢复路径的静默损坏": "Case 42: false books in the backup — silent corruption on the restore path",
    "静默失真的检测靠对账与不变量而不是报错": "Detecting silent distortion relies on reconciliation and invariants, not on errors",
    "症状到机制的判定树——新缺陷的归类入口": "A symptom-to-mechanism decision tree — the entry point for classifying new defects",
    "磁盘坏道与静默损坏的检测修复路径": "Detecting and repairing bad sectors and silent corruption",
    "网卡静默降速与链路劣化：协商、光功率与吞吐基线": "Silent NIC downshift and link degradation: negotiation, optical power, and throughput baselines",
    "案例一：垃圾回收线程的死亡——BookKeeper 磁盘写满": "Case 1: death of the garbage-collection thread — BookKeeper with a full disk",
    "案例三十六：写被自己的回调堵死——挂起的 add 回调": "Case 36: writes blocked by their own callback — a stuck add callback",
    "案例二十一：异常路径上没有完成——永不兑现的 future": "Case 21: never completed on the error path — futures that never resolve",
    "案例二十三：一次抖动变成一次重算——SASL 拉取没有重试": "Case 23: one hiccup becomes a recompute — SASL fetch without retries",
    "案例二十二：时间也是输入——夏令时让序列生成越界": "Case 22: time is input too — daylight saving pushes sequence generation out of range",
    "案例八：承诺没有兑现——Pulsar 里六个永不返回的请求": "Case 8: promises unkept — six Pulsar requests that never return",
    "案例十一：上游修好了，你这边没有——一个发行分支的移植缺口": "Case 11: fixed upstream, not on your side — a backport gap on a release branch",
    "案例十二：调度线程的永久等待——广播写锁不释放": "Case 12: the scheduler waits forever — a broadcast write lock never released",
    "缺陷分析五步法——从个案到通用模型": "A five-step method for defect analysis — from incident to general model",
    "缺陷分析的本质——期望与现实的偏差": "The essence of defect analysis — the gap between expectation and reality",
    "缺陷分析：从个案到体系——导读与开源地图": "Defect analysis: from incidents to systems — a guide and an open-source map",
    "案例六：容量与泄漏——连接泄漏和 SST 堆积": "Case 6: capacity and leaks — connection leaks and SST pile-up",
    "案例十七：删除列表里的幽灵——永不收敛的待删账本": "Case 17: ghosts in the deletion list — a deletion ledger that never converges",
    "资源泄漏的三段式排查法：预筛确认与归因": "A three-stage approach to resource leaks: pre-screening, confirmation, and attribution",
    "案例三十五：后写的覆盖了先写的——策略层级的覆盖顺序": "Case 35: later writes override earlier ones — override order across policy tiers",
    "案例三十八：没有写下来的版本——默认值里的迁移债": "Case 38: the version that was never written down — migration debt hidden in defaults",
    "案例十五：错误最晚在哪一刻暴露——Imputer 与公平调度的两种延迟": "Case 15: the latest moment an error can surface — two delayed failures, Imputer and fair scheduling",
    "案例四：配置不生效——recover 速率与重复日志": "Case 4: configuration that never took effect — recovery rate and duplicated logs",
    "配置类缺陷的静态防线：schema校验与默认值审计": "A static front line against configuration defects: schema validation and default-value audits",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt25·标题批 2/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    da_titles = {n["title"] for n in notes if n["category"].startswith("缺陷分析")}
    missing = da_titles - set(TITLES)
    extra = set(TITLES) - da_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in sorted(extra):
            print("  extra:", t)
        sys.exit(1)

    lines = [
        "    /* 【rt25·标题批 2/7】缺陷分析域 60 篇。案例标题按",
        "       \"Case N: mechanism — consequence\" 骨架精译，保留编号与",
        "       双段结构，方便与中文原题对照。 */",
    ]
    for zh, en in TITLES.items():
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 1 尾部（AI 域标题块最后一行）。
    anchor_line = '    "评测集的构建与维护：从场景采样到难度分层": { en: "Building and maintaining eval sets: from scenario sampling to difficulty tiers" },\n'
    if anchor_line not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor_line, anchor_line + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
