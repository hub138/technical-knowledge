---
title: HTTP语义的分层：方法、状态码与头部的约定角色
type: concept
status: active
updated: 2026-10-02
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
  - "https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Status"
  - "https://www.rfc-editor.org/rfc/rfc9457"
---



# HTTP语义的分层：方法、状态码与头部的约定角色

HTTP 的方法（GET（HTTP 读取资源的请求方法）、POST（HTTP 提交数据的请求方法）这样的动作词）、状态码（三位数字的结果码）、头部（消息附带的元数据字段）回答的是三个不同问题：**这个动作是什么性质**（方法）、**这次结果由谁负责**（状态码）、**这条消息该被怎么处理**（头部）——三问的划分出处是 RFC 9110 的请求语义定义。三者混用要解决的问题在网关（站在客户端与后端服务之间的入口层，集中处理路由、鉴权与协议转换）、SDK（软件开发工具包）和重试逻辑上：**它们按错误的前提做决策**，同一个接口直连时正常，**经过一层代理就开始重复下单或缓存串味**。读完你能判断**一个接口把信息放在哪一层才不出错**，并在网关与重试逻辑里避开重复下单、缓存串味。

怎样判断一层有没有被塞进不属于它的信息？**只看这一层能不能做出正确处理：能则分层成立，不能则那层被塞了别层的信息**。像快递面单分栏：收件地址、运费、保价各填各的栏，分拣机只看对应栏。这个比喻只到「各栏各司其职」为止，具体每层怎么协作看正文。延伸到 HTTP：**把本该由状态码传达的信息塞进头部，网关和重试逻辑就会读到错误的分类**。

## HTTP 方法表达的是动作的什么性质

先看 HTTP 在整个通信里处在什么位置，再看一次请求要经过哪些环节——语义是建立在这两层之上的约定。

![HTTP 报文的逐层封装：应用层 HTTP 报文经传输层加 TCP 首部、网络层加 IP 首部、链路层加以太网首部与尾部，接收端逐层剥离还原](/static/figures/http-layers.png)

*图源：MDN（Mozilla Developer Network，Web 技术权威文档站） Web Docs 中文版（Mozilla 贡献者），CC BY-SA 2.5，https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Overview。*

![HTTP 请求全过程：浏览器发起 DNS 解析与 TCP 连接，发出 HTTP 请求，服务器解析执行后返回响应，浏览器接收并渲染页面](/static/figures/http-request-process.png)

*Web 文档组成图示来源：同上 MDN Web Docs 中文版，CC BY-SA 2.5。*

![正向代理与反向代理对比：正向代理替客户端向服务器转发请求并隐藏客户端，反向代理在服务器侧接收请求再转给内部服务，两侧都改写转发链路](/static/figures/http-proxy-chain.png)

*代理链图示来源：同上 MDN Web Docs 中文版，CC BY-SA 2.5。*

中间那一串代理是理解头部语义的关键：请求和响应都要逐跳经过它们，而**每一跳代理都可能改写头部，端到端语义要跨这些节点维持**，所以头部必须区分**"这条消息整体怎么算"（端到端）和"这一跳怎么算"（逐跳）**。

方法到底表达什么？**只表达语义，不表达实现**。RFC 9110 的划分里实际有用的是两条属性：

| 属性 | 含义 | 例子 |
|---|---|---|
| safe（安全） | 不产生服务端状态变化，可被预取（浏览器提前请求资源）、爬虫（自动抓取网页的程序）、预连接（提前建立连接）触发 | GET、HEAD |
| idempotent（幂等） | 重复执行与执行一次效果相同 | GET、PUT、DELETE（HTTP 删除资源的请求方法） |

POST 两者都不保证。POST 的语义由资源自己解释，**属于"语义未定"的兜底动作**，创建资源只是它的一种用法——而 GET 被定义为安全，浏览器预取、爬虫抓取、预连接都会自动发出 GET。把写操作挂到 GET 上（"用 URL 参数触发状态变更"）之后，**这些自动请求就等于在执行写操作**，这类事故在生产环境反复出现（参见 [[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/幂等性的完整谱系：从操作语义到删除接口的天然陷阱]]）。

幂等（同一操作执行多次与执行一次效果相同）**是写进规范的约定声明，实现层面要专门做到**：声明 DELETE 幂等，服务端就必须做到第二次删除返回同样的终态，而不是 404 报错。做到它靠**幂等键（每次请求的唯一编号，供服务端识别这次请求是不是重放）**。

把幂等键比作餐厅的点单小票——重复递交同一张小票，厨房出的餐应与第一次一致；没有编号就只是重新点了一次单，会出两份。这个比喻到「编号对应小票」为止，服务端的去重机制看后文。

机制上，中间件按声明把它当作重试的前提，服务端实现没跟上时，**重试直接放大副作用（操作对外部状态产生的额外影响）——本该一次的扣款变成两次**。小票的比喻到此为止：真实机制里，靠的是**声明、中间件与实现三方各就各位**，比喻替换不掉这个机制。

## 状态码层：结果由谁负责

**状态码的首要读者是中间件（位于客户端与服务端之间的代理、网关等处理程序）和调用方代码**，人只看摘要。它回答"下一步该谁动"：

