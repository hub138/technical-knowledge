---
title: QUIC把传输握手与加密合流到用户态
type: concept
status: active
updated: 2026-10-02
confidence: high
change_rate: medium
review_after: 2028-09-22
tags:
  - "networking"
  - "web/http"
  - "performance/network"
  - "systems/network"
sources:
  - "https://www.rfc-editor.org/rfc/rfc9000"
  - "https://www.rfc-editor.org/rfc/rfc9001"
  - "https://blog.cloudflare.com/http3-the-past-present-and-future/"
---

# QUIC把传输握手与加密合流到用户态

读完你能判断自己的服务是否该上 QUIC（一个跑在 UDP 上的新一代传输协议），以及要付出哪些运维代价。传输协议在内核里走了四十年，QUIC（RFC 9000，2021 年标准化）把它搬到用户态 UDP（用户数据报协议，只管发、不保证到达与顺序）之上重做了一遍。

**要解决的问题：TCP（传输控制协议，负责把数据完整、有序地送达）的握手与 TLS（Transport Layer Security，传输层加密协议，HTTPS 里的 S）的握手是两条链，连接建立时间是两者相加；TCP 层一个丢包（数据包在网络传输途中丢失）会卡住这条连接上所有 HTTP 流（队头阻塞跨层泄漏：排在最前面的数据没到，后面所有数据只能干等）；协议行为改一次要等内核发版，演进周期以年计。QUIC 把传输层从内核抽到用户态库，一次重构同时处理这三件事。**

## QUIC 做了哪三条改造，各自代价是什么

**演进过程有依赖关系：先有 TLS 1.3（TLS 的当前主用版本）把加密握手压缩到 1-RTT。**RTT 即往返时间，一次请求加响应在网络上走一个来回的耗时，详见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/TLS握手与证书链决定连接建立成本|TLS 握手与证书链决定连接建立成本]]，**QUIC 才可能把传输握手与加密握手合并成同一次往返——QUIC 的初始包直接用 TLS 1.3 的 ClientHello（握手中客户端发出的第一个报文）承载传输参数。这条依赖解释了为什么 QUIC 标准化在 2021 年而非更早：加密层的先行成熟是前提。**

| 改造 | TCP+TLS 时代 | QUIC | 代价 |
| --- | --- | --- | --- |
| 握手合流 | TCP 1-RTT 与 TLS 1-RTT 串行 | 传输与加密一次握完，1-RTT 建连 | 传输头自带加密，中间盒无法审计，调试要专用工具 |
| 队头阻塞 | TCP 丢一个段，连接上所有流卡住 | 流间独立，丢包只阻塞所在流 | 丢包检测按包序号空间（packet number space）独立维护确认与重传状态，实现复杂度上升 |
| 演进速度 | 改内核，周期以年计 | 用户态库随应用发布 | 失去内核 TCP 快速通道（内核针对常见收发路径做的专门优化）与硬件卸载（把校验、分片等交给网卡处理）优化——用户态库不经过内核网络处理，自然用不上这些内核优化，换来的是随应用发布的演进速度 |

