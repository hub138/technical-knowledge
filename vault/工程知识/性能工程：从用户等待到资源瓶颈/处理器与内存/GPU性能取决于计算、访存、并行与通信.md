---
title: GPU 性能取决于计算、访存、并行与通信
type: concept
status: active
updated: 2026-09-03
review_after: 2027-02-28
change_rate: medium
confidence: medium
sources:
  - "https://docs.nvidia.com/nsight-systems/UserGuide/index.html"
  - "https://docs.nvidia.com/nsight-compute/NsightCompute/index.html"
  - "[[工程知识/性能工程：从用户等待到资源瓶颈/观测与诊断/性能问题定位]]"
tags:
  - performance/gpu
  - systems
---

# GPU 性能取决于计算、访存、并行与通信

GPU 适合大量相似、可并行的计算。性能通常受计算吞吐、显存带宽、访存局部性、并行度、主机与设备传输以及 kernel 调度共同限制。

LLM 的 prefill 与 decode 使用 GPU 的方式不同：前者更像大批量矩阵计算，后者每步工作小却反复读取权重和 KV cache。把两者混成一个“GPU 利用率”会掩盖 TTFT、ITL、吞吐和显存的真实瓶颈。

## 判断瓶颈

| 现象 | 优先检查 |
| --- | --- |
| SM/计算单元利用率低 | 网格规模、occupancy、分支发散、kernel 间空洞 |
| 显存带宽接近上限 | 访问合并、数据布局、缓存、重复读写和精度 |
| 显存不足或频繁分配 | batch、激活、缓存、生命周期和内存池 |
| CPU 等待 GPU | kernel 粒度、同步点、PCIe/NVLink 传输和流水线 |
| 延迟抖动 | 频率/温度、上下文切换、动态形状、后台任务 |

## 验证流程

1. 固定模型、输入形状、batch、精度、驱动和运行时版本，记录吞吐、端到端延迟和显存峰值。
2. 先用应用 trace 判断 CPU、数据加载、传输和 kernel 哪一段等待。
3. 用 Nsight、rocm tools 或框架 profiler 查看 kernel 时间、occupancy、内存吞吐、同步和空洞。
4. 只改一个变量，比较 warm-up 后的多轮分布；不要用单次最快结果代表收益。
5. 复核数值精度、稳定性、错误率和功耗；速度提升不能以错误结果为代价。

## 优化边界

- 先减少不必要的数据搬运和同步，再调整 kernel、融合、批处理或精度。
- 更大的 batch 可能提高吞吐但增加尾延迟和显存压力；以业务 SLO 选点。
- GPU 参数、驱动和 kernel 能力高度依赖设备，所有硬件数字都必须来自目标环境实测。

## AI 推理中的时间线

LLM prefill 通常能形成较大矩阵运算，更容易利用计算单元；decode 每步工作较小，却要反复读取权重和 KV cache，常受显存带宽、kernel launch 与调度限制。多 GPU 后还要区分 all-reduce/all-to-all、PCIe/NVLink 或跨节点网络时间。

一次 Nsight 时间线至少应能区分：CPU tokenization/调度、host-to-device、kernel、collective、同步空洞和流式发送。只有 kernel profile 而没有请求 trace，无法判断优化是否改善 TTFT 或 ITL。

## 最小 GPU 实验

固定模型、输入/输出 token 分布、精度、GPU、驱动和并发，分别测单请求 prefill、持续 decode、静态 batch 和连续 batch；记录 TTFT、ITL、完成吞吐、显存峰值、kernel 空洞、通信时间和质量。只改变 batch、量化或并行度中的一个变量，并保留 warm-up 后多轮分布。

量化、批处理、算子融合、CUDA Graph 和并行策略改变的资源不同；完整关系见 [[工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/批处理、KV缓存、量化与并行如何改变服务容量]]。

## 关联

- [[工程知识/性能工程：从用户等待到资源瓶颈/性能工程：从用户等待到资源瓶颈]]
- [[工程知识/性能工程：从用户等待到资源瓶颈/处理器与内存/CPU性能来自有效执行与数据供给]]
- [[工程知识/AI 系统工程：从模型能力到生产能力/推理服务与平台/推理服务的核心矛盾是延迟、吞吐、显存与质量]]
- [[工程知识/AI 系统工程：从模型能力到生产能力/模型基础与训练/GPU执行模型与显存层级：SIMT与合并访存.md]] —— 瓶颈判断的方法论与 LLM 场景
