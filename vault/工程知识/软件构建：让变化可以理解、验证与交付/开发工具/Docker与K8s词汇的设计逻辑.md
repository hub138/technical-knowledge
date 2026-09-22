---
title: Docker与K8s词汇的设计逻辑
type: reference
status: core
status_note: 词源系列核心参考
updated: 2026-09-29
confidence: high
change_rate: medium
review_after: 2028-09-22
tags:
  - vocabulary
  - terms/etymology
  - distributed-systems
sources:
  - "https://docs.docker.com/reference/cli/docker/"
  - "https://kubernetes.io/docs/reference/kubectl/quick-reference/"
  - "https://kubernetes.io/docs/concepts/overview/kubernetes-api/"
  - "https://en.wikipedia.org/wiki/Docker_(software)"
  - "https://kubernetes.io/blog/2019/01/14/apiserver-and-command-line-survival-guide/"
---

# Docker与K8s词汇的设计逻辑

`docker run` 是动词直接用，`kubectl get` 是 REST 动词照搬，`kubectl apply` 是声明式语义的入口——容器生态的命令词汇有两套设计哲学打架又融合。要解决的问题：把 Docker 与 Kubernetes 命令词汇的设计逻辑与词源讲清楚，理解"为什么 kubectl 有 get/create/apply 三个看起来重叠的动词"，从此容器命令行可以推理出来，不用死背。

## 机制：两套哲学与动词表

| 设计哲学 | 代表 | 动词集特征 | 词源背景 |
| --- | --- | --- | --- |
| 命令式（imperative） | docker run/stop/rm | 动词即操作：run 一条命令同时创建+启动 | 进程模型：容器=轻量进程，词汇继承进程动词（stop/kill 与进程信号同源） |
| 声明式（declarative） | kubectl apply/delete | 动词作用于"期望状态"：apply 声明期望，控制器收敛 | API 模型：K8s 是数据库，kubectl 是 API 实现照搬 REST（GET/POST/PUT/PATCH/DELETE） |

kubectl 动词的 REST 词源表：

| kubectl 动词 | REST 词源 | 语义 | 与近义动词的区别 |
| --- | --- | --- | --- |
| get | GET | 列出/查看对象 | get 是读，describe 是读+关联对象展开 |
| create | POST | 新建对象 | create 失败即报错；apply 幂等 |
| apply | PATCH（server-side）/ PUT | 声明期望状态 | apply 重复执行无害（幂等），create 重复执行报错 |
| edit | PATCH | 编辑后提交 | edit 本质是 apply 的交互版 |
| replace | PUT | 整体替换 | 字段没写全会被清掉，apply 不会 |
| delete | DELETE | 删除对象 | delete 删对象，remove 已废弃 |
| describe | GET（多对象） | 查看详情+事件 | get 给表格，describe 给叙事 |
| expose | POST（Service） | 创建 Service | 一步完成"创建+关联" |
| exec | POST（exec subresource） | 进容器执行 | 与 docker exec 同源 |
| logs | GET（log subresource） | 查日志 | subresource 是 K8s API 的子资源设计 |
| rollout | PATCH（按子命令） | 管理发布历史 | rollout undo ≠ delete，是历史指针回拨 |

## 年代与演进：设计哲学的换代点

| 词汇/概念 | 出生年代 | 状态 | 门道 |
| --- | --- | --- | --- |
| docker run/stop/kill | 2013（Docker 0.x） | 遗留 | 进程动词直搬，命令式哲学的原点 |
| docker ps | 2013 | 遗留 | ps 抄 Unix process status，容器=进程的心智模型证据 |
| kubectl get/create/delete | 2014（K8s 1.0 前） | 标准 | REST 动词照搬，API 客户端哲学的落地 |
| kubectl apply | 2015（K8s 1.2，client-side） | 演进 | 声明式入口，last-applied-configuration 注解驱动幂等 |
| kubectl apply --server-side | 2022（K8s 1.22 GA） | 演进 | 服务端 apply，field ownership 让多控制器协作不用互踩字段 |
| kubectl edit | 2015 | 标准 | apply 的交互版，编辑器改完即 PATCH 提交 |
| Pod | 2014 | 标准 | 一荚多豆的隐喻：多容器共享网络/存储命名空间 |
| rollout undo | 2015（1.1） | 演进 | 历史指针回拨，不是删除——发布历史是资源 |
| docker compose | 2014（fig，独立项目） | 演进 | fig 改名 compose，音乐术语：多容器协同如多声部合奏 |