- **2xx**：服务端接受并处理了。201 表示创建了新资源，202 表示已接受但尚未完成。
- **3xx**：需要再走一步。301/308 是永久、302/307 是临时；307/308 保持方法不变，**302 在历史上允许把 POST 降级成 GET**——**浏览器收到 302 后会按 GET 重新发起跳转，原表单提交的语义被改成一次 GET 请求，这是表单被意外重放的根源**。
- **4xx**：调用方这边的问题，**原样重试必然再失败**。400 格式错、401 未认证、403 已认证但不允许、404 不存在、409 与当前状态冲突、422 语义正确但业务规则不满足、429 限流（控制单位时间放进来的请求数量，超过配额就拒绝）。
- **5xx**：服务端这边的问题，**可以重试**，但要带退避（每次失败后等更久再试）和上限（最多重试次数）。

两个高频错误：

1. **统一返回 200，失败写在 body 的 code 里**。这样**网关、负载均衡（把请求分发到多台服务器的组件）的健康判断和客户端的重试都失去信号**——**SDK 只识别 HTTP 状态码，读不到 body 里的业务 code**，于是既不报错也不重试，错误只能靠人工查看 body 才能发现。
2. **用 500 表达参数错误**。调用方会把**可重试和不可重试的两类失败混成一类**，于是参数错误被无限重试。

业务域的错误细节不该塞进状态码（HTTP 状态码是有限的公共词汇），**正确做法是状态码给出分类，body 用稳定的 `code + message + details + request_id` 给出细节**，错误响应格式见 RFC 9457 的 Problem Details（一种标准化的错误响应格式，固定包含 type、title、status、detail、instance 等字段）。

## 头部层：这条消息怎么被处理

头部这层为什么最容易"配了但没生效"？因为它是元数据通道，**一个字段写错在界面上看不出任何变化**：

- **缓存**：`Cache-Control`（max-age、no-store、must-revalidate）、`ETag` / `Last-Modified` 配合条件请求 `If-None-Match`，返回 304 复用本地副本。代价在配置侧：缓存键由 URL 加 `Vary` 声明的请求头共同决定——漏配 `Vary: Accept-Encoding` 或 `Vary: Origin`，缓存键就不含这些头，**针对不同编码或来源生成的响应会共用同一份缓存条目，客户端收到不匹配的表示，等于互相覆盖**。缓存改变读写路径与失效模式的完整讨论见 [[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/缓存改变读写路径、一致性与故障模式]]。
- **限流反馈**：429 或 503 带 `Retry-After`，**让调用方知道该等多久，而不是自行猜一个退避值**。
- **追踪**：`traceparent`（W3C Trace Context）与 `request-id`，**把一跳一跳的观测串成一条链路**；请求穿过各层边界时的观测点见 [[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/HTTP请求穿过浏览器、网络与服务端边界]]。
- **逐跳 vs 端到端**：逐跳头部只作用于相邻一跳，代理不应把它们转发下去，如 `Connection`、`Keep-Alive`。端到端头部才会到达最终服务端，如 `Cache-Control`、`Authorization`。把两者搞混，**会出现"本地直连正常、过一层代理就丢头"的现象**。

真实报文里头部层长什么样，Cloudflare 学习站贴了两屏 DevTools 截图——请求头一屏、响应头一屏，正文讲的字段都在里面：

![Cloudflare Learning Center 截图：一次对 www.google.com 的 GET 请求的 Request Headers 面板——伪头部 :authority、:method、:path、:scheme之后是 accept: text/html、accept-encoding: gzip, deflate, br、accept-language、upgrade-insecure-requests、user-agent 等端到端头部逐行列出](/static/figures/http-request-headers.png)

![Cloudflare Learning Center 截图：对应的 Response Headers 面板——cache-control: private, max-age=0、content-encoding: br、content-type: text/html; charset=UTF-8、date、status: 200、strict-transport-security: max-age=86400、x-frame-options: SAMEORIGIN 逐行列出，缓存语义与安全策略都通过头部声明](/static/figures/http-response-headers.png)

来源：Cloudflare Learning Center，[What is HTTP?](https://www.cloudflare.com/learning/ddos/glossary/hypertext-transfer-protocol-http/)。两屏合起来正是**"头部是元数据通道"的实物**：请求屏的 `accept-encoding` 与响应屏的 `content-encoding: br` 是**一次内容协商（客户端声明自己支持的格式、服务端选定并返回的过程）的两端**，响应屏的 `cache-control` 决定中间每一层代理能缓存多久——**头部层配错了，图里这两屏的任何一个字段都是故障现场**。

## 这套分层在什么时候不再成立

- 状态码表达**协议层**结果，不表达业务结果：订单被风控（识别并拦截欺诈与异常行为的风险控制）拒绝是 200 还是 422，取决于它是不是协议意义上的失败，实践中按**"调用方能否用同一套重试逻辑处理"**来划。
- 幂等是**规范里的声明**：**声明了幂等却没有幂等键或条件更新支撑，重复请求照样产生两份副作用**。
- 缓存的正确性依赖头部与方法的配合：对非安全方法做缓存，或忽略 `Vary`，**都属于配置错误而不是调优空间**。

## 怎么自己动手验证

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

判据：非 2xx 里，**4xx 原样重试必然失败；5xx 带退避与上限重试应成功；429 须按 `Retry-After` 等待后再试**；带 `If-None-Match` 的重复请求回 304；**相同幂等键的两次 POST 只产生一份副作用**。这几条中任何一条对不上预期，**都是语义分层被破坏，排查方向在层的归属，客户端实现通常没有问题**。
