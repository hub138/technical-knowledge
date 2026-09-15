---
title: Socket 与 TCP 把连接可靠性分成多层
type: concept
status: active
updated: 2026-09-03
review_after: 2027-09-03
change_rate: stable
confidence: high
tags:
  - systems/network
  - tcp
  - backend
sources:
  - "https://www.rfc-editor.org/rfc/rfc9293"
  - "https://man7.org/linux/man-pages/man7/socket.7.html"
  - "https://www.rfc-editor.org/rfc/rfc9000"
---

# Socket 与 TCP 把连接可靠性分成多层

它解决的是把“连接建立成功”误认为“请求一定完成”的问题。核心机制是把 DNS、连接、TLS、字节流、应用协议和业务提交分层，并在每层定义 deadline、取消和重试；收益是故障定位和恢复边界清晰，代价是状态与观测字段更多。用半开、RST、部分读、连接池耗尽和取消实验验证资源与副作用。

TCP 提供有序、可靠的字节流和拥塞控制，不提供消息边界、业务超时、请求幂等或“对端一定处理了”。Socket 还受 DNS、路由、防火墙、连接池、内核队列和应用读写循环影响。

## 一次请求经过什么

```text
解析/连接 -> SYN/TLS -> send buffer -> 网络/拥塞
           -> receive buffer -> 应用协议解析 -> 业务处理 -> 响应
```

`read` 可能只返回部分字节；EOF、RST、超时和连接复用分别表达不同事实。HTTP keep-alive、HTTP/2 multiplexing、QUIC/HTTP/3 改变连接和队头阻塞边界，但仍需应用 deadline、取消和重试语义。

## 性能与故障

RTT、拥塞窗口、带宽、丢包、TLS、Nagle、队列和服务器处理时间共同决定延迟。连接建立成功不代表服务健康；半开连接、连接池耗尽、端口耗尽和代理 idle timeout 会制造间歇性错误。

## 验证

用 trace 区分 DNS、connect、TLS、request write、server queue、TTFB 和 body read；注入丢包、延迟、半开、RST、连接复用和服务端超时。验证重试不会重复副作用，长响应取消会释放 socket 和服务端工作。

关系：[[工程知识/后端与分布式系统/服务设计/HTTP请求穿过浏览器、网络与服务端边界]] · [[工程知识/后端与分布式系统/分布式可靠性/超时、重试与幂等共同定义调用语义]]
