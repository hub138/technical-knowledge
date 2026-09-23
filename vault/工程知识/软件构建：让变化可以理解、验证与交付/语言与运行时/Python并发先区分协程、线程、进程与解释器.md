---
title: Python 并发先区分协程、线程、进程与解释器
type: concept
status: active
updated: 2026-09-03
review_after: 2026-10-03
change_rate: high
confidence: high
sources:
  - "https://docs.python.org/3/howto/free-threading-python.html"
  - "https://docs.python.org/3/library/asyncio-task.html"
  - "https://docs.python.org/3/library/concurrent.futures.html"
  - "https://docs.python.org/3/library/threading.html"
  - "https://peps.python.org/pep-0703/"
tags:
  - python/runtime
  - python/concurrency
---

# Python 并发先区分协程、线程、进程与解释器

先回答三个不同问题，再选并发模型：任务是等待 I/O 还是消耗 CPU？需要共享内存还是隔离故障？取消、超时和副作用能否被可靠回收？“协程一定更快”“线程不能并行”都不是跨版本、跨扩展和跨负载成立的结论。

## GIL 的真实边界

传统 CPython 构建中，GIL 让同一解释器同一时刻只有一个线程执行 Python 字节码；线程在阻塞 I/O 或某些释放 GIL 的原生扩展中仍可并发。它保护的是解释器实现，不是业务数据结构：即使有 GIL，复合操作、外部资源和共享状态仍需锁或其他同步协议。

