# 出处与外部标杆

本技能每条规则都有来源。要深挖时按这里的入口去读原文，不要凭印象。

## 已读并提炼的技能（装在各自机器的技能目录下，如 `.agent/skills/`）

| 技能 | 从这里取了什么 |
|---|---|
| `ui-ux-pro-max` | ux-guidelines.csv（99 条 UX 规则，可 `python3 scripts/search.py "<关键词>" --domain ux` 检索）；交付前四段清单；禁用 emoji 当图标；hover 稳定性；浅色玻璃卡不透明度 |
| `tdesign-design-skill` | M03 字号/行高/间距/圆角 Token 表；M04 栅格 24px 边距、三级底色、侧栏 flex 写法、顶栏 56px 与 `min-height` 双保险 |
| `frontend-design` | 排版三旋钮、动效时长与 `prefers-reduced-motion`、背景细节、禁止硬编码色值、避免"通用 AI 美学" |
| `theme-factory` | 10 套成套主题（配色 + 字体配对），换风格时从 `themes/` 取成套方案，不要自己单点调色 |
| `canvas-design` | 视觉哲学的写法（先立意再画），做海报/头图类单幅视觉时用它 |
| `icon-designer` | 16 条图标规范（统一视角色板、正面视角、禁描边/投影/发光），生成图标时用它 |
| `archify`（本机与 dev 都装） | 画图判断与验收的来源：五类图路由、主路径唯一、边标签语义、validate→deliver→visual-check 三关验收；工具本体与 schema 归它，本技能 `references/diagrams.md` 只沉淀判断标准 |

`ui-ux-pro-max` 检索示例：

```
cd <skill 目录> && python3 scripts/search.py "contrast dark mode" --domain ux -n 8
python3 scripts/search.py "dashboard" --domain product
python3 scripts/search.py "elegant" --domain typography
```

## 视觉参考站（站长钦定，取长补短不照抄）

| 站 | 学什么 |
|---|---|
| bestblogs.dev/reading/follow | 总标杆：橙色调、导航、右上角、正文排版、夜间模式按钮、侧边栏、字数与阅读时长提示 |
| papernotes.org | 紫 + 深蓝配色、按会议分类、一句话摘要 |
| arxivdaily.com | 深红 logo、黑粗字体、清晰摘要 |
| ruanyifeng.com | 老牌口碑、内容组织 |
| readhub.cn / zeli.app | 资讯类设计思路（放最后，标资讯） |

## 待补（这次没拿到一手证据，别当依据引用）

- Refactoring UI（Wathan/Schoger）的具体条目：本次 web 检索没返回结果，规则暂按上面已读来源 + 本项目实测写。
- 标杆站点（Linear / Vercel / Stripe Docs）的实测结构数据：本次未抓取，需要时用 curl 抓真实 HTML/CSS 再补。
- Nielsen 十条、Dieter Rams 十条、Gestalt 原则：只在 spacing 里用了亲密性一条，其余待核。
