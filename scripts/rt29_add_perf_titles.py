# -*- coding: utf-8 -*-
"""rt29: 性能工程域 39 篇文章标题的英文词条插入 i18n.js（标题批 6/7）。

背景：EN 态全站标题翻译。批 1-5（AI 系统工程 94、缺陷分析 60、后端系统 59、
软件构建 56、数据系统 40）已完成。本批覆盖性能工程域全部 39 篇，其中域总览
1 篇已在 rt24 领域批译出（查重核实），故插入其余 38 条。句式多为方法论断言，
按原句语义直译、保留冒号骨架。
幂等：已有 rt29 标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt29.json")

TITLES = {
    "CPU 性能来自有效执行与数据供给": "CPU performance comes from effective execution and data supply",
    "CPU 缓存与分支决定有效执行时间": "CPU caches and branches decide effective execution time",
    "ECC内存把单比特错误挡在报告之前": "ECC memory stops single-bit errors before they reach reports",
    "GPU 性能取决于计算、访存、并行与通信": "GPU performance depends on compute, memory access, parallelism and communication",
    "NUMA让跨槽访问付出带宽与延迟代价": "NUMA makes cross-socket access pay in bandwidth and latency",
    "SIMD与数据并行：一行代码的多个通道": "SIMD and data parallelism: multiple lanes in one line of code",
    "大页与TLB：地址翻译的隐藏成本": "Huge pages and the TLB: the hidden cost of address translation",
    "无锁数据结构的证据门槛：CAS与内存序": "The evidence bar for lock-free structures: CAS and memory ordering",
    "缓存行与伪共享：64字节里的并发性能": "Cache lines and false sharing: concurrent performance inside 64 bytes",
    "DNS解析是延迟与故障的隐形入口": "DNS resolution is the hidden entry point of latency and failure",
    "QUIC把传输握手与加密合流到用户态": "QUIC merges transport handshake and encryption into userspace",
    "RDMA绕过内核但要付出可运维性代价": "RDMA bypasses the kernel but pays in operability",
    "SSD的写放大来自介质要先擦后写": "SSD write amplification comes from erase-before-write media",
    "Socket 与 TCP 把连接可靠性分成多层": "Sockets and TCP split connection reliability into layers",
    "TIME_WAIT是连接收尾的代价与设计": "TIME_WAIT is the cost and design of closing connections",
    "TLS握手与证书链决定连接建立成本": "TLS handshakes and certificate chains decide connection setup cost",
    "cache分配策略与命中率：LFU与LRU的实证对比": "Cache eviction policies and hit rates: LFU versus LRU, an empirical comparison",
    "交付前的网络检查清单": "A pre-delivery network checklist",
    "存储 I/O 性能取决于访问模式、队列与持久化语义": "Storage IO performance depends on access pattern, queueing and persistence semantics",
    "拥塞控制在吞吐与公平之间动态调节": "Congestion control dynamically tunes between throughput and fairness",
    "端到端网络延迟来自排队、协议、传输与处理": "End-to-end network latency comes from queueing, protocols, transport and processing",
    "cgroups把机器切成可调度的资源单元": "cgroups slice the machine into schedulable resource units",
    "io_uring与异步IO演进：系统调用省下的开销": "io_uring and the evolution of async IO: the overhead saved from system calls",
    "垃圾回收与内存分配决定延迟尾部": "Garbage collection and memory allocation decide the latency tail",
    "脏页回写在性能与崩溃丢失窗口间权衡": "Dirty page writeback balances performance against the crash-loss window",
    "虚拟内存与文件系统把地址和持久化分层": "Virtual memory and file systems layer addresses and persistence",
    "进程线程与系统调用构成执行边界": "Processes, threads and system calls form the execution boundary",
    "零拷贝把数据通路的CPU让给业务": "Zero-copy hands the data path's CPU back to the business",
    "tcpdump与抓包定位网络问题的现场方法": "tcpdump and packet capture: the field method for locating network problems",
    "优化收益递减决定何时该停手": "Diminishing returns decide when optimisation should stop",
    "基准测试必须先定义负载和测量误差": "Benchmarks must first define workload and measurement error",
    "市面Benchmark的设计读法：宏微与中间层基准": "How to read mainstream benchmark designs: macro, micro and mid-level benchmarks",
    "性能剖析与火焰图": "Performance profiling and flame graphs",
    "性能回归门禁：把性能预算写进CI": "Performance regression gates: writing performance budgets into CI",
    "性能问题定位方法": "A method for locating performance problems",
    "指标、日志、Trace与剖析各答一问，合起来才构成证据": "Metrics, logs, traces and profiling each answer one question; together they form evidence",
    "排队论给容量一个可推导的模型": "Queueing theory gives capacity a derivable model",
    "系统指标、结构化事件与观测方法": "System metrics, structured events and observation methods",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt29·标题批 6/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    pf_titles = {n["title"] for n in notes if n["category"].startswith("性能工程")}
    missing = pf_titles - set(TITLES) - {"性能工程：从用户等待到资源瓶颈"}
    extra = set(TITLES) - pf_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in extra:
            print("  extra:", t)
        sys.exit(1)

    lines = [
        "    /* 【rt29·标题批 6/7】性能工程域 39 篇（域总览已于 rt24 领域批译出，",
        "       本批插入其余 38 条）。方法论句式直译，保留冒号骨架。 */",
    ]
    for zh, en in TITLES.items():
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 5（数据系统）尾部最后一行。
    anchor = '    "慢查询治理从发现到索引闭环": { en: "Slow query governance: from discovery to index closure" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
