# 状态、动效与反馈

入口：做 hover/focus/当前项/禁用、加载空错态、动效时读。

## 五态必须齐

| 态 | 要求 |
|---|---|
| 默认 | 层级正确，不靠 hover 才看得懂 |
| hover | 有可见反馈 + `cursor: pointer`；过渡 150–300ms |
| focus | 键盘可达且有可见描边，不能只给鼠标做（ui-ux-pro-max 交付清单） |
| 当前（current） | 用 `aria-current`，视觉上实底框/左竖条/字重，回答"你在哪" |
| disabled | 明确变浅且不可点，不要只有颜色变化 |

- hover 不要做会推动布局的位移（scale 位移、边框突然加粗都算），只改颜色/阴影/透明度（ui-ux-pro-max `Stable hover states`）。
- 触屏上没有 hover，主要交互必须能点，不能只挂在 `mouseenter`（同库 `Hover vs Tap`）。

## 当前态与推荐态是两套语义

- 当前位置：路由决定，实底框，语义神圣，不挪用。
- 推荐/钉选：人工指定，暖色项，常驻亮着。
- 两者叠加时观感要自洽（访问钉选项时两态并存，不许互相吞掉）。
- 语义由结构决定（路由、人工标记），**不由数据决定**：阅读量/热度不驱动展示。

## 动效

- 时长 150–300ms；超过 500ms 让人不耐烦（frontend-design 动效章）。
- 必须有 `prefers-reduced-motion` 分支。
- 入场动画错峰用 `animation-delay`，别让所有元素一起动。
- 动效服务于"变化被看见"，不服务于炫技；找不到理由就不加。

## 加载 / 空 / 错误

- 超过 300ms 的操作必须有反馈（骨架屏或 spinner），不许界面冻住（ui-ux-pro-max `Loading Indicators`）。
- 异步内容预留尺寸（aspect-ratio 或固定高度），不许加载完把版面顶开（同库 `Content Jumping`）。
- 空态要有说明 + 一个动作，不许留白屏（同库 `Empty States`）。
- 错误信息必须带下一步怎么办；视觉之外要有 `role="alert"` 或 `aria-live`（同库 `Error Feedback` / `Error Messages`）。

## 无障碍底线

- 图片有 alt；表单有 label；颜色不是唯一信号；键盘能走完全流程。
- 状态变化同步进 URL，支持深链（同库 `Deep Linking`）。
