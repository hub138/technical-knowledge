---
title: cgroups把机器切成可调度的资源单元
type: concept
status: active
updated: 2026-09-22
confidence: high
change_rate: low
review_after: 2029-09-22
tags:
  - linux/operations
  - operating-systems/process
  - performance
  - systems
sources:
  - "https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html"
  - "https://facebookmicrosites.io/cgroup2/docs/overview"
  - "https://kubernetes.io/docs/concepts/scheduling-eviction/resource-quantities/"
---

# cgroups把机器切成可调度的资源单元

裸机上跑一百个进程，一个失控进程能把整台机器的内存、CPU、IO 全吃光，其余进程跟着陪葬。要解决的问题：把一台机器的资源切成按组隔离的配额单元，让"谁用了多少、谁超了被限制"变成内核强制执行的事实，而不是靠进程自觉。cgroups（control groups，控制组）就是内核提供的这个机制，容器的资源隔离底座。

## 机制：三个控制器与一张资源视角表

cgroups v2 的统一层级把资源控制器（controller）挂到同一棵树上，按路径继承。常用控制器：

| 控制器 | 管什么 | 关键参数 | 超限行为 |
| --- | --- | --- | --- |
| memory | 内存上限与回收 | memory.max | 超限触发 OOM kill 或回收 |
| cpu | CPU 带宽配额 | cpu.max（ period/quota ） | 超限节流（throttle），不杀进程 |
| io | 块设备带宽与 IOPS | io.max | 超限排队延迟 |

资源视角的关键区分：cgroups 限制的是"这个组能用多少"，CPU 亲和性（cpuset）决定"这个组在哪跑"。两者叠加出容器场景的完整资源画像。收益是隔离与可预测（noisy neighbor 邻居噪声被挡在配额外）；代价是配额语义的坑：cpu.max 按周期分片给时间片，Java 这类多线程进程在配额边界会被节流出延迟毛刺（周期内配额用完就等到下个周期），这是 JVM 容器化的经典问题，JVM 后来加了容器感知（UseContainerSupport）来感知配额。

与 NUMA 的关系：cpuset 可以绑定 NUMA node，把"内存位置"这个硬件约束映射进调度域，见 [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/NUMA让跨槽访问付出带宽与延迟代价|NUMA让跨槽访问付出带宽与延迟代价]]。

## 验证

```bash
# 建 v2 控制组、限额、观察节流
mount -t cgroup2 none /sys/fs/cgroup
echo "+cpu +memory" > /sys/fs/cgroup/cgroup.subtree_control
mkdir /sys/fs/cgroup/demo
echo "100000 50000" > /sys/fs/cgroup/demo/cpu.max   # 0.5 CPU
echo $PPID > /sys/fs/cgroup/demo/cgroup.procs
cat /sys/fs/cgroup/demo/cpu.stat                    # 看 nr_throttled
# 对比：无限制 vs 0.5 CPU 下的 sysbench
sysbench cpu --threads=4 --time=10 run
```
预期：0.5 CPU 配额下 nr_throttled 随负载上升，吞吐约减半；memory.max 下超限进程被 OOM kill（dmesg 可见）。数字对不上时先查是否混用 v1（v2 需要 unified hierarchy，`stat -fc %T /sys/fs/cgroup/` 输出 cgroup2fs 才对）。内核 cgroup-v2 文档是参数语义的权威来源，Facebook 的 cgroup2 运维报告是大规模实践的一手参考。

## 边界

本篇讲内核资源隔离机制。cgroups 之上的打包与交付（容器镜像、namespace 进程视图隔离）见 [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份|容器隔离资源边界与镜像身份]]，两篇分工：cgroups 管资源量、容器打包把它变成交付单元。调度器怎么在配额约束下放进程，见 [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/进程线程与系统调用构成执行边界|进程线程与系统调用构成执行边界]]。IO 控制器的队列视角见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/存储IO性能取决于访问模式、队列与持久化语义|存储IO性能取决于访问模式、队列与持久化语义]]。容器 JVM 的延迟毛刺问题属于运行时适配，见 [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/垃圾回收与内存分配决定延迟尾部|垃圾回收与内存分配决定延迟尾部]]。

## 相关

- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份|容器隔离资源边界与镜像身份]]——cgroups 的容器化封装
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/NUMA让跨槽访问付出带宽与延迟代价|NUMA让跨槽访问付出带宽与延迟代价]]——cpuset 与 NUMA 的交汇
