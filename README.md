# technical-knowledge

一个以 Markdown/Obsidian 为知识事实源、同时提供动态阅读站、关系图、学习入口和 Agent 评估工作台的工程知识库。

它不是把旧课程、项目日志或热门名词堆在一起。主区按可以反复使用的技术对象组织：AI 系统、后端与分布式系统、数据系统、计算机系统与性能、软件构建与质量。每个主题都尽量把基础概念、机制、边界、验证方式、演进关系和来源放在同一页；会快速变化的内容单独进入动态雷达，并标注核对日期。

## 项目结构

```text
vault/                         可直接用 Obsidian 打开的知识库
  工程知识/                    五个技术领域与主题页
  知识库管理/                  来源、更新、质量和维护规则
  Clippings/                   原始剪藏，按要求完整保留
  .obsidian/                   Obsidian 配置和已安装插件
site/                          依赖最少的动态 Markdown 网站与图谱
apps/agent-evaluation/         自研 Agent 评估项目：设计原型与后续产品入口
packages/agent-foundation/     会话、上下文、记忆、恢复和证据基础包
projects/                      完整上游源码快照与其许可证/测试
  archify/                     架构、流程和关系图生成器
  OpenMAIC/                    互动课堂与 Agent 学习运行时
  DeepTutor/                   检索、记忆和学习工作区
  mattpocock-skills/           工程协作 Agent Skills
```

## 本地使用

直接打开 `vault/` 作为 Obsidian Vault。网站读取这个目录中的当前 Markdown，修改笔记后无需导出：

```bash
./run-site.sh
```

修改导航、分类或站点服务后运行回归测试：

```bash
python3 -m unittest discover -s tests -v
```

首页提供知识检索、关系网络、知识流通、学习循环、AI 系统分层和技术选型象限。图中的节点会回到对应 Markdown 页面。

自研 Agent 评估项目位于 `apps/agent-evaluation/`，独立于 `projects/` 下的第三方开源项目。当前完成的是设计契约、静态原型和 `agent-foundation` 基础包；真实仓库、任务夹具、隔离执行、Trace 和证据投影仍是后续开发范围。只有代码与 README 时只能做结构审查，不能伪装成运行时结论。评估契约已写入 `vault/工程知识/AI系统/质量与运营/Agent评估系统的设计契约.md`。

## 更新原则

稳定原理和快速变化的产品事实分开维护。新模型、SDK、协议、论文或开源项目先登记来源，再判断它改变了哪个主题；版本、弃用、价格、安全和 API 事实必须回到官方来源核对。外部论文支持“值得尝试的机制”，本地固定任务、轨迹和前后对照才支持“当前系统有效”。详见 `vault/知识库管理/维护/知识演化机制.md`、`vault/知识库管理/来源/来源注册表.md` 和 `vault/工程知识/AI系统/生态与选型/AI技术动态.md`。

## 上游项目

`projects/` 保留四个项目的完整 Git 跟踪源码快照，并保留各自许可证、文档和测试。依赖目录、构建产物、虚拟环境、用户数据、日志和密钥不纳入本仓库；按项目原 README 安装依赖即可重建。

项目入口页面：`/projects`。容器部署说明见 `DEPLOYMENT.md` 和 `docker-compose.yml`。

本机长期运行的访问地址优先使用 `http://MacBook-Pro-2.local:8787/`；知识内容公开可读，只有启动会使用默认模型凭据的教学工具才对其他设备要求密码。本机和局域网地址、认证边界及故障处理见 `DEPLOYMENT.md`。

## 许可证与来源

本仓库的知识文字和整合代码按仓库提交记录管理；`projects/` 下的第三方项目继续受各自 LICENSE 和 THIRD_PARTY_NOTICES 约束。不要把本地凭据、内部地址、用户数据或未授权材料写入 Markdown、图谱或提交。
