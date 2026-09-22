# -*- coding: utf-8 -*-
"""rt27: 软件构建域 56 篇文章标题的英文词条插入 i18n.js（标题批 4/7）。

背景：EN 态全站标题翻译，批 1（AI 系统工程 94 篇）、批 2（缺陷分析 60 篇）、
批 3（后端系统 59 篇）已完成。本批覆盖软件构建域全部 56 篇，其中域总览
1 篇已在 rt24 领域批译出（查重核实），故本脚本插入其余 55 条。
标题多为方法论句式，按原句语义直译、保留冒号骨架。幂等：已有标记则跳过。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "site" / "i18n.js"
NOTES = Path("/tmp/notes-rt27.json")

TITLES = {
    "Docker与K8s词汇的设计逻辑": "The design logic of Docker and K8s vocabulary",
    "Git 操作先区分工作区、索引与历史": "Git operations start by separating the working tree, index and history",
    "Linux常用命令的词源地图": "An etymological map of common Linux commands",
    "Linux 调查先收集事实再改变状态": "Linux troubleshooting collects facts before changing state",
    "Make 描述依赖图，不自动保证可重复构建": "Make describes the dependency graph; it does not guarantee reproducible builds",
    "依赖供应链需要锁定来源与构建输入": "Dependency supply chains need locked sources and build inputs",
    "依赖升级按风险分层，兼容性验证跟着层走": "Dependency upgrades are tiered by risk; compatibility verification follows the tiers",
    "依赖升级的半衰期策略：跟随与锁定的平衡": "A half-life strategy for dependency upgrades: balancing following and locking",
    "本地复现环境是修线上问题的第一现场": "A local reproduction environment is the first crime scene for production issues",
    "维护者信任是供应链信任的地基：贡献者治理与维护者变更审计": "Maintainer trust is the foundation of supply-chain trust: contributor governance and maintainer-change audits",
    "词汇即接口：Linux与容器命令的词源与设计": "Vocabulary is the interface: the etymology and design of Linux and container commands",
    "静态分析在门禁里定位为证据生成器": "Static analysis is positioned in the gate as an evidence generator",
    "API 与 Schema 演进必须兼容新旧消费者": "API and schema evolution must stay compatible with old and new consumers",
    "API演进的兼容性纪律：废弃流程与版本策略": "The compatibility discipline of API evolution: deprecation flows and versioning strategy",
    "AST 提供语法结构，语义仍需符号与运行证据": "ASTs provide syntactic structure; semantics still need symbol and runtime evidence",
    "分层与依赖方向决定可测试性和演进成本": "Layering and dependency direction decide testability and evolution cost",
    "技术方案先写清约束、取舍与验证": "Technical designs start by stating constraints, trade-offs and verification",
    "架构组织高成本决策与演进边界": "Architecture organises high-cost decisions and evolution boundaries",
    "架构适应度函数：把架构约束写成可执行检查": "Architecture fitness functions: turning architectural constraints into executable checks",
    "状态机把隐式状态变成显式约束": "State machines turn implicit state into explicit constraints",
    "策略与依赖注入把变化关在边界外": "Strategy and dependency injection lock change outside the boundary",
    "绞杀者模式用增量迁移替代整体重写": "The strangler pattern replaces wholesale rewrites with incremental migration",
    "编译器与 JIT 把源码变成可执行行为": "Compilers and JITs turn source code into executable behaviour",
    "装饰器与中间件把横切关注点串成链": "Decorators and middleware chain cross-cutting concerns together",
    "观察者与事件解耦发布者与订阅者": "Observers and events decouple publishers from subscribers",
    "设计模式解决的是变化点的隔离，不是代码复用": "Design patterns solve the isolation of variation points, not code reuse",
    "购买与自建的决策框架：每条约束都摆上桌面": "A build-vs-buy decision frame: putting every constraint on the table",
    "适配器与防腐层隔离外部模型": "Adapters and anti-corruption layers isolate external models",
    "重构的安全边界由测试网和绞杀者模式共同划定": "The safe boundary of refactoring is drawn jointly by test nets and the strangler pattern",
    "错误处理是策略问题，异常只是运输手段": "Error handling is a policy question; exceptions are just transport",
    "错误处理的分类学：错误类型与恢复策略的映射": "A taxonomy of error handling: mapping error types to recovery strategies",
    "静态分析发现结构问题但不能证明行为正确": "Static analysis finds structural problems but cannot prove behaviour correct",
    "领域建模的落地路径：从事件风暴到聚合边界": "A landing path for domain modelling: from event storming to aggregate boundaries",
    "AI 做顶级 UI 设计：从创作到验证的完整回路": "AI doing top-tier UI design: a complete loop from creation to verification",
    "CI 流水线把反馈速度和发布证据连接起来": "CI pipelines connect feedback speed with release evidence",
    "发布门禁必须绑定真实证据": "Release gates must bind to real evidence",
    "可观测性断言：把运行时行为写进测试": "Observability assertions: writing runtime behaviour into tests",
    "契约测试的适用边界：消费者驱动与提供者验证": "The applicable boundary of contract testing: consumer-driven and provider verification",
    "测试替身按依赖行为而非名字分类": "Test doubles are classified by dependent behaviour, not by name",
    "测试策略从风险选择证据": "Test strategy selects evidence from risk",
    "混沌工程验证系统是否真的能处理故障": "Chaos engineering verifies whether the system can really handle failures",
    "灰度与功能开关的边界：交付节奏与配置漂移": "The boundary of canary releases and feature flags: delivery cadence and configuration drift",
    "覆盖率的三种读法：行分支与路径覆盖的证据强度": "Three readings of coverage: the evidential strength of line, branch and path coverage",
    "调试从假设到最小复现": "Debugging goes from hypothesis to minimal reproduction",
"配置与特性开关分离部署与发布": "Configuration and feature flags separate deployment from release",
    "静态分析的证据边界：它证明什么不证明什么": "The evidential boundary of static analysis: what it proves and what it does not",
    "算法复杂度连接规模与资源成本": "Algorithmic complexity links scale to resource cost",
    "CPU微架构与流水线：分支预测乱序执行对程序员的可见影响": "CPU microarchitecture and pipelines: the visible impact of branch prediction and out-of-order execution on programmers",
    "Go 并发以所有权、取消与错误传播为边界": "Go concurrency is bounded by ownership, cancellation and error propagation",
    "Python 并发先区分协程、线程、进程与解释器": "Python concurrency starts by distinguishing coroutines, threads, processes and interpreters",
    "Python 数据访问必须显式拥有连接与事务": "Python data access must explicitly own connections and transactions",
    "Spring 代理与 Bean 生命周期会改变调用边界": "Spring proxies and bean lifecycles change invocation boundaries",
    "TypeScript 类型边界与 Node 事件循环共同约束服务": "TypeScript type boundaries and the Node event loop jointly constrain services",
    "内存模型决定并发读写何时可见": "Memory models decide when concurrent reads and writes become visible",
    "跨语言并发模型必须同时比较抽象与运行机制": "Cross-language concurrency models must compare abstraction and runtime mechanics together",
}

def main():
    src = I18N.read_text(encoding="utf-8")

    marker = "rt27·标题批 4/7"
    if marker in src:
        print("already inserted; skip")
        return

    data = json.loads(NOTES.read_text(encoding="utf-8"))
    notes = data.get("notes", data) if isinstance(data, dict) else data
    be_titles = {n["title"] for n in notes if n["category"].startswith("软件构建")}
    missing = be_titles - set(TITLES) - {"软件构建：让变化可以理解、验证与交付"}
    extra = set(TITLES) - be_titles
    if missing or extra:
        print("MISMATCH vs notes")
        for t in sorted(missing):
            print("  missing:", t)
        for t in sorted(extra):
            print("  extra:", t)
        sys.exit(1)

    lines = [
        "    /* 【rt27·标题批 4/7】软件构建域 56 篇（域总览已于 rt24 领域批译出，",
        "       本批插入其余 55 条）。方法论句式直译，保留冒号骨架。 */",
    ]
    for zh, en in TITLES.items():
        lines.append("    %s: { en: %s }," % (json.dumps(zh, ensure_ascii=False), json.dumps(en, ensure_ascii=False)))
    block = "\n".join(lines) + "\n"

    # 锚点：批 3（后端系统）尾部最后一行。
    anchor = '    "连接池的容量数学：池大小与排队等待的权衡": { en: "The capacity math of connection pools: sizing versus queueing wait" },\n'
    if anchor not in src:
        print("anchor not found")
        sys.exit(1)
    src = src.replace(anchor, anchor + block, 1)

    I18N.write_text(src, encoding="utf-8")
    print("inserted", len(TITLES), "title entries")

if __name__ == "__main__":
    main()
