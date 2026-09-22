---
title: HTTP 请求穿过浏览器、网络与服务端边界
type: concept
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: high
tags:
  - web/http
  - web/browser
  - security/web
sources:
  - "https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS"
  - "https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy"
  - "https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API"
  - "https://owasp.org/www-community/attacks/xss/"
---

# HTTP 请求穿过浏览器、网络与服务端边界

Web 系统的关键不是某个前端框架或 Flask 语法，而是浏览器安全模型、HTTP 契约、状态归属和数据在各层的编码边界。

同一个 `/api/report` 请求，可能先被浏览器的同源策略拦截，再被网关的超时截断，最后在服务端已经提交后丢失响应；排障必须沿浏览器、网络、入口、服务和事实源逐层确认，不能只看浏览器控制台的“failed”。

这条边界链决定了请求究竟有没有到达、数据是否已提交，以及客户端能否安全重试；任何一层的状态都不能替代端到端证据。

浏览器看到的错误只是最后一个观测点，不能说明请求没有在服务端产生副作用；必须把每一跳的状态、超时和 request ID 串起来。

## 请求链路

```text
用户事件 -> 浏览器 DOM/状态 -> fetch/form/navigation
        -> DNS/TCP/TLS/HTTP -> 网关/路由 -> 鉴权/业务/数据库
        -> HTTP 状态/headers/body -> 浏览器解析 -> DOM 更新
```

SSR 在服务端生成初始 HTML，CSR 由浏览器 JavaScript 获取数据并更新页面；两者可混合。AJAX/fetch 是异步 HTTP 调用方式，不是渲染架构。选择依据是首屏、SEO、交互复杂度、缓存、团队和运行成本。

## HTTP 契约

- 方法表达语义：安全读取与有副作用写入分开；重试写操作需要幂等键或条件更新。
- 状态码区分客户端错误、权限、冲突、限流和服务端故障；不要全部返回 200 再在字符串里写失败。
- 请求/响应使用版本化 schema，验证类型、长度、枚举和未知字段；错误返回稳定 `code + message + details + request_id`。
- 超时分连接、读取、单次下游和总 deadline；调用链剩余预算逐层传递。
- 分页使用稳定排序与 cursor；大结果支持流式/异步任务和取消。

## 同源策略与 CORS

同源由 scheme、host、port 共同决定。浏览器限制脚本读取跨源响应；CORS 是服务端通过响应头授予特定 origin 的读取权限，不是认证机制，也不限制非浏览器客户端。

当请求方法/headers/content-type 不属于 CORS safelisted 范围时，浏览器先发送 `OPTIONS` preflight，确认允许的方法、headers 和 credentials。正确做法：

- 允许明确 origin，不把带凭据请求与 `*` 混用；
- `Access-Control-Allow-Credentials` 只在确有 cookie/认证需要时启用；
- 预检缓存用 `Access-Control-Max-Age`，但同时考虑策略变更；
- 服务端仍做认证、授权、CSRF 和输入校验；preflight 通过不代表业务请求被授权。

详见 [MDN CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) 与 [same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy)。

## 模板、DOM 与 XSS

- 模板默认转义用户内容；只有经过可信 sanitizer 且语境正确的 HTML 才能标记 safe。
- HTML、属性、URL、CSS 和 JavaScript 字符串是不同编码上下文，不能用同一种转义替代。
- DOM 更新优先 `textContent` 和安全组件 API，避免把不可信字符串交给 `innerHTML`。
- CSP 是纵深防御，不替代输出编码和依赖安全。
- 服务端校验是最终边界；前端校验只改善体验。

## 任务状态与健康检查

长任务返回 task ID，由 [[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/健康检查只能提供有时效的失败证据]] 的轮询/Webhook/流式机制获取结果。状态接口与 liveness/readiness 分离：任务状态是业务事实，健康检查决定实例是否接流量，心跳只反映最近通信。

## 验证清单

- [ ] API schema、错误码、权限、幂等、超时和取消已定义。
- [ ] 浏览器 CORS、cookie SameSite、CSRF 和服务端授权分别测试。
- [ ] 用户数据在 HTML/属性/URL/JS 等正确上下文编码。
- [ ] SSR/CSR 边界不重复请求、泄漏秘密或造成 hydration 不一致。
- [ ] trace/request ID 串起浏览器、网关、服务端和下游。

关联：[[工程知识/性能工程：从用户等待到资源瓶颈/存储与网络/端到端网络延迟来自排队、协议、传输与处理]]、[[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/流量入口只负责路由与连接，不负责业务正确性]]、[[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/测试策略从风险选择证据]]。
