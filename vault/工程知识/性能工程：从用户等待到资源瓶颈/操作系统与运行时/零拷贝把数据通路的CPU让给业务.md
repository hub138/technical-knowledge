---
title: 零拷贝把数据通路的CPU让给业务
type: concept
status: active
updated: 2026-09-21
confidence: high
change_rate: low
review_after: 2029-03-21
tags:
  - linux/io
  - operating-systems/process
  - networking
  - performance/network
sources:
  - "https://www.kernel.org/doc/html/latest/networking/msg_zerocopy.html"
  - "https://man7.org/linux/man-pages/man2/sendfile.2.html"
  - "https://lwn.net/Articles/726917/"
---

# 零拷贝把数据通路的CPU让给业务

同一个"把文件内容发到网络"的动作，朴素实现要在内核态与用户态之间搬四次数据、上下文切换四次；零拷贝实现把搬运次数压到零或一。要解决的问题：数据通路上的 CPU 消耗不是花在业务逻辑上，是花在搬运数据上，高吞吐场景下这部分浪费直接吃掉 CPU 预算，指标准确地说出"CPU 花在 memcpy 上了"。

## 机制：四次搬运到零次搬运的演进

朴素 read+write 路径：内核从磁盘读页缓存（DMA 拷贝 1）、拷到用户缓冲区（CPU 拷贝 2）、write 时拷回 socket 缓冲区（CPU 拷贝 3）、网卡再从 socket 缓冲区 DMA 出去（拷贝 4），伴随 4 次上下文切换。演进路径每一步都消掉一部分：

![传统 read+write 路径的四次拷贝与系统调用往返（取自 SoByte《Zero-copy technology》，https://www.sobyte.net/post/2022-11/zero-copy/）](https://cdn.jsdelivr.net/gh/b0xt/sobyte-images1/2022/11/30/8be724f07a034ca5be182ce0f3610492.png)

这张图把四次拷贝的位置摆出来了：拷贝 1 和 4 由 DMA 完成，CPU 不参与；真正吃 CPU 的是拷贝 2 和 3——数据只是经过用户空间转了一圈，应用并没有改它。两次 CPU 拷贝加上四次系统调用往返，就是后续每一步演进要消掉的账。

| 技术 | 消掉的拷贝 | 消掉的切换 | 约束 |
| --- | --- | --- | --- |
| sendfile(2) | 拷贝 2、3 | 2 次 | 文件→socket 单向 |
| sendfile + SG-DMA | 拷贝 2、3、4 | 2 次 | 网卡支持 scatter-gather |
| splice(2) | 2、3 | 2 次 | 管道中转，两个 fd 间 |
| mmap+write | 拷贝 2 | 1 次 | 映射管理开销、页错误 |
| msg_zerocopy | socket 发送缓冲的拷贝 | 0 | 超大包才划算，需回调处理 |

![sendfile 路径：数据全程不进用户空间，四次拷贝降为三次（取自 SoByte《Zero-copy technology》，https://www.sobyte.net/post/2022-11/zero-copy/）](https://cdn.jsdelivr.net/gh/b0xt/sobyte-images1/2022/11/30/6b8f376617044687ab371e6878207623.png)

对照上一张图：用户空间只剩系统调用的进出，数据本身不再绕道用户程序 buffer，拷贝 2、3 合并为内核内的一次 CPU 拷贝；网卡支持 scatter-gather 后这次拷贝也只剩描述符，CPU 拷贝归零。演进不是换了更快的拷贝，是把「数据要经过用户空间」这个结构假设拆掉了。

收益与代价的权衡：CPU 从通路让出、缓存污染减少，但 API 约束变多（sendfile 只能文件到 socket）、对网卡特性有要求、错误处理路径更绕。什么时候不划算：小包高频场景里 syscall 本身的开销占比高，msg_zerocopy 官方文档给出的经验阈值是数据量大于约 10KB 才值得。

## 案例回流与量化锚点：拷贝路径的实录

量化锚点：传统读文件发网络包的四次拷贝四次切换——read（磁盘到页缓存，DMA）→ 用户缓冲区（CPU 拷贝）→ socket 缓冲区（CPU 拷贝）→ 网卡（DMA），`sendfile` 把两次 CPU 拷贝合并为一次描述符传递，CPU 占用降 40-60%（大文件场景），Kafka 单机百万级消息吞吐的基础就是 sendfile 加页缓存。案例回流的实录：网关类服务在用户态做一次多余拷贝（先读进业务 buffer 再写回 socket）的代价在压测里现形——CPU 全在 sys 态，业务线程饿住，P99 随流量直线涨；改 sendfile 或 splice 后 sys 占比降半，同样的容量上限翻倍。适用边界的实录：TLS 加密链路不能直接 sendfile（数据要先进用户态加密），HTTPS 网关的优化路径改为 kTLS（内核态加密）或接受拷贝——机制有前提，前提变化优化归零。同域的地址层账见 [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/虚拟内存与文件系统把地址和持久化分层.md]]（mmap 的页错误代价）——零拷贝与内存映射是同一目标（把 CPU 从数据搬运里解放）的两条实现路径，选哪条看数据要不要被业务碰。

## 验证

```bash
# 对比 sendfile 与 read/write 的 CPU 与吞吐（服务器自带基准）
# nginx 配 sendfile on/off 各压一轮，同负载对比：
wrk -t8 -c100 -d30s --latency http://host/bigfile
perf stat -e context-switches,cpu-migrations ./server
```
预期：sendfile 开启后同吞吐的 CPU 占用下降（上下文切换次数减半）。内核文档 msg_zerocopy 一章有完整的吞吐对比数据可当基线。

## 边界

本篇讲 OS 通路层的搬运消除。文件系统层（页缓存的角色）见 [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/虚拟内存与文件系统把地址和持久化分层|虚拟内存与文件系统把地址和持久化分层]]；存储队列层见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/存储IO性能取决于访问模式、队列与持久化语义|存储IO性能取决于访问模式、队列与持久化语义]]。内核旁路（DPDK/kernel bypass）是另一档：零拷贝仍在内核协调下，旁路把整个协议栈搬进用户态，适用场景与代价不同。TLS 加密与零拷贝的叠加（加密强制触碰数据）见 [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/TLS握手与证书链决定连接建立成本|TLS握手与证书链决定连接建立成本]]。

## 相关

- [[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/存储IO性能取决于访问模式、队列与持久化语义]]——IO 路径分为多层，零拷贝是其中通路优化
- [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/虚拟内存与文件系统把地址和持久化分层]]——mmap 一系的机制底座
- [[工程知识/性能工程：从用户等待到资源瓶颈/操作系统与运行时/io_uring与异步IO演进：系统调用省下的开销.md]] —— 消切换与消拷贝是数据通路降本的两条轴
