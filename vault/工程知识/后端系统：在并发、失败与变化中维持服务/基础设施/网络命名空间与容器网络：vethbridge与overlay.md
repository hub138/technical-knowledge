---
title: 网络命名空间与容器网络：vethbridge与overlay
type: concept
status: active
updated: 2026-09-22
review_after: 2027-09-22
change_rate: low
confidence: high
tags:
  - networking
  - infrastructure
  - devops/container
sources:
  - "https://man7.org/linux/man-pages/man7/netns.7.html"
  - "https://www.kernel.org/doc/html/latest/networking/bridge.html"
---

# 网络命名空间与容器网络：vethbridge与overlay

## 要解决的问题

容器网络要解决的问题，是让每个容器拥有"自己的一套网络"：独立的网卡、路由表、iptables 规则，互不干扰，又能按需连通。Linux 的答案是网络命名空间（netns）：内核把网络栈整个复制一份（loopback、路由表、邻接表、套接字列表），进程关进哪个 netns 就用哪套栈。容器隔离资源边界与镜像身份（见 [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份.md]]）给了进程的隔离单元，netns 给了这个单元的网络维度。剩下的问题是：两套互相看不见的栈，怎么通信？

## 三级连通方案（机制）

**veth 对：点对点管道**。veth 是一对虚拟网卡，从一端进必然从另一端出，内核把它做成连接两个 netns 的管道。容器 netns 里放一端（eth0），宿主 netns 里放另一端（vethxxx）。这是最底层的连通原语：有了管道，还要有人转发才能成网。

**bridge：把管道接成交换机**。单个 veth 只通一个容器，宿主里放一个 bridge（虚拟交换机，docker0 是默认实例），把所有容器的 veth 宿主端都插上去，容器间就能二层互通，再配上 NAT（iptables MASQUERADE）让容器借宿主 IP 出网。单机容器网络的默认形态（Docker bridge 模式）到此成型：netns 隔离 + veth 管道 + bridge 交换 + NAT 出网。

**overlay：跨主机的虚晃一层**。多主机时容器 IP 不能靠桥接直接通（宿主之间是三层路由），overlay 在底层网络之上再叠一个虚拟二层：VXLAN 把容器的二层帧封装进 UDP 报文，跨宿主传输后解封还原。每个宿主跑一个 vtep（隧道端点），宿主间组成 overlay 的交换平面。Kubernetes 的 CNI 插件（Calico、Flannel、Cilium）各有取舍：Flannel VXLAN 是朴素 overlay，Calico BGP 走三层路由不用封装，Cilium eBPF 在内核里改写转发路径。

## 背景与代价

思想背景：netns 进入内核（2007 年 2.6.24）是" namespaces 家族"的一环（pid/net/mnt/ipc/uts），思想源头是 1998 年的 FreeBSD jail：把系统的全局视图切成进程组的局部视图。veth/bridge 复用既有虚拟设备框架（bridge 是 2000 年前后的内核功能，早于容器十年），容器网络不是发明新机制，是把三个旧零件拼成新形态。overlay 的思想来自数据中心的大二层愿景（VMware VXLAN 2011 年标准化），容器集群把它继承下来。

最精巧的一笔是**"复用而非新造"的组合设计**。netns、veth、bridge、iptables、VXLAN 全部是既有内核机制，容器网络栈只是编排它们。这让整个方案随内核演进免费升级（内核修一个 bridge bug，所有容器网络受益），也让排障有据可查（每个零件都有独立的观测点）。代价要摆明：每加一层抽象丢一分性能与可观测性——veth+bridge 的转发路径比裸网卡多两次上下文切换，VXLAN 封装吃掉约 50 字节头与 MTU（1470 变 1420 之类的碎片问题），overlay 的包在宿主间抓包看到的是 UDP 不是原始帧，排障要逐层解封。跨主机网络的故障定位成本，是单机的数倍。

## 边界

- **overlay 的性能税在封装与解封**。同东西向流量走 VXLAN，吞吐低于 Calico 的裸 BGP 路由（少了封装开销）。大流量服务间通信选 CNI 时，封装方案（Flannel vxlan）与路由方案（Calico）的实测差距要进选型依据，不能只看易用性。
- **NAT 模式遮蔽了源地址**。容器出网经 MASQUERADE，外部看到的源 IP 是宿主的。服务收到的"客户端地址"失真，日志、限流、地域调度都拿不到真实源。Docker 的 userland-proxy、Kubernetes 的 externalTrafficPolicy: Local 都是对这个失真的补救，各有代价（前者加一跳，后者牺牲节点间负载均衡）。
- **netns 隔离的是栈不是带宽**。两个容器在同一宿主共享物理网卡，netns 没有任何带宽隔离，一个容器打满网卡，邻居全部卡顿。带宽控制要靠 tc（traffic control）或 Cilium 的带宽管理，隔离单元与网络单元不是一回事。
- **容器网络排障的层次纪律**：先在容器 netns 内看（ip addr、路由表、ping 网关），再切到宿主看 veth 与 bridge（brctl show、tcpdump -i docker0），最后看 overlay 隧道（宿主间 vtep 抓包）。跳层排查（直接在宿主抓 overlay 包）会把三层问题搅在一起。进入任意 netns 的方法：`nsenter -t <pid> -n ip addr`，这是排障第一命令。

## 验证

- **隔离验证**：两个容器互 ping 容器 IP，预期通；`nsenter -t <容器pid> -n ip route` 预期看到独立的路由表（默认网关是 bridge 网段的网关地址）。若两容器看到了同一张路由表，隔离没生效，查运行时是否共享了 netns（如 --network=container:x）。
- **连通链验证**：宿主 `brctl show docker0`（或 `ip link show master docker0`），预期所有运行容器的 veth 宿主端都挂在 bridge 上。容器不通外网时，逐跳查：容器内 ping 网关 → 宿主 tcpdump -i docker0 看包是否到了 bridge → 看 NAT 规则 `iptables -t nat -L -n` 的 MASQUERADE 是否命中计数在涨。
- **overlay 路径验证**：跨宿主两容器互 ping，宿主间抓 UDP 4789 端口（VXLAN 默认），预期看到封装报文在飞；解封后（tcpdump -e 看内层）源目 IP 是容器 IP。若宿主间没有 VXLAN 报文但容器"通了"，说明走了别的路径（hostNetwork 或路由直通），网络模型与声明不符，要修正文档。

## 相关

- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份.md]] —— 隔离单元与网络维度的关系
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/代理与网关的谱系：正向反向与sidecar各自解决什么.md]] —— sidecar 共享 netns 的部署基础
- [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/词汇即接口：Linux与容器命令的词源与设计.md]] —— ip/netns 命令族的设计语义
