---
title: AI 研发迭代框架案例证据
type: case
exclude_from_graph: true-study
status: source-only
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: medium
tags:
  - source/case-study
  - ai/engineering
  - software/testing
  - database/mysql
derived:
  - "[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论]]"
  - "[[工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/AI辅助研发必须形成证据闭环]]"
  - "[[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/测试策略从风险选择证据]]"
---

# AI 研发迭代框架案例证据

本页从整理前的三份工作原稿中保留可复核的案例矩阵和失败事实：代码修复候选、MySQL 用例复现候选，以及一次工具框架迭代的运行记录（相关缺陷编号见下表，均以公开 Bug 库链接呈现）。具体机器路径、端口、模型默认值、重复提示词和未执行待办不构成长期证据，已移除。

> [!warning] 证据边界
> 这是项目时期的证据快照，不代表当前框架、模型或 MySQL 版本仍有相同行为。`已复现` 只说明记录中的环境和输入曾观察到现象；`框架修复成功` 还必须与人工会话修复、只通过编译和假 PASS 分开。需要重新运行时，以公开 Bug 页面重建测试并保存新的 revision、环境和产物。

## 为什么需要事实门禁

### 案例 A：Proposer 绕过 operations 协议

当时 `mutate` 阶段的约定是只输出结构化 operations，由引擎统一应用、验证和回滚。模型却尝试直接通过命令/写文件修改磁盘，约 7.8 分钟后被执行引擎拦截并失败。

这个案例能证明：

- “模型提出变更”和“变更已真实应用”必须是两个事件；
- 若模型既直接改盘又返回 operation，重放可能造成重复修改和冲突；
- 写入事实必须来自框架的 apply 记录，不能从模型文字推断；
- 输出 schema、权限和文件差异需要由框架验证。

它不能证明“所有语义决策都应写成固定 operation 规则”。项目适配和修复方向仍由 AI 决定，框架只控制真实副作用。

### 案例 B：主进程退出，状态仍为 running

另一次运行显示 13 小时以上“卡住”，但实际 Python 主进程已经退出，SQLite 状态没有完成终态投影。主进程内部的心跳、超时和 `finally` 无法在进程被外部终止后继续工作。

长期结论：

- 孤儿检测和租约必须由进程外 observer 或调度器负责；
- 状态带 `owner/generation/lease/last_heartbeat`，超时后通过事件投影进入 `orphaned/failed/unknown`；
- 子进程和外部 CLI 纳入同一进程树，保存退出原因与最后证据；
- “最近仍有 thinking 文本”不能无限续期，应分开观测推理进度、工具进度和墙钟预算。

### 案例 C：后一次失败与旧成功混在一起

同一 Bug 的不同 run 曾出现成功、编译失败和事后推翻的方案。如果只保留一个可覆盖的 `status` 字段，就会把 attempt、revision、测试目标和证据范围混为一谈。

因此每次尝试必须是不可变记录：

```text
bug/task + repository + revision + environment
  -> attempt/generation
  -> plan and hypotheses
  -> commands/logs/artifacts
  -> supported claims
  -> projected result
```

## 代码修复案例矩阵

