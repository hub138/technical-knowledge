# 发布红线（必须/禁止）

## 测试门禁

- **必跑**：`pytest tests/test_site.py`，必须全绿才允许发布。
- **文章排版必查**：修改阅读样式、Markdown 渲染或文章结构后，执行 `scripts/note_verify_shots.py --base <验证地址>`；`check_all.py` 完整模式包含 `article-typography`，`--fast` 跳过浏览器验证，报告必须明确这一范围。断言涵盖真实文章身份、元素数量、文字大小、对比度、表格列边界与滚动，查看全页及局部截图后才能交付。
5:- **统一巡检入口**：仓库 `scripts/check_all.py` 一条命令跑全部检查（tests、tokens、links、copy、readme、i18n、papers、contrast、layout、skill-drift），输出一张 verdict 表（2026-09-24 自 Harness 工程实践吸收）。发布前按改动面加跑对应子集：改样式/颜色 → contrast 与 tokens，改文案 → copy 与 i18n，改链接/删内容 → links；改了 nav/路由则全跑。skill-drift 管 skill 文档与代码的同步：改了路由、文件名、frontmatter 字段、词表锚点，或改了 skill 文档，跑它确认文档指针没有悬空（含内嵌 `.knowledge-skills/` 与聚合层主副本的同步）。
6:- **提交钩子兜底**（2026-09-24）：`.githooks/pre-commit` 已随仓库配置（`core.hooksPath .githooks`），按 staged 改动面裁剪检查——skill-drift 永跑，改 vault 才跑 links、改样式才跑 tokens、改文案才跑 i18n、改论文注册表才跑 papers，全绿才放行提交。钩子挡日常，`check_all` 全量在发布流程兜底；`--no-verify` 是逃生门，用了就要在发布前补跑全量。
7:- **skill 副本晋升**（2026-09-24）：`scripts/sync_skill_copies.py`（`diff | promote | pull | sync`）对账内嵌 `.knowledge-skills/` 与聚合层主副本——promote 把站点侧改动发布到平台侧，pull 反向，sync 按 mtime 双向收敛。改完 skill 文档后先 diff 看差异面，再选方向晋升；晋升后 skill-drift 的副本同步面自动归零。
8:- **tag 词表收编**（2026-09-24）：`scripts/collect_orphan_tags.py` 把游离 tag（不在 matrix.js 词表里的写法）按显式映射表归并到正式词条，`--dry` 预览 `--write` 落笔，无映射的词保持原样不猜。写新文章时 tag 从 `site/matrix.js` 词表里选，收不进词表的先扩词表再使用，让 skill-drift 的落位检查保持干净。
- **必须看清结果**：不要用 `tail -1` 等会吞掉失败信息的方式看输出；有一次只看最后一行把 1 个失败当成全过，差点带病上线。
- **修源头不改断言**：断言失败 = 代码或内容有问题。禁止为了让测试通过而改断言。
- 测试的正确用途示例：它拦住过 vault wikilink 前缀错误导致的断链——内容问题也是发布阻塞项。

## 内容红线（仓库是公开的）

- 禁止把内部产品名写进 vault（`tbase` / `tchouse` / `csig`），正文、标题、文件名、链接都算。
- 禁止把内部统计口径、方法论、分类依据写进页面（受众规则）。
- 数据文件不入库：`data/*` 被 gitignore，唯一例外 `data/favorites.json`（跨机共享收藏）。
- **写盘前备份**：清洗/迁移运行时数据前先 `.bak` 一份（清理访问记录时留过 `.bak-clean`）。

## 降级（任何新增能力都要能"没有也不坏"）

- 新增接口必须在 Pages 静态镜像下静默降级：取不到数据就不显示该区块，**禁止白屏、禁止报错弹窗**。
- 管理类控件（钉选/取消等）在无后端时自动隐藏，而不是显示成死按钮。
- 新增接口的实现顺序：先写降级路径，再写正常路径。

## i18n

- 文案改动必须**中英双版同步**（删/加都要两版一起动）。
- 新增文案要有 zh/en 两条，并走 `TKI18N.translateDOM` 可翻译路径。
- 页面默认中文（站长定过：内容面向中文读者，国际化体现在 README 等项目说明上）。

## 主题

- 颜色全部 token 化，深浅主题自适应；禁止写死色值（写死白描边在深色主题刺眼）。
- SVG 描边用 `currentColor`，不要写死颜色。

## 回滚与变更纪律

- 动手前读取 `git status` 与相关文件差异，保留其他会话尚未提交的修改。需要恢复本次修改时，使用文件编辑工具恢复相应内容；禁止使用 Git 恢复工作区文件。
- 大改前后对比清单：路由表 / 接口清单 / 关键文件行号——防止重写时静默删能力（历史上发生过）。
- 删除能力（功能、区块、文案）前，先确认没有别处引用（grep 全仓），删完再 grep 一次验证归零。
- 声称"已删除/已修复"必须附验证证据：grep 计数、curl 状态码或截图。

## 发布后

- push 后必须做三端核对（18787 / woa 域名 / Pages），并提醒浏览器硬刷新。
- 确认方式：curl 服务端内容 grep 新代码标记（注意 URL 是 `/static/`，不是 `/site/`）。
