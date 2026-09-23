# -*- coding: utf-8 -*-
"""rt26: 后端系统域 59 篇文章标题的英文词条插入 i18n.js（标题批 3/7）。

背景：EN 态全站标题翻译，批 1（AI 系统工程 94 篇）、批 2（缺陷分析 60 篇）
已完成。本批覆盖后端系统域全部 59 篇，其中域总览 1 篇已在 rt24 领域批译过
（查重核实），故本脚本插入其余 58 条。标题多为方法论句式（非案例编号），
按原句语义直译、保留"主题：要点"冒号骨架。幂等：已有标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt26.json")

TITLES = {
    "任务生命周期必须覆盖进程、日志、超时与清理": "A task lifecycle must cover process, logs, timeouts and cleanup",
    "分布式锁的正确与错误用法：fencing与租约": "Distributed locks, right and wrong: fencing and leases",
    "后台任务不能依赖终端会话维持生命周期": "Background tasks cannot rely on a terminal session for their lifecycle",
    "幂等性的完整谱系：从操作语义到删除接口的天然陷阱": "The full spectrum of idempotency: from operation semantics to the natural trap of delete APIs",
    "并发控制先定义共享状态和完成条件": "Concurrency control starts by defining shared state and completion conditions",
    "调度必须同时处理优先级、公平与背压": "Scheduling must handle priority, fairness and backpressure together",
    "队列和流系统用时间与容量换取解耦": "Queues and stream systems trade time and capacity for decoupling",
    "限流熔断与隔离控制故障半径": "Rate limiting, circuit breaking and isolation control the failure radius",
"Raft选举与日志复制把共识变成工程实现": "Raft elections and log replication turn consensus into an engineering implementation",
"Saga把长事务变成补偿链，代价是失去隔离性": "Saga turns long transactions into compensation chains at the cost of isolation",
    "一致性模型与共识解决不同问题": "Consistency models and consensus solve different problems",
    "健康检查只能提供有时效的失败证据": "Health checks only provide time-limited evidence of failure",
    "分布式事务的分类与各自失败形态": "A taxonomy of distributed transactions and how each one fails",
    "复制分片与再平衡改变数据归属": "Replication, sharding and rebalancing change data ownership",
    "时间顺序与因果必须显式建模": "Time ordering and causality must be modelled explicitly",
    "消息投递与业务提交需要显式的一致性边界": "Message delivery and business commits need an explicit consistency boundary",
    "电源与时钟：UTC与单调钟的工程含义": "Power and clocks: the engineering meaning of UTC and monotonic time",
    "租约必须配合 Fencing Token 阻止过期持有者": "Leases must pair with fencing tokens to stop expired holders",
    "超时、重试与幂等共同定义调用语义": "Timeouts, retries and idempotency together define call semantics",
    "超时的层次设计：连接、读写与整链路的预算分配": "Layered timeout design: budgeting across connections, reads/writes and the full chain",
    "部分失败决定分布式系统的设计": "Partial failure dictates distributed-system design",
    "重试的正确姿势：退避、抖动与重试预算": "Retries done right: backoff, jitter and retry budgets",
    "CDN的回源与边缘缓存：静态加速背后的机制": "CDN origin fetches and edge caching: the mechanics behind static acceleration",
    "DNS解析的全链路：递归缓存与失效传播": "The full path of DNS resolution: recursive caching and invalidation propagation",
    "Kubernetes 管理资源状态，不管理业务正确性": "Kubernetes manages resource state, not business correctness",
    "QUIC之后的传输层：HTTP3与连接迁移的工程红利": "The transport layer after QUIC: HTTP/3 and the engineering dividends of connection migration",
    "TCP连接建立与断开的状态机：握手挥手与异常路径": "The TCP connection state machine: handshakes, teardown and abnormal paths",
    "TLS握手与证书链：信任是怎么一层层背书的": "The TLS handshake and certificate chains: how trust is endorsed layer by layer",
    "socket读写缓冲区：拥塞窗口与应用层背压的连接点": "Socket read/write buffers: where the congestion window meets application backpressure",
    "代理与网关的谱系：正向反向与sidecar各自解决什么": "A spectrum of proxies and gateways: what forward, reverse and sidecar each solve",
    "基础设施选型先比较责任边界与故障模型": "Infrastructure selection starts with comparing responsibility boundaries and failure models",
    "容器隔离资源边界与镜像身份": "Containers isolate resource boundaries and image identity",
    "容量规划与压测要用同一个负载模型说话": "Capacity planning and load testing must speak the same load model",
    "拥塞控制的四代演进：从AIMD到BBR的思路转变": "Four generations of congestion control: the shift in thinking from AIMD to BBR",
    "服务网格控制面与数据面：mTLS与流量治理": "Service mesh control plane and data plane: mTLS and traffic governance",
    "服务网格统一通信治理但不负责业务正确性": "Service meshes unify communication governance, not business correctness",
    "网卡与内核旁路：中断与轮询的取舍": "NICs and kernel bypass: the trade-off between interrupts and polling",
    "网络命名空间与容器网络：vethbridge与overlay": "Network namespaces and container networking: veth, bridge and overlay",
    "长连接网关的工程要点：心跳推送与连接迁移": "Engineering essentials of long-connection gateways: heartbeats, push and connection migration",
    "ACL 把权限挂在资源上": "ACLs attach permissions to resources",
"API 接口约定定义输入输出和演进边界": "API contracts define inputs, outputs and evolution boundaries",
    "HTTP语义的分层：方法、状态码与头部的约定角色": "HTTP semantics in layers: the contract roles of methods, status codes and headers",
    "HTTP 请求穿过浏览器、网络与服务端边界": "An HTTP request crosses browser, network and server boundaries",
    "RPC框架的通用骨架：序列化连接管理与超时传递": "A common skeleton for RPC frameworks: serialisation, connection management and timeout propagation",
    "事件驱动架构的解耦代价：最终一致与可追溯性": "The decoupling cost of event-driven architecture: eventual consistency and traceability",
    "优雅停机的完成语义：排空连接与任务交接": "The completion semantics of graceful shutdown: draining connections and handing over tasks",
    "健康检查的三层语义：存活就绪与深度": "Three levels of health-check semantics: liveness, readiness and depth",
    "分布式限流的四种算法：计数漏桶令牌与滑动窗口": "Four algorithms for distributed rate limiting: counters, leaky buckets, tokens and sliding windows",
    "容量估算的通用骨架：从峰值QPS到机器数的推导演练": "A general skeleton for capacity estimation: working from peak QPS to machine count",
"微服务划分的判据：从团队认知到数据边界": "Criteria for partitioning microservices: from team cognition to data boundaries",
"服务发现与负载均衡决定请求发往哪里": "Service discovery and load balancing decide where requests go",
    "服务降级是有损服务，损什么损多少要变成业务决策": "Service degradation is lossy serving: what to lose and how much must become a business decision",
    "流量入口只负责路由与连接，不负责业务正确性": "Traffic entry points handle routing and connections, not business correctness",
    "缓存改变读写路径、一致性与故障模式": "Caches change read/write paths, consistency and failure modes",
    "缓存穿透击穿与雪崩是三种不同的失效模式": "Cache penetration, breakdown and avalanche are three distinct failure modes",
    "背压的传递链路：从下游饱和到上游减速": "The propagation chain of backpressure: from downstream saturation to upstream slowdown",
    "认证授权决定请求能看什么和做什么": "Authentication and authorisation decide what a request can see and do",
    "连接池的容量数学：池大小与排队等待的权衡": "The capacity math of connection pools: sizing versus queueing wait",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt26·标题批 3/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    be_titles = {n["title"] for n in notes if n["category"].startswith("后端")}
    missing = be_titles - set(TITLES) - {"后端系统：在并发、失败与变化中维持服务"}
    extra = set(TITLES) - be_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in sorted(extra):
            print("  extra:", t)
        sys.exit(1)

    lines = [
        "    /* 【rt26·标题批 3/7】后端系统域 59 篇（域总览已于 rt24 领域批译出，",
        "       本批插入其余 58 条）。方法论句式直译，保留冒号骨架。 */",
    ]
    for zh, en in TITLES.items():
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 2（缺陷分析）尾部最后一行。
    anchor = '    "配置类缺陷的静态防线：schema校验与默认值审计": { en: "A static front line against configuration defects: schema validation and default-value audits" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
