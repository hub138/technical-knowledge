---
title: Spring 代理与 Bean 生命周期会改变调用边界
type: concept
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: medium
sources:
  - "https://docs.spring.io/spring-framework/reference/core/beans.html"
  - "https://docs.spring.io/spring-framework/reference/data-access/transaction.html"
  - "https://docs.oracle.com/en/java/"
tags:
  - java
  - spring
  - backend
---

# Spring 代理与 Bean 生命周期会改变调用边界

它解决的是对象创建、配置、事务和横切逻辑在大型 Java 服务中重复实现且容易失控的问题。核心机制是容器管理 Bean 生命周期并通过代理织入调用边界；收益是依赖和事务治理集中，代价是隐式调用路径、启动顺序和代理限制增加。验证要覆盖同类内部调用、异步边界、事务提交后的副作用和版本迁移。

## 核心模型

Spring 的价值在于依赖注入、生命周期管理、配置和横切能力；它不替代领域边界、事务设计和可观测性。Bean 生命周期通常经历实例化、依赖注入、Aware/后处理器、初始化、使用和销毁，代理可能改变调用路径和事务边界。

## 事务边界

- 事务应围绕一个完整的持久化不变量，而不是包住网络调用或长计算。
- `@Transactional` 依赖代理调用；同类内部直接调用可能绕过代理，事务不生效。
- 明确传播、隔离、只读、超时和回滚异常；数据库隔离级别仍由数据库实际配置决定。
- 异步、事件和事务提交后的副作用要通过 outbox、消息确认或补偿机制协调。

## 配置和发布

- 配置按环境分层，密钥进入密钥管理系统，不写入仓库和日志。
- 兼容升级遵循“先兼容读写，再迁移数据，最后删除旧路径”；锁定 JDK、Spring、构建插件和驱动版本。
- 健康检查区分存活与就绪；启动、关闭、线程池、连接池和数据库迁移都要有超时。

## 示例与版本的使用原则

旧课程和示例工程不作为当前 API 或生产配置。重写示例时先锁定 JDK、Spring、构建插件和数据库驱动版本，再以当前官方文档验证 Bean 生命周期、代理事务和迁移行为；默认密码、绝对路径、旧注解组合和日志配置不复制到新项目。

## 关联

- [[工程知识/软件构建与质量/软件构建：让变化可以理解、验证与交付]]
- [[工程知识/数据系统/数据系统：在并发与故障中保存事实]]
