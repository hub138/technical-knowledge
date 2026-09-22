---
name: design-craft
description: 好设计的成熟规矩——视觉层级、排版尺度、间距栅格、语义色 token、交互五态、信息密度、文案语气、交付自检。用于判断"这个页面好不好"、改布局配色排版、设计高亮与推荐位、美化已有界面。Use when 用户说好看/丑/改版式/配色/字号/间距/高亮/密度/对齐，或要美化、重排、重做某个界面。Do NOT use for 纯内容写作（归 knowledge-governor）、纯前端实现（归 knowledge-site-dev）。
---

# 好设计的规矩

## 冲突时的裁决顺序

1. **页面目的**：这个页面为什么存在、给谁看（见 `knowledge-governor/references/page-purposes.md`）。
2. **用户的实际评价**：他说好看就是好看。不许用"信息量大""更现代"反驳。
3. **下面的通用法则**。
4. 法则之间打架时：**可读性 > 一致性 > 个性**。

## 七条硬规则（任何界面都成立）

1. **层级靠三个维度一起拉开**：字号、字重、颜色深浅。只动一个维度等于没层级。（frontend-design 排版章；TDesign M03 字号/行高 Token）
2. **不靠颜色单独承载信息**：红绿之外必须有图标或文字。（ui-ux-pro-max ux-guidelines `Color Only`）
3. **正文对比度 ≥ 4.5:1**，灰字压灰底是禁止项。（同库 `Color Contrast` / `Contrast Readability`）
4. **间距走阶梯**：2/4/8/12/16/24/32/48/64，区块级留白优先 16/24/32/48。（TDesign M03 `--td-size-*`）
5. **可点元素三件套**：hover 反馈 + `cursor: pointer` + 键盘 focus 可见；过渡 150–300ms，超 500ms 让人不耐烦。（ui-ux-pro-max `Hover States`；frontend-design 动效章）
6. **不用 emoji 当 UI 图标**：用 SVG，统一 viewBox 24，同一套图标库。（ui-ux-pro-max `No emoji icons`）
7. **色值一律走 token**，不写死 hex；深浅主题靠 token 自适应，SVG 描边用 `currentColor`。（frontend-design 禁止硬编码色值；本项目实测：写死白描边在深色下刺眼）

## 按要动的东西加载

| 要动的东西 | 读 |
|---|---|
| 字号 / 字重 / 行高 / 行宽 / 字体 | `references/hierarchy-typography.md` |
| 间距 / 栅格 / 边距 / 对齐 / 密度 / 右栏 | `references/spacing-layout.md` |
| 配色 / 语义色 / 深浅主题 / 对比度 | `references/color-theme.md` |
| hover / focus / 当前态 / 禁用 / 动效 / 加载空错态 | `references/states-motion.md` |
| 页面文案 / 标语 / 说明文字 | `references/wording.md` |
| 交付前自检、觉得不对但说不清 | `references/review-checklist.md` |
| 找外部标杆、查某条规则的出处 | `references/sources.md` |

## 两条反直觉经验（本项目实测，不是抄来的）

- **引导元素要颜色和位置一起设计**：颜色对但埋没 = 没用；位置对但刺眼 = 反感。音量降到所在容器级别（导航项级，不要大卡级）。历史：大黄卡过重 → 安静小行无引导力 → 实底框位置混淆 → 暖橙导航项可用。
- **"当前位置"与"推荐"是两套语义**，必须视觉可区分：当前位置 = 实底框（路由决定），推荐 = 暖橙项（人工钉选）。实底框语义神圣，挪用一次导航定位就废。

## 红线

- 判断好坏以用户评价为准，不以"信息量大 / 酷炫 / 现代"自行排序。
- 删元素必须补位，不留空洞；太空 = 布局错，缩小容器重排，不是只删元素。
- 改完必须截图看，不能只看代码。
- 站点专属偏好（覆盖矩阵是默认 tab、八层气泡判丑、站长钦定的参考站）在 `knowledge-site-dev/references/design-language.md`，与本技能冲突时以那边为准。

## 参考文件

`references/hierarchy-typography.md` · `spacing-layout.md` · `color-theme.md` · `states-motion.md` · `wording.md` · `review-checklist.md` · `sources.md`
