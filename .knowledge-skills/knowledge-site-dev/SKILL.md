---
name: knowledge-site-dev
description: 开发 technical-knowledge 知识站（工程知识库网站）。涉及该站点 UI/后端/部署/数据/内容展示改动时使用。
---

# 知识站开发

循环：**意图 → 决策 → 18788 本地实现 → 双态截图 → 站长确认 → push → 三端核对**。

## 决策规则

- 意图不明：写出你的理解 + 选定方案直接做，用截图对齐。不抛选择题，不反复问。
- 展示内容由站长策展驱动（`type: radar` / `pinned: true`）。阅读数据只进中台，不驱动展示。
- 推广即背书：推任何内容前，确认站长认可该内容。
- 位置与推荐视觉分离：实底框=当前位置，暖橙项=推荐。互不冒充。
- 领域顺序改两处：`/api/domains` 钉选 + `PINNED_FIRST`，同步后四面截图（树/卡/地形/图谱）。
- 两侧都能写（Mac/dev）：**commit 必做**（脏工作区挡住 pull 会让部署卡住）；**push 看目的**——要让另一端看到才 push，只在本机保住工作则不必。
- 「已完成」必须附验证证据：grep 计数 / curl 状态码 / 截图。

## 两类变更（勿混）——最关键的结构

| 类别 | 例子 | 存哪 | 生效方式 |
|---|---|---|---|
| **代码/页面** | UI、排序、功能、样式 | git | Mac/dev 改 → push → dev 5 分钟自动拉取 |
| **运营数据** | 钉选头条、反馈、收藏、访问 | dev `data/*.json`（不入库） | **点完立即生效，全端同步，无需 push/重启** |

混淆两类 = 用户在旧版入口前困惑、以为"没上线"。

## 受众规则（页面为读者而做）

- 页面只放受众要的东西：知识、好文章、论文。**统计口径、方法论、分类依据、调研过程、内部思考一律不上页面**。
- 文案为抓眼球设计：访客不带问题来；禁用幼稚表达与过程性叙述，写完当读者读一遍。
- 站长让你调研的产品/网站是**设计参考**，不是页面内容。

## 时效规则

- 论文：只收新的（2024 前标记待做不解析）；旧库不作主模块。
- 优质好文：只展示近两个月；早报是本周的。
- 旧内容宁可藏起标记待做，不凑数展示。

## 展示规则

- 删掉任何元素/文案后必须重新设计布局补位，不留空洞、不留孤立空行。
- 布局自检：右边空了要利用（悬浮/入口/目录）；对齐、字号、字重逐项截图核对；按钮大小要可发现。
- 外部优质源可整站嵌入展示或给入口；抓不到的内容直接不显示。

## 文章排版：开发前与交付前

- 开发前选真实文章覆盖普通文字、列表、引用、行内代码、代码块、两列表格、多列表格和长英文。文章阅读是本站的主要用途，必须在文章页面检查这些元素。
- 同一阅读层级使用同一字号：正文、列表、引用与表格继承阅读字号；辅助信息才用 `--text-small`。核对 token 的最终数值，逐个读取 `p/li/blockquote/th/td/code` 的 computed style。
- 表格保留原生 `table/thead/tbody` 布局，由 `.table-wrap` 横向滚动；禁止表头与表体分别设置 `display:table`。长内容换行，多列表格保留可读列宽。
- 修改样式前检查基础规则、媒体查询和后续覆盖；文章主标题选择器限定头部，正文样式集中维护，删除重复声明。
- 必跑 `scripts/note_verify_shots.py --base <验证地址>`：默认四种宽度、双主题、真实代表文章，输出字号、对比度、列边界、滚动检查和截图。指定文章用重复的 `--path`；截图必须查看全页和表格局部。
- 验收报告必须说明实际检查的文章、宽度、主题和元素类型。首页检查、服务测试、截图数量都不能单独证明文章阅读质量。

## 工作方式

- **脚本化巡检**（2026-09-24 自 Harness 工程实践吸收）：同一验证动作写第二次时就沉淀成 `scripts/` 下的确定性脚本（现成参考：check_all.py 统一门禁、audit_shots.py 全站截图、audit_regression.py 回归三件套），重复操作交给脚本，判断与决策留给 AI；新脚本入口支持 `--base` 参数复用端口约定。
- **自主巡检**：每个改动后自己全站截图找问题，不等用户报；发现一个同类问题 → 全站扫一遍。
- **现成验证脚本**（改完重启后直接跑，别每次重写）：
  - `scripts/verify_reading_page.py` —— `/panorama/reading` 两分区功能回归（勾选同步、隐藏已读、换域、响应式、暗色、控制台报错）。
  - `scripts/verify_subnav.py` —— 侧栏折叠与高亮（整行折叠、总览入口、锚点归属、页头跳转）。
