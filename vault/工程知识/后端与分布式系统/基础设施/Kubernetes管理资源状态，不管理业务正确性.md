---
title: Kubernetes 管理资源状态，不管理业务正确性
type: concept
status: active
updated: 2026-09-03
review_after: 2027-02-28
change_rate: medium
confidence: high
sources:
  - "https://kubernetes.io/docs/concepts/overview/"
  - "https://kubernetes.io/docs/concepts/workloads/"
  - "https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/"
tags:
  - kubernetes
  - cloud-native
  - operations
---

# Kubernetes 管理资源状态，不管理业务正确性

## 核心拆解

| 维度 | 回答 |
| --- | --- |
| 要解决的问题 | 多个进程和节点需要按期望状态调度、发现、重启和扩缩，但人工维护每个实例会放大部署和故障处理成本。 |
| 本质 | 控制器持续比较声明的期望状态和集群观察状态，并通过 API、调度器、kubelet 和运行时收敛资源。 |
| 做法 | 定义资源请求、探针、拓扑、发布顺序、权限、配置版本、网络策略和业务状态的外部事实源。 |
| 效果与代价 | 降低资源编排和发布操作成本；代价是控制面、网络、调度、可观测性和数据迁移复杂度。 |
| 边界 | Pod 重启、自愈和 readiness 不等于业务正确、数据一致或容量足够；回滚应用也不能自动回滚数据。 |
| 验证 | 分别注入 Pod/节点故障、陈旧 Endpoint、资源耗尽、网络/DNS 故障和部分发布，核对请求、状态、数据与恢复证据。 |

一个 Pod 被重新调度只能说明资源控制器完成了替换，不能说明处理中订单、消息 offset 或数据库迁移已经安全恢复。把 Kubernetes 事件、容器状态和业务事实分开记录，才能避免“Pod Running”被误读为服务恢复。

## Kubernetes 解决什么

Kubernetes 通过声明式对象和控制循环提供调度、服务发现、滚动发布、自愈和资源隔离。它不自动解决数据库一致性、业务幂等、容量规划、权限设计或错误处理。

```mermaid
flowchart LR
    D[声明式期望状态] --> A[API Server]
    A --> S[(etcd)]
    A --> C[Controller]
    C --> K[Scheduler/Kubelet]
    K --> R[容器运行时]
    R --> O[观测与反馈]
    O --> C
```

## 生产边界

- Pod 只是故障域中的进程；请求仍需超时、取消、重试、幂等和背压。
- readiness 决定是否接流量，liveness 只用于重启异常容器；探针不能依赖脆弱的下游全链路。
- requests/limits、HPA、节点容量和拓扑分布共同决定调度；只设 limit 不等于容量规划。
- ConfigMap/Secret 有版本和权限边界；镜像固定 digest，依赖和供应链可追溯。
- 发布要有灰度、指标门禁、数据库兼容迁移和回滚；回滚应用不一定能回滚已执行的数据变更。

## 排障顺序

```text
入口/路由 -> Service/Endpoint -> Pod 状态 -> 容器日志
         -> 资源/调度 -> 网络策略/DNS -> 依赖服务和数据层
```

## 关联

- [[工程知识/后端与分布式系统/后端系统：在并发、失败与变化中维持服务]]
- [[工程知识/软件构建与质量/软件构建：让变化可以理解、验证与交付]]
- [[工程知识/计算机系统与性能/性能工程：从用户等待到资源瓶颈]]