![TCP+TLS 时代的连接建立：TCP 三次握手与 TLS 握手串行进行，请求要等两条链走完（取自 Cloudflare《HTTP/3: the past, the present, and the future》，https://blog.cloudflare.com/http3-the-past-present-and-future/）](/static/figures/01kw44c99k9hk86vrfn0zfym3g.png)

这张图的延迟要按往返（RTT）算而不是**按包数：TCP 三次握手**（TCP 建立连接前、双方交换三个报文确认彼此收发能力的流程）占用 1 个 RTT（第三次握手的包可以捎带数据，但它仍要等前两次走完），TLS 1.3 握手再占 1 个 RTT，**合计约 2 个 RTT 之后才能发出第一个业务请求。串行是延迟的主因——这两段握手一个都不能省，也无法重叠。**


## 用了能拿到什么，要付什么代价

![QUIC 把传输与加密握手套进同一次往返，四个包之后就能发 HTTP 请求（取自 Cloudflare《HTTP/3: the past, the present, and the future》，https://blog.cloudflare.com/http3-the-past-present-and-future/）](/static/figures/01kw44qbzx9kagj4sdgg0dmywx.png)

对照上一张图：握手从八步压到四步，QUIC 包里每个包都自带加密帧，传输参数随 TLS ClientHello 报文一并发出，两条握手共用同一串往返——「合流」在图上的形态就是两类握手内容封装在同一批往返报文里，这是协议的真实机制，两类内容并未合并成一个报文。往返次数减半之外，每个包都加密也让中间设备无法按明文头做审计，这是表里「调试要专用工具」的来源。

合流的收益在重复连接（0-RTT 恢复：复用上一次会话凭据，第一个包就能带上业务数据，无需重新握手）场景被进一步放大。Cloudflare 官方博客的报文对比图：同样的 HTTP 请求，TCP+TLS 路线即使带着 0-RTT 恢复凭据仍要走完 TCP 三次握手加 TLS 各阶段共八个报文，QUIC 路线合并后剩四个报文，首个请求随第一趟往返报文一并发出。

![TCP+TLS 路线的 0-RTT 恢复：三次握手与 TLS 各阶段仍是独立报文，首个 HTTP 请求要等握手收尾才能发出（取自 Cloudflare《Even faster connection establishment with QUIC 0-RTT resumption》，https://blog.cloudflare.com/even-faster-connection-establishment-with-quic-0-rtt-resumption/）](/static/figures/cloudflare-tcp-tls-0rtt.png)

![QUIC 路线的 0-RTT 恢复：传输与加密报文合并，首个 HTTP 请求随第一个包发出（取自同一篇 Cloudflare 博客）](/static/figures/cloudflare-quic-0rtt.png)

**收益与代价的权衡里最容易被忽略的一条：UDP 路径在企业网络与部分运营商处被限速或封禁，QUIC 部署必须保留 TCP 回退；服务端要同时跑 UDP 与 TCP 两套实现、两套监控与排查流程，运维要同时覆盖两套协议，成本显著上升（部署报告将其描述为接近翻倍）。**Cloudflare 的部署报告给出了大规模实测的建连收益与回退比例，验证本文断言时值得对照。

「流间独立」在图上的形态（同一张 Cloudflare 文章的对照图）：**HTTP/2（HTTP 第二版，多条流复用一条连接）的多个流复用在同一条 TCP 字节流上，一个包丢失在字节序列里开了一个洞（字节流里缺失的一段，序号不连续导致后续字节无法递交应用层），洞后面的字节即使属于无关的流也要等重传把这段补齐——阻塞是跨流的；QUIC 把每个流放进独立的包序号空间，丢包只卡住自己那条流**：

![HTTP/2 over TCP 与 HTTP/3 over QUIC 的队头阻塞对照：TCP 单一字节流被丢包卡住全部流，QUIC 各流独立确认](/static/figures/quic-hol-blocking.svg)

*图源：[Cloudflare《The Road to QUIC》](https://blog.cloudflare.com/the-road-to-quic/)。*


## 怎么自己动手验证

本节的验证全部用公开可复现的方式确认协议行为，命令与预期如下。
```bash
# curl 8.8+ 支持强制 QUIC，失败说明路径上 UDP 不通
curl -sI --http3-only https://quic.nginx.org/ && echo "QUIC OK"
# 对比建连时间：同站 HTTP/1.1+TLS 与 HTTP/3 各测十次取中位数
for i in $(seq 10); do curl -so /dev/null -w "%{time_appconnect}\n" --http1.1 https://quic.nginx.org/; done
for i in $(seq 10); do curl -so /dev/null -w "%{time_appconnect}\n" --http3-only https://quic.nginx.org/; done
```
预期：首次连接 HTTP/3（跑在 QUIC 上的新一代 HTTP）的 `time_appconnect`（加密握手完成时刻）低于 HTTP/1.1+TLS 串行——这里不能用 `time_connect`，QUIC 跑在 UDP 上，传输层连接几乎即时返回，量不到握手。

数字对不上时先查回退是否被触发（`--http3-only` 直接报错说明 UDP 路径不通，此时 QUIC 的收益讨论对该网络无效）。丢包场景的流隔离要专门工具观察：quiche（Cloudflare 出品的 QUIC 库）的 qlog（记录协议交互过程的日志格式）输出能看到单流阻塞不影响并发流吞吐。

## 这套说法在哪儿会失效

本篇讲传输层重构的动机、结构与代价。拥塞控制（发送方根据网络状况调整速率、避免压垮网络）在 QUIC 里把算法协商变成协议内的行为，不必再依赖内核版本——TCP 本来也支持按连接选择算法，QUIC 的差别在于协商随协议走、能随应用发布演进，机制本身见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/拥塞控制在吞吐与公平之间动态调节|拥塞控制在吞吐与公平之间动态调节]]，本文只补它部署位置的变化。

TCP 分层模型的原始设计见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/Socket与TCP把连接可靠性分成多层|Socket与TCP把连接可靠性分成多层]]，QUIC 是对它的重构而非否定。连接建立入口的 DNS（域名解析系统：把网址里的域名换成机器用的 IP 地址）环节 QUIC 并不改变，见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/DNS解析是延迟与故障的隐形入口|DNS解析是延迟与故障的隐形入口]]。

建连收益怎么换算成端到端延迟预算，见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/端到端网络延迟来自排队、协议、传输与处理|端到端网络延迟来自排队、协议、传输与处理]]。

## 接着该读哪几篇来补齐 TCP 分层基线？

- [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/Socket与TCP把连接可靠性分成多层|Socket与TCP把连接可靠性分成多层]]——被重构的 TCP 分层基线（正常状态下的指标水平、用来对比异常）
- [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/TLS握手与证书链决定连接建立成本|TLS握手与证书链决定连接建立成本]]——握手合流所依赖的 TLS 1.3 前提
- [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/拥塞控制在吞吐与公平之间动态调节|拥塞控制在吞吐与公平之间动态调节]]——QUIC 里变为可插拔的拥塞控制
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/TCP连接建立与断开的状态机：握手挥手与异常路径.md]] —— 握手成本的用户态重构路线
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/拥塞控制的四代演进：从AIMD到BBR的思路转变.md]] —— 拥塞控制在新传输协议里的可插拔装载
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/长连接网关的工程要点：心跳推送与连接迁移.md]] —— 协议层连接迁移的原生支持
- [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/QUIC之后的传输层：HTTP3与连接迁移的工程红利.md]] —— 握手合流的设计细节