- **持续模式**：长任务一口气做完，不暂停不问「要不要继续」；用户离开也持续工作。
- **长会话管理**：JS heap OOM（4GB/8GB）在超长会话反复出现——压缩上下文或重启会话，重活拆会话。
- **性能预算**：外部 API 有配额（BestBlogs 每日 500 次）；抓取固定化 + 定时更新，去掉无意义刷新按钮。

## 高亮语义（不可混淆）

- **实底框**（aria-current）= 当前位置。语义神圣，不挪用、不复刻。
- **暖橙项**（pinned，`--color-warm-*`）= 站长推荐。常驻亮着，不用实底框样式。
- 引导元素：颜色与位置一起设计，音量降到所在容器级别。数据不影响展示。

## 环境

| 用途 | 值 |
|---|---|
| 仓库（Mac） | `~/Developer/technical-knowledge` |
| 线上（唯一） | dev 内网机，nginx 28788 → `127.10.0.1:28787`，systemd `knowledge-site`，5 分钟自动拉取 main |
| Mac 入口 | `localhost:18787`（SSH 隧道 → dev） |
| 本地测试 | 临时文件使用仓库内已忽略的 `.agent/tmp/`；`TMPDIR` 与 `KNOWLEDGE_DATA_HOME` 指向该目录的独立子目录，密码由环境变量提供。服务仅监听 `127.0.0.1`；并行验证选择未占用端口并通过 `--base` 显式传入 |
| **静态资源 URL** | **`/static/`（不是 `/site/`）**——仓库目录是 `site/`，URL 是 `/static/` |
| 密码 | dev `/etc/knowledge-site.env`（600）；运营者会话豁免监控 |
| 测试 | `pytest tests/test_site.py`（54 例）；改 nav/路由前后必跑 |

## 改完代码必须重启（看不到变化的头号原因）

三个实例跑的是**同一份代码**，但互不共享内存。改完不重启 = 浏览器看旧行为，
截图、curl、playwright 全都证伪不了问题。

| 实例 | 怎么起 | 重启命令 |
|---|---|---|
| 28787（systemd，nginx 28788 的后端） | `python3 site/server.py --root vault --host 127.10.0.1 --port 28787` | `systemctl restart knowledge-site.service` |
| 18788（手动，本地验证用） | 同上，`--host 0.0.0.0 --port 18788` | `bash /data/code/AIagent/scripts/restart_knowledge_sites.sh` |
| 8787（手动，本机接口） | 同上，`--host 127.0.0.1 --port 8787` | 同上脚本一并重启 |

- 脚本自己 `source /etc/knowledge-site.env`，**不用手动带密码**。手动起必须带
  `KNOWLEDGE_SITE_PASSWORD`，否则 `RuntimeError: KNOWLEDGE_SITE_PASSWORD is not set`
  （macOS Keychain 分支只在 Darwin 生效，Linux 上必然报这个）。
- **禁止 `ps aux | grep server.py | xargs kill`**：会误杀同机的其他项目服务
  （`mr_six/.../agent-architecture-review/server.py` 就被这么杀过一次）。
- 公网入口 `http://<host>:28788` 是 nginx，`proxy_pass → 127.10.0.1:28787`，
  28788 返 502 就是 28787 没起来。
- 路径别写错：静态资源 URL 是 `/static/shell.js`，`/site/shell.js` 会返回 404 HTML。

## 红线

- 本地测试必用 KNOWLEDGE_DATA_HOME 隔离，不写真实 data/
- 运营者会话的访问与反馈不入监控
- 端口不混：18787 隧道 ／ 18788 本地测试 ／ 28788 内网站
- 断言失败即修源头，不改断言迁就
- 仓库是**公开的**：任何内容进仓库 = 面向全世界

## 渐进式披露

- 看不到变化 / 排查决策树 → [workflow.md](references/workflow.md)
- 拓扑 / 端口 / 数据流 / 监控豁免 → [architecture.md](references/architecture.md)
- 高亮 / 排序 / 策展 / 文案 / 布局 / 站长视觉偏好 → [design-language.md](references/design-language.md)
- **发布红线（测试门禁 / check_all 统一巡检 / 内容红线 / 降级 / i18n / 回滚）→ [constraints.md](references/constraints.md)**
- **多写者协作（Mac↔dev / dev 直改 / 变基 / 发布核对）→ [collaboration.md](references/collaboration.md)**
- 症状排查 → [pitfalls.md](references/pitfalls.md)