| MySQL Bug | 整理时证据状态 | 关键观察 | 对评测的价值 |
| --- | --- | --- | --- |
| [#119327](https://bugs.mysql.com/bug.php?id=119327) | 历史框架成功；后续新运行得到缩减 patch | 位置接近基线，但触发条件过宽且漏掉协同状态 | 不能只看 compile/test；还要比较语义条件和影响面 |
| [#119352](https://bugs.mysql.com/bug.php?id=119352) | 不同 run 有早期 PASS，也有长程 compile failure；人工会话有修复 | 结果不稳定，人工产出不能算框架闭环成功 | attempt 必须分开，答案参考与框架能力分开 |
| [#120003](https://bugs.mysql.com/bug.php?id=120003) | 框架未修复；人工会话有修复 | 多轮停留在编译失败 | 同类错误重复出现时应改变假设或升级阻断，而非机械重试 |
| [#118277](https://bugs.mysql.com/bug.php?id=118277) | 历史框架成功 | 正确假设曾被状态机过早排除，后续才挽回 | 假设需要证据增减与可恢复状态，不能一次失败永久删除 |
| [#118394](https://bugs.mysql.com/bug.php?id=118394) | 框架未修复；人工会话有修复 | 同一假设附近反复生成略有差异的无效改点 | 需要结构/符号定位、diff 去重和进展检测 |
| [#118464](https://bugs.mysql.com/bug.php?id=118464) | 早期 PASS 后被推翻 | 所提修复所在函数并未经过该 Bug 的真实路径 | 测试通过不等于因果正确；需要 coverage/trace 或反向变异 |
| [#120015](https://bugs.mysql.com/bug.php?id=120015) | 未修复 | 假设过多且每条探索不足 | 用证据价值调度假设，限制横向发散并保留深挖预算 |
| [#118278](https://bugs.mysql.com/bug.php?id=118278) | 未修复 | 根因方向接近，但精确改点长期振荡 | 将“根因理解”和“patch 正确”作为两个评测维度 |
| [#119973](https://bugs.mysql.com/bug.php?id=119973) | 用例侧成功，修复侧失败 | 有源码支持的方向被过早排除 | 复现成功与修复成功分开投影；强证据假设不因一次 patch 失败消失 |

### 不能混用的成功定义

```text
定位到相关文件/函数
  != 形成受支持的根因
  != 生成可应用 patch
  != 编译成功
  != 目标测试执行并通过
  != 原 Bug 已被因果性修复
  != 相邻行为没有回归
```

案例矩阵中最重要的反例是 #118464：某方案曾让测试变绿，但后续发现修改点不在真实执行路径上。系统必须保留“成功证据覆盖了什么”，而不是把绿色状态扩大成完整修复。

## 用例复现案例矩阵

### 已在当时环境观察到稳定或明确现象

| MySQL Bug | 触发条件中不可丢失的部分 | 旧流程常见失败 |
| --- | --- | --- |
| [#118277](https://bugs.mysql.com/bug.php?id=118277) | 复杂索引与 IFNULL/常量折叠的对照路径 | 过度简化索引结构，现象消失 |
| [#119565](https://bugs.mysql.com/bug.php?id=119565) | TIME 边界值与临时结果路径对照 | 使用普通时间值，无法暴露元数据差异 |
| [#118393](https://bugs.mysql.com/bug.php?id=118393) | 视图、NATURAL RIGHT JOIN、HAVING/DEFAULT 组合 | 换成普通 INNER JOIN 后 NULL 扩展语义改变 |
| [#120087](https://bugs.mysql.com/bug.php?id=120087) | 分区索引表、完整多表 RIGHT JOIN 与谓词对照 | 只创建部分表或提前结束，误判为产品不复现 |
| [#119780](https://bugs.mysql.com/bug.php?id=119780) | UNION ALL、AND 与三值逻辑 `IS UNKNOWN` | 简化表达式后改变逻辑语义 |
| [#116140](https://bugs.mysql.com/bug.php?id=116140) | 存储过程需要多次 CALL 对比 | 只执行一次，遗漏跨调用状态 |
| [#115629](https://bugs.mysql.com/bug.php?id=115629) | 升级路径与 `CAST ... CHARSET binary` | 删除 charset 条件后不再是同一问题 |
| [#113464](https://bugs.mysql.com/bug.php?id=113464) | BEFORE INSERT trigger 后的 UPDATE；不能提前 FLUSH | 添加 FLUSH 恰好绕过问题，产生错误反证 |
| [#112770](https://bugs.mysql.com/bug.php?id=112770) | INSERT IGNORE 与嵌套 VALUES/ROW 语法 | 改成普通 INSERT 后不再触发解析边界 |
| [#110577](https://bugs.mysql.com/bug.php?id=110577) | generated column 中的 `CAST(... AS YEAR)` | 测试缺少真正触发语句，却被当产品失败 |

这些案例共同说明：复现用例的最小化不是删除最多内容，而是保留所有因果必要条件。AI 负责识别哪些条件可能必要；框架负责记录实际 SQL、版本、输出和断言，支持消融验证。

### 只能算条件性或代理证据

| MySQL Bug | 证据限制 | 重新验证要求 |
| --- | --- | --- |
| [#119066](https://bugs.mysql.com/bug.php?id=119066) | 当时主要观察执行计划/估算异常，未形成稳定性能因果证据 | 固定版本、数据量、缓存与负载，区分计划和实际耗时 |
| [#116393](https://bugs.mysql.com/bug.php?id=116393) | 加密函数性能计时受 CPU/调度影响 | 多轮基线、统计分布、CPU 频率与隔离 |
| [#116303](https://bugs.mysql.com/bug.php?id=116303) | race condition 概率触发 | 并发控制、重复次数、失败率和线程/锁证据 |
| [#112767](https://bugs.mysql.com/bug.php?id=112767) | 大数据性能问题，目标分支可能已 backport 修复 | 先验证版本差异，再固定数据与缓存比较 |
| [#112532](https://bugs.mysql.com/bug.php?id=112532) | 高并发短连接，旧日志还发生截断 | 完整日志、并发曲线、丢样检测和资源隔离 |
| [#102191](https://bugs.mysql.com/bug.php?id=102191) | 需要外部 mysqlbinlog 与 binlog 配置，不是纯 SQL 用例 | 把二进制、配置、产物和解析命令纳入事实记录 |

这里的 `条件性` 不是“不适用”。它表示现有证据不足以把一次结果推广成稳定事实，框架应保留 `partial/unknown/environment-blocked`，AI 再决定怎样补证据。

## 从案例提炼的机制

| 观察 | 机制要求 |
| --- | --- |
| 反复 compile failure | 相同错误/近似 diff 检测，强制生成新证据或结束阻断 |
| 假设方向正确但 patch 失败后被删除 | 假设与实现尝试分层计分；实现失败不等于根因被证伪 |
| 测试步骤被“简化”后现象消失 | 保存原始条件，逐项消融并比较行为 |
| PASS 后发现代码路径未执行 | coverage/trace/定向探针或反向变异 |
| 人工会话修复被记为框架成功 | 记录 actor、入口、完整闭环和产物来源 |
| 进程已死而状态 running | 外部 observer、lease、进程树和不可变事件 |
| 不同 run 互相覆盖 | attempt/generation/revision 绑定，单调事实投影 |

## 重新使用这些案例的规则

1. 从公开 Bug 链接重新读取当时描述和目标版本，不把本页概括当完整测试规格。
2. AI 动态识别构建系统、测试入口和适配方式；不为这些 Bug 写生产框架特例。
3. 每次运行使用独立 worktree/目录，保存命令、退出码、stdout/stderr、测试报告、patch 和 revision。
4. 明确标记 `reproduced / not_reproduced / environment_blocked / unknown`，不要用“测试不适用”吞掉依赖或权限失败。
5. 代码修复至少验证：原问题、相邻边界、目标路径覆盖、反向变异和无关回归。
6. 只有新证据满足当前门禁，才能更新结论；本页的历史状态不可直接覆盖新 run。

## 已提炼到哪里

- AI 与框架职责、事件与投影：[[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论]]。
- 代码理解、假设、修改和验证闭环：[[工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/AI辅助研发必须形成证据闭环]]。
- 结构/符号索引与路径证明：[[工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/代码智能体需要结构索引、任务探索与运行证据]]。
- 测试层次、环境阻断和回归资产：[[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/测试策略从风险选择证据]]。
- 进程退出、孤儿和资源清理：[[工程知识/后端系统：在并发、失败与变化中维持服务/任务与并发/任务生命周期必须覆盖进程、日志、超时与清理]]。
