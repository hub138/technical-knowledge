---
title: HTTP语义的分层：方法、状态码与头部的约定角色
type: concept
status: active
updated: 2026-09-23
review_after: 2027-03-23
change_rate: low
confidence: high
tags:
  - web/http
  - api
  - backend/api
  - compatibility
sources:
  - "https://www.rfc-editor.org/rfc/rfc9110"
  - "https://www.rfc-editor.org/rfc/rfc9111"
  - "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status"
  - "https://www.rfc-editor.org/rfc/rfc9457"
---

# HTTP语义的分层：方法、状态码与头部的约定角色

HTTP 的方法、状态码、头部回答的是三个不同问题：**这个动作是什么性质**（方法）、**这次结果由谁负责**（状态码）、**这条消息该被怎么处理**（头部）。把三者混在一起用，最常见的后果不是"不优雅"，而是网关、SDK 和重试逻辑按错误的前提做决策——同一个接口，在直连时正常，经过一层代理就开始重复下单或缓存串味。

分层的判据很简单：能不能只看其中一层就做出正确处理？能，说明分层成立；不能，说明那层被塞了不属于它的信息。

## 方法层：动作的性质

方法表达语义，而不是实现。RFC 9110 的划分里实际有用的是两条属性：

| 属性 | 含义 | 例子 |
|---|---|---|
| safe（安全） | 不产生服务端状态变化，可被预取、爬虫、预连接触发 | GET、HEAD |
| idempotent（幂等） | 重复执行与执行一次效果相同 | GET、PUT、DELETE |

POST 两者都不保证。它不是"创建"的同义词，而是"语义未定、由资源自己解释"的兜底动作——所以把写操作挂到 GET 上（"用 URL 参数触发状态变更"）会让预取、扫描器和浏览器预连接变成真实的写请求，这类事故在生产环境反复出现（参见 [[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/幂等性的完整谱系：从操作语义到删除接口的天然陷阱]]）。

方法的幂等是**契约**，不是实现保证：声明 DELETE 幂等，服务端就必须做到第二次删除返回同样的终态，而不是 404 报错。

## 状态码层：结果由谁负责

状态码的首要读者不是人，是中间件和调用方代码。它回答"下一步该谁动"：

- **2xx**：服务端接受并处理了。201 表示创建了新资源，202 表示已接受但尚未完成。
- **3xx**：需要再走一步。301/308 是永久、302/307 是临时；307/308 保持方法不变，302 在历史上允许把 POST 降级成 GET——这是表单提交被改成 GET 重放的根源。
- **4xx**：调用方这边的问题，**原样重试必然再失败**。400 格式错、401 未认证、403 已认证但不允许、404 不存在、409 与当前状态冲突、422 语义正确但业务规则不满足、429 限流。
- **5xx**：服务端这边的问题，**可以重试**，但要带退避和上限。

两个高频错误：

1. **统一返回 200，失败写在 body 的 code 里**。这样网关、负载均衡的健康判断和客户端的重试都失去信号，错误只能靠解析 body 才能发现——而多数 SDK 只在 HTTP 层做重试。
2. **用 500 表达参数错误**。调用方会把可重试和不可重试的两类失败混成一类，于是参数错误被无限重试。

业务域的错误细节不该塞进状态码（HTTP 状态码是有限的公共词汇），正确做法是状态码给出分类，body 用稳定的 `code + message + details + request_id` 给出细节，错误响应格式见 RFC 9457 的 Problem Details。

## 头部层：这条消息怎么被处理

头部是元数据通道，也是最容易"配了但没生效"的一层：

