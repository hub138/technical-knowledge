---
title: NUMA让跨槽访问付出带宽与延迟代价
type: concept
status: active
updated: 2026-09-25
confidence: high
change_rate: low
review_after: 2029-03-21
tags:
  - hardware
  - performance/cpu
  - systems/memory
  - memory
sources:
  - "https://www.hpl.hp.com/techreports/2012/HPL-2012-61.pdf"
  - "https://akkadia.org/drepper/cpumemory.pdf"
  - "https://www.kernel.org/doc/html/latest/admin-guide/mm/numapolicy.html"
editorial_pass: 3
editorial_at: 2026-09-25
editorial_by: with-numa-r1
editorial_note: "验证节补 lstopo 实机拓扑图（hwloc 项目，BSD，镜像站内），中文三轮检索（RedHat 403/CSDN TLS 失败/博客园尺寸不足后取 Commons 官方截图）；表达修复 6 处：问题节独立成节恢复 problem 信号、NUMA 定义前移首现、UPI/Infinity Fabric/HITM/distance/Drepper 补释、mermaid 补跨槽访存边、预写句消歧、图文数字断言弱化。双模型评审 remaining 全处理，桌面 1440 与窄屏 390 双档渲染验收通过"
editorial_dims: [text, image]
---

# NUMA让跨槽访问付出带宽与延迟代价

多路服务器里每个 CPU 槽位独占本地内存，访问别的槽位要过互联总线。

## 要解决的问题

线程跑在 A 槽、数据分配在 B 槽时，每次访存都要穿过互联总线，带宽减半、延迟翻倍，而这类损失在常规指标里不可见——top 看不出内存是远程的，必须用 NUMA（Non-Uniform Memory Access，非统一内存访问）视角的工具才能看到。本篇回答：跨槽访问贵在哪、代价怎么随拓扑级联、它和伪共享怎么区分、用什么实验把这笔账对出来。

## 机制：本地内存与远程内存的代价表

![伪共享随线程数增长的示意：多个核反复写同一缓存行的不同部分，吞吐被一致性流量拖住](/static/figures/scaling-of-false-sharing.png)

*图源：Wikimedia Commons《Scaling of false sharing》，作者 Vibrant franklin，CC0，https://commons.wikimedia.org/wiki/File:Scaling_of_false_sharing.svg。这张图讲的是另一种"距离"：数据离得近不等于访问便宜，跨核与跨槽都会把一次写入变成一致性流量——NUMA 的代价表是同一条规律在更大的物理尺度上。*

NUMA 的物理拓扑：每个 socket（即上文说的 CPU 槽位）直连自己的内存控制器（本地内存），socket 之间靠 UPI（Intel 的槽间互联 Ultra Path Interconnect）/Infinity Fabric（AMD 的对应互联）互联。跨槽访问一次的成本见下表：

两个槽位各带本地内存、经互联总线相连，跨槽与本地访问走的路径不同：

```mermaid
graph TD
    C0[CPU 槽0] -->|本地访存| M0[(槽0 本地内存<br/>70-100ns)]
    C0 -->|跨槽走 UPI| C1[CPU 槽1]
    C1 -->|本地访存| M1[(槽1 本地内存<br/>70-100ns)]
    C0 -.->|远程访存：延迟 1.5-2x、带宽下降| M1
```

| 访问路径 | 相对代价 | 说明 |
| --- | --- | --- |
| 本地 DRAM | 1x（基线） | 约 70-100ns |
| 远程 DRAM（跨槽） | 延迟 1.5-2x，带宽显著下降 | 走互联总线，与对向流量竞争 |
| 本地 LLC 命中 | 约 1/3 基线 | 末级缓存吸收 |
| 互联总线饱和 | 全局带宽塌陷 | 所有人抢同一条总线 |

代价随拓扑级联：2 槽是单跳，4 槽常见两级（NUMA distance 不止两档）。收益是多路扩容的内存容量与核数；代价是"内存位置"从硬件细节变成软件必须管理的资源，调度器、分配器、线程绑定都要参与。