从 Python 3.13 开始，CPython 提供可禁用 GIL 的 free-threaded 构建；它不是默认发行模式，第三方 C 扩展可能不兼容并重新启用 GIL，而且单线程有额外开销。必须在目标 Python 构建、依赖 wheel 和真实负载上做基准，不能把“升级到 3.13+”当作自动获得多核加速。[Python free-threading 文档](https://docs.python.org/3/howto/free-threading-python.html)

## 四种执行单位

| 单位 | 内存/故障边界 | 是否抢占 | 适合 | 主要代价 |
| --- | --- | --- | --- | --- |
| 协程/Task | 同一事件循环、共享进程 | 在 `await` 处协作让出 | 大量 I/O、连接和 Agent 工具调用 | 一个阻塞调用会卡住整个 loop；取消需传播 |
| 线程 | 同一进程、共享内存 | 操作系统调度 | 阻塞库、少量后台 I/O、与同步 API 集成 | 共享状态竞态；GIL 构建下 CPU 字节码不并行 |
| 子进程 | 独立解释器和地址空间 | 操作系统调度 | CPU 隔离、崩溃隔离、不同运行时 | 启动、内存、序列化和 IPC 成本 |
| 子解释器 | 同一进程不同解释器状态 | 线程 + 独立解释器 | 需要多核且可显式隔离数据的纯 Python 工作 | 扩展兼容性和跨解释器通信复杂；Python 3.14 `InterpreterPoolExecutor` 才加入标准库 |

协程不是线程，也不是“后台任务”：调用 `async def` 只创建 coroutine object，必须 `await` 或包装为 Task 才会运行。Task 由事件循环调度，单个协程在 `await` 前执行的 CPU 代码仍会阻塞其他任务。[asyncio tasks 文档](https://docs.python.org/3/library/asyncio-task.html)

## 结构化并发：让生命周期可证明

优先使用 `asyncio.TaskGroup` 管理相关子任务：离开上下文时等待全部任务；一个任务失败会取消同组其余任务并聚合异常，避免 `create_task()` 后无人持有引用或吞掉异常。对边界调用使用 `asyncio.timeout()`，在 `finally` 中关闭连接、释放锁和取消子任务。捕获 `CancelledError` 做清理后通常应继续抛出，否则会破坏 TaskGroup/timeout 的取消语义。

```python
import asyncio

async def fetch_all(client, ids):
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(client.fetch(item_id)) for item_id in ids]
    return [task.result() for task in tasks]

async def bounded_call(client, item_id):
    async with asyncio.timeout(5):
        return await client.fetch(item_id)
```

`asyncio.gather()` 仍有用途，但默认一个任务失败时不会取消其他任务；需要强生命周期保证时选择 TaskGroup，并为每个子任务设并发上限、总截止时间和结果大小上限。

## 执行器的选择

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# 阻塞同步库：在线程池中运行，但不要把无限任务塞进无界队列
with ThreadPoolExecutor(max_workers=16) as pool:
    result = pool.submit(blocking_call, arg).result(timeout=5)

# CPU 密集：进程隔离，参数和返回值必须可序列化
with ProcessPoolExecutor() as pool:
    result = pool.submit(cpu_bound_call, data).result(timeout=30)
```

`InterpreterPoolExecutor`（Python 3.14）为每个 worker 提供独立解释器和 GIL，可实现多核并行；代价是可变对象不能直接共享，模块/运行时状态需要在各解释器中初始化，通信通常要序列化。[concurrent.futures 文档](https://docs.python.org/3/library/concurrent.futures.html)

选择顺序应是：先用同步函数证明正确性 → 明确阻塞点和资源上限 → I/O 用协程或线程池 → CPU 用原生扩展、进程或子解释器 → 用 profile 和基准确认收益。不要为了“异步”把所有代码改成 `async`，也不要在事件循环里直接调用阻塞数据库、文件或 subprocess API。

## 取消、超时与共享状态

- 取消是控制流，不是普通异常日志：在 `finally` 中释放连接、锁、临时文件和子进程；对不可取消的外部系统用幂等键和状态查询补偿。
- 连接超时、读取超时、总截止时间分开设置，并把剩余预算传递给下游；多层重试只按一个总预算计算。
- 线程共享可变状态用 `Lock`、`Queue`、`Event` 或不可变消息；不要依赖 dict/list 的“原子性”推断业务安全。free-threaded 构建也不改变业务同步约定。[threading 文档](https://docs.python.org/3/library/threading.html)
- 进程/子解释器之间只传递明确 schema 的消息；大对象优先共享文件/内存映射或批量传输，避免每个任务重复 pickle。
- 队列、线程池、连接池和并发工具调用都要有上限、背压、拒绝/降级策略和积压指标。

## 服务与 Agent 场景

一次 Agent 请求通常包含：并行检索、模型调用、工具执行和写入事实源。检索可以在 TaskGroup 中并发，写入工具必须按幂等键串行或由事实源协调；模型流式输出不能代替任务状态。把请求取消、客户端断开、模型超时和工具超时统一映射为可观察的状态机，并记录 trace/span、任务 ID、版本和副作用结果。

## 评测与排障

至少同时测：吞吐、p50/p95/p99 延迟、CPU 利用率、内存峰值、上下文切换、队列等待、取消完成时间和失败重试次数。对同一 workload 比较同步、协程、线程池、进程/子解释器，并记录 Python 版本、GIL 构建、依赖版本和硬件。常见症状与方向：

| 症状 | 优先检查 |
| --- | --- |
| 协程并发却整体变慢 | loop 中的阻塞调用、无界并发、DNS/连接池和大响应 |
| CPU 线程没有加速 | GIL 构建、C 扩展是否释放 GIL、锁竞争和数据拷贝 |
| 取消后进程仍占用资源 | 子任务引用、`finally` 清理、线程池无法强制终止 |
| 内存随流量上涨 | 无界队列、未回收 Task、缓存/响应体和进程池 worker |
| free-threaded 反而退化 | 单线程开销、扩展回启 GIL、锁/分配器竞争和缺少专用 wheel |

## 关联知识

- [[工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/跨语言并发模型必须同时比较抽象与运行机制]]
- [[工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/Go并发以所有权、取消与错误传播为边界]]
- [[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理]]
- [[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能问题定位]]
- [[工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/构建可靠Agent应用]]

相关（运行时对照）：[[工程知识/软件构建：让变化可以理解、验证与交付/语言与运行时/TypeScript类型边界与Node事件循环共同约束服务]] —— 协程在不同事件循环下的差异

## 验证

1. 阻塞探测：在事件循环上混入一次同步阻塞调用，比较前后的请求延迟分位数，预期延迟抬升的区间与阻塞调用持续的时间对齐。
2. 加速比测量：把同一 CPU 密集任务分别交给线程池与子进程执行，记录多核使用率与总耗时，预期线程方案在多核上没有加速，原因可回到 GIL 的释放情况。
3. 取消核验：取消一个持有连接与临时文件的任务，用 `ls -1 /proc/<pid>/fd | wc -l` 与连接数核对资源是否回收；未回收时检查子任务引用与 `finally` 清理路径。
4. 内存跟踪：在稳定流量下跟踪常驻内存与排队任务数，预期两者不随流量单调上涨；上涨时按无界队列、未回收 Task 与缓存逐类排查。
5. 构建对照：在同一压测下比较普通构建与 free-threaded 构建的吞吐与单线程开销，预期退化可归因到具体的锁竞争或扩展回启 GIL。
6. 断言锚点：阻塞调用被识别并移出事件循环，并发上限与背压已设置，取消路径回收资源，内存曲线在稳定流量下持平。

## 要解决的问题

把代码改成协程之后整体反而变慢，原因是事件循环里混入了阻塞调用；用线程池处理 CPU 密集任务，多核并没有带来加速；任务被取消之后进程仍占着连接与临时文件；内存随流量持续上涨，排队中的任务无人持有。本篇回答：协程、线程、子进程与子解释器各自的内存与故障边界在哪里、GIL 限制的到底是什么、结构化并发怎样让生命周期可证明、取消与超时如何在多层之间传递预算、以及并发上限与背压应当设在什么位置。

