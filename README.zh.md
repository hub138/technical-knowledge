# technical-knowledge

**记机制，不记结论 —— 以及服务这套知识库的站点。**

[![tests](https://img.shields.io/badge/tests-50%2F50-brightgreen)](#验证)
[![a11y](https://img.shields.io/badge/contrast-18%2F18%20WCAG%20AA-brightgreen)](#验证)
[![dependencies](https://img.shields.io/badge/runtime%20deps-none-blue)](#设计取舍)
[![python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-see%20below-lightgrey)](#许可证)

<sup>[English](README.md) · 中文</sup>

184 篇工程笔记，覆盖 AI 系统、后端与分布式系统、数据系统、计算机系统与性能、
软件构建与质量。每页按同一套结构写，读完能说清一个技术**是拿来干什么的**，
而不只是它叫什么。

每一页回答四个问题：

| | |
|---|---|
| **背景** | 它为什么出现？之前卡在哪？ |
| **方案** | 它怎么解决的？机制是什么？ |
| **效果** | 实际改变了哪个指标，在什么条件下测的？ |
| **优缺点** | 代价是什么？什么情况下不该用？ |

性能结论不带数据规模、版本和硬件条件就不算事实。网上看来的只当线索：
要写进正文，先回官方文档、论文，或者自己跑一遍。

---

## 目录结构

```
vault/                         可直接用 Obsidian 打开
  工程知识/                     五个技术领域，一个工程问题一页
  知识库管理/                   来源、更新、质量和维护规则
  Clippings/                   原始剪藏，按要求完整保留
site/                          站点：单文件 HTTP 服务，无运行时依赖
apps/agent-evaluation/         自研 Agent 评估：设计契约与原型
packages/agent-foundation/     会话、上下文、记忆、恢复与证据基础包
projects/                      完整上游源码快照，含各自许可证
  archify/                     架构、流程与关系图
  OpenMAIC/                    互动课堂运行时
  DeepTutor/                   检索、记忆与学习工作区
  mattpocock-skills/           工程协作 Agent Skills
```

## 快速开始

```bash
./run-site.sh                  # 起在 http://localhost:8787
```

用 Obsidian 打开 `vault/` 即可编辑。站点直接读 Markdown 文件，存盘刷新就行，
没有构建步骤，也不需要导出。

## 站点

| | |
|---|---|
| **阅读** | 搜索、按领域索引、文章页含入链与来源列表 |
| **图谱** | 笔记之间的关联，另有系统分层与选型象限图 |
| **学习** | 通往课堂与导师工具的引导路径，主题会预填 |
| **评估** | 自研 Agent 评估项目，与上游第三方工具分开维护 |
| **访问与反馈** | 只在本机可见的运营视图：谁读了什么、说了什么 |

界面提供**英文（默认）与中文**，在侧边栏切换。知识笔记保持写作时的语言 ——
机翻一篇机制解释会读起来通顺但是错的，所以没有英文版的笔记会如实说明，
而不是假装有。

## 设计取舍

三个决定影响了其余一切。

**没有构建步骤，没有运行时依赖。** `site/server.py` 是单文件 Python 标准库
HTTP 服务；`site/base.css` 是一份由 93 个设计 token 驱动的样式表；唯一第三方
资产是 vendored 的 Mermaid。没有 npm install、没有打包器，也没有需要同步的东西。

**同一件事只有一个来源。** 导航在 `site/nav.js` 定义一次，由 `site/shell.js`
渲染一次，所有页面共用。这是有意为之：站点曾经有两套页面系统，各自维护一份
导航、各自渲染侧边栏，然后漂移了 —— 同一个入口一边有一边没有，点过去布局还会变。
合并之后删掉了 63 条只为迁就另一套而存在的覆写规则。

**要证据，不要断言。** 笔记里的结论带测试条件；关于站点本身的结论带脚本：

| 检查什么 | 怎么查 |
|---|---|
| 行为 | `python3 -m unittest tests/test_site.py` —— 50 个测试 |
| 布局 | `python3 scripts/layout_audit.py` —— 27 个页面×宽度组合 |
| 可读性 | `python3 scripts/contrast_audit.py` —— 逐页逐主题 WCAG AA |
| 文案质量 | `python3 scripts/copy_audit.py` —— 可数规则 |
| 翻译覆盖 | `python3 scripts/i18n_audit.py` —— 未翻译的界面字符串 |

## 验证

```bash
python3 -m unittest tests/test_site.py        # 50/50
python3 scripts/contrast_audit.py <url>#dark  # 18/18 页面×主题组合
python3 scripts/layout_audit.py              # 27/27 页面×宽度组合
python3 scripts/copy_audit.py                 # 得分 2（越低越好）
python3 scripts/i18n_audit.py                 # 未翻译的界面字符串
```

凡是视觉上的改动，验收面就是渲染出来的页面：用桌面与移动宽度的整页截图确认，
而不是读 diff。

## 怎么更新知识

稳定原理和快速变化的产品事实分开存。新模型、新协议、新论文先登记为来源，
再判断它影响哪几页。版本号、弃用时间、价格、安全口径这类会变的事实，
一定回官方文档核对，不看二手总结。

论文能说明「这个机制值得试」；只有在本地跑过、有前后对比，才能说明「它在我这儿有效」。

同一个工程问题只留一页。发现重复的，先把案例、机制、代价和验证合并进保留的那页，
再删掉旧入口 —— 不要两份各写一半。

见 `vault/知识库管理/方法/一篇知识怎么写.md` 与 `CONTEXT.md`。

## 部署

容器部署见 `DEPLOYMENT.md` 与 `docker-compose.yml`。

局域网访问优先用 `http://<host>.local:8787/`。知识内容公开可读，只有启动会签发
模型会话的工具才需要站点密码。完整的信任边界 —— 哪些路由开放、哪些要密码、
为什么 —— 写在 `DEPLOYMENT.md`，由 `site/server.py` 强制执行。

## 上游项目

`projects/` 保留四个上游项目的完整 Git 跟踪源码快照，各自附带许可证、文档和测试。
依赖目录、构建产物、虚拟环境、用户数据、日志和密钥不纳入本仓库；
按各项目自己的 README 安装即可重建。

## 参与

增删知识前先读 `AGENTS.md` —— 它定义了动手前必须先过的检查（写新页之前，
先搜有没有同一问题的既有页）。提改动前跑一遍上面的验证命令。

## 许可证

本仓库的知识文字和整合代码按提交记录管理；`projects/` 下的第三方项目
继续受各自 LICENSE 和 THIRD_PARTY_NOTICES 约束。

不要把凭据、内部地址、用户数据或未获授权转发的材料写进知识库、图谱或提交。