- **缓存**：`Cache-Control`（max-age、no-store、must-revalidate）、`ETag` / `Last-Modified` 配合条件请求 `If-None-Match`，返回 304 复用本地副本。缓存键由 URL 加 `Vary` 声明的请求头共同决定——漏配 `Vary: Accept-Encoding` 或 `Vary: Origin`，会让不同表示互相覆盖。缓存改变读写路径与失效模式的完整讨论见 [[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/缓存改变读写路径、一致性与故障模式]]。
- **限流反馈**：429 或 503 带 `Retry-After`，让调用方知道该等多久，而不是自行猜一个退避值。
- **追踪**：`traceparent`（W3C Trace Context）与 `request-id`，把一跳一跳的观测串成一条链路；请求穿过各层边界时的观测点见 [[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/HTTP请求穿过浏览器、网络与服务端边界]]。
- **逐跳 vs 端到端**：`Connection` 及逐跳头部只作用于相邻一跳，代理不应把它们转发下去；端到端头部才会到达最终服务端。把两者搞混，会出现"本地直连正常、过一层代理就丢头"的现象。

真实报文里头部层长什么样，Cloudflare 学习站贴了两屏 DevTools 截图——请求头一屏、响应头一屏，正文讲的字段都在里面：

![Cloudflare Learning Center 截图：一次对 www.google.com 的 GET 请求的 Request Headers 面板——伪头部 :authority、:method、:path、:scheme（HTTP/2 形态）之后是 accept: text/html、accept-encoding: gzip, deflate, br、accept-language、upgrade-insecure-requests、user-agent 等端到端头部逐行列出](https://www.cloudflare.com/img/learning/ddos/glossary/hypertext-transfer-protocol-http/http-request-headers.png)

![Cloudflare Learning Center 截图：对应的 Response Headers 面板——cache-control: private, max-age=0、content-encoding: br、content-type: text/html; charset=UTF-8、date、status: 200、strict-transport-security: max-age=86400、x-frame-options: SAMEORIGIN 逐行列出，缓存语义与安全策略都通过头部声明](https://www.cloudflare.com/img/learning/ddos/glossary/hypertext-transfer-protocol-http/http-response-headers.png)

来源：Cloudflare Learning Center，[What is HTTP?](https://www.cloudflare.com/learning/ddos/glossary/hypertext-transfer-protocol-http/)。两屏合起来正是"头部是元数据通道"的实物：请求屏的 `accept-encoding` 与响应屏的 `content-encoding: br` 是一次内容协商的两端，响应屏的 `cache-control` 决定中间每一层代理能缓存多久——头部层配错了，图里这两屏的任何一个字段都是故障现场。

## 边界

- 状态码表达**协议层**结果，不表达业务结果：订单被风控拒绝是 200 还是 422，取决于它是不是协议意义上的失败，实践中按"调用方能否用同一套重试逻辑处理"来划。
- 幂等是**契约声明**：声明了幂等却没有幂等键或条件更新支撑，重复请求照样产生两份副作用。
- 缓存的正确性依赖头部与方法的配合：对非安全方法做缓存，或忽略 `Vary`，都属于配置错误而不是调优空间。

## 验证路径

```bash
# 看真实的状态码、缓存与限流头部（-i 带响应头）
curl -si https://api.example.com/v1/orders/42 | head -20

# 条件请求：带 ETag 应回 304，不带应回 200
ETAG=$(curl -sI https://api.example.com/v1/orders/42 | awk '/[Ee]Tag/{print $2}' | tr -d '\r')
curl -si -H "If-None-Match: $ETAG" https://api.example.com/v1/orders/42 | head -1

# 幂等验证：同一个 Idempotency-Key 连发两次，结果应一致
curl -s -X POST -H 'Idempotency-Key: test-key-1' -d '{"sku":"A","n":1}' https://api.example.com/v1/orders
curl -s -X POST -H 'Idempotency-Key: test-key-1' -d '{"sku":"A","n":1}' https://api.example.com/v1/orders
```

判据：非 2xx 里，4xx 原样重试必然失败、5xx 与 429 重试应当最终成功；带 `If-None-Match` 的重复请求回 304；相同幂等键的两次 POST 只产生一份副作用。三条中任何一条不成立，都是语义分层被破坏，而不是"客户端写得不对"。