这套词汇设计的收益：动词集有哲学出处（REST/进程模型），学习成本从背每个命令降到学两套模型；代价：两套模型并存意味着同一件事有两三种说法（get/describe、create/apply），新人要在该用哪个上付出选择成本。

核心设计的分水岭：`get/create/apply` 三动词并存不是冗余，是两类心智模型的并存——create 是"我要造一个东西"（命令式），apply 是"我要世界变成这样"（声明式）。理解这条分水岭后，整个 kubectl 动词集可以按 REST 语义推理出来。

设计的闪光点：server-side apply 的 field ownership（字段级所有权）是这套词汇里最精巧的设计——每个字段记住谁写的，两个控制器各管各的字段互不干扰，把"声明式协作"从口号做到了字段级实现。它没有新词汇，但让 apply 这个词从"客户端 diff"升维成"服务端合约"。

## 思想背景与看完能判断什么

两套哲学的融合史：Docker 的进程动词（2013）先落地，K8s 的 REST 照搬（2014）把它收编进 API 模型——但收编的方式是并存而非替换，kubectl 至今保留 run/create（命令式）与 apply（声明式）两套入口。这不是犹豫，是有意的过渡设计：命令式让人快速上手，声明式让人长期可靠，两套词汇服务两个阶段的使用者。自己的系统要不要留两套接口，这里就是参照。

- 手上的活是写部署脚本：用 apply 而非 create，幂等性让重跑无害（CI/CD 里脚本被重试是常态）。
- 手上的活是多团队共享集群：server-side apply 的 field ownership 直接可用——各团队管各的字段，冲突在字段级暴露而不是整对象互踩。
- 手上的活是评审别人的部署方案：看到 kubectl create/replace 在 CI 脚本里，可以指出幂等性缺陷；看到 replace 清字段，可以指出声明式误用。
- 想借鉴设计：get/create/apply 的动词三分（读/造/声明）是 API 设计的通用模式——任何"状态+收敛"的系统（配置管理、IaC、甚至游戏存档）都能套用这个词汇骨架。
- 想避坑：compose 的 fig 出身说明生态词汇会被收购改名单词不变，依赖工具词源做架构决策时要查它的演进史，别被名字骗。

## 验证

```bash
# 验证 apply 幂等 vs create 不幂等
kubectl apply -f deploy.yaml && kubectl apply -f deploy.yaml   # 第二次 configured/no-op
kubectl create -f deploy.yaml && kubectl create -f deploy.yaml # 第二次 AlreadyExists 报错
# 验证 get 与 describe 的信息层次差
kubectl get pods -A | head -5
kubectl describe pod <name> | head -20
# 验证 docker ps 的词源亲属
docker ps --format '{{.ID}} {{.Status}}' ; ps aux | head -3
```
预期：apply 两次执行第二次无副作用（幂等证据）；create 第二次报 AlreadyExists（非幂等证据）；describe 比 get 多出 Events 段（subresource 聚合证据）。数字对不上（apply 第二次也改了东西）时查是否用了 replace 语义的注解冲突（last-applied-configuration 注解是 apply 幂等性的实现载体）。

## 边界

本篇讲容器生态命令词汇。方法论总纲见 [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/词汇即接口：Linux与容器命令的词源与设计.md|词汇即接口：Linux与容器命令的词源与设计]]。Linux 侧命令词源见 [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/Linux常用命令的词源地图.md|Linux常用命令的词源地图]]。声明式模型的深机制（控制器收敛循环）见 [[工程知识/后端系统：在并发、失败与变化中维持服务/基础设施/容器隔离资源边界与镜像身份.md|容器隔离资源边界与镜像身份]]。资源模型（K8s 把集群当数据库）的设计深度见 [[工程知识/后端系统：在并发、失败与变化中维持服务/服务设计/服务发现与负载均衡决定请求落到哪里.md|服务发现与负载均衡决定请求落到哪里]] 的 Service 部分。

## 相关

- [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/词汇即接口：Linux与容器命令的词源与设计.md|词汇即接口：Linux与容器命令的词源与设计]]——方法论总纲
- [[工程知识/软件构建：让变化可以理解、验证与交付/开发工具/Linux常用命令的词源地图.md|Linux常用命令的词源地图]]——Linux 侧对照