与伪共享（false sharing）的区分：伪共享是缓存一致性问题——两个核各写不同变量，但变量位于同一个缓存行（64B），一致性协议让这行在两个核的缓存间来回弹，写吞吐塌到总线速度。它发生在单槽内部甚至单核内部，与 NUMA 无关；两者叠加时（跨槽伪共享）最致命。

## 验证

跨槽代价要与绑定对照对账——预先写明同一基准在全本地与跨节点两种绑定下的预期延迟差，实测对不上就说明访存热点并不在远端节点。

公开可复现的实测方法：
```bash
numactl --hardware          # 看 NUMA node 拓扑与 distance 矩阵
numactl --cpunodebind=0 --membind=1 ./benchmark   # 故意跨槽：内存绑到 node1
numactl --cpunodebind=0 --membind=0 ./benchmark   # 全本地对照
perf c2c record -a -- ./benchmark                  # perf c2c 直接定位伪共享缓存行
```

对照跨槽与本地的吞吐差即互联代价。伪共享用 perf c2c 的 HITM（Hit In Modified，命中其他核处于 Modified 状态的缓存行）事件直接抓到地址级证据。绑定实验之前先用 lstopo 看一眼真实拓扑长什么样：

![4 路服务器的 lstopo 实机拓扑：4 个 NUMA node，每槽独占本地内存与 L3，32 个逻辑核跨槽编号](/static/figures/lstopo-ccnuma-4socket.png)

*图源：hwloc 项目《Portable Hardware Locality》文档示例图（Open MPI 项目，BSD 许可），https://commons.wikimedia.org/wiki/File:Hwloc.png。*

四个 NUMA node 各带本地内存，L3 与缓存层级都收在槽内，逻辑核编号连续跨过四个槽——进程被调度器挪一个槽，本地内存就换了一片。这种实机视图是 numactl --hardware 输出的图形版：那条命令里的 node distance 矩阵（节点两两之间的相对访问成本，10 为本地基准，数值越高越贵）是绑定前应确认的前提。跨槽比对延迟的权威基线是 Drepper 的《What Every Programmer Should Know About Memory》实测表（Drepper 是 glibc 与该文档的作者），写代码时的直觉校准可以用它。

## 边界

本篇讲硬件拓扑级的代价机制。进程内并发原语（锁、原子操作）怎么尽量减少跨核缓存行争用，见 [[工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/Go并发以所有权、取消与错误传播为边界|Go并发以所有权、取消与错误传播为边界]]（把数据所有权收进单 goroutine 就消除伪共享）。JVM 的堆在 NUMA 上的分配策略属于运行时层，见 [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/垃圾回收与内存分配决定延迟尾部|垃圾回收与内存分配决定延迟尾部]]。内存带宽耗尽（本地也救不了）的容量判断见 [[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/排队论给容量一个可推导的模型|排队论给容量一个可推导的模型]]。容器环境里 NUMA 拓扑被 cgroup 掩盖的问题见 [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份|容器隔离资源边界与镜像身份]]。

## 相关

- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/ECC内存把单比特错误挡在报告之前|ECC内存把单比特错误挡在报告之前]]——同属处理器与内存的硬件基础层：NUMA 讲访问代价，ECC 讲可靠性代价
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/CPU性能来自有效执行与数据供给]]——数据供给是 CPU 性能的一半
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/CPU缓存与分支决定有效执行时间]]——缓存层级是 NUMA 代价的下游承接
- [[工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/CPU微架构与流水线：分支预测乱序执行对程序员的可见影响.md]] —— 跨槽访存代价与伪共享区分
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/网卡与内核旁路：中断与轮询的取舍.md]] —— 中断亲和性与跨槽代价
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/缓存行与伪共享：64字节里的并发性能.md]] —— 一致性粒度是缓存行，行内独立写也会乒乓失效
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/大页与TLB：地址翻译的隐藏成本.md]] —— TLB 与 NUMA 同在物理布局层收税：页覆盖半径与跨槽距离
