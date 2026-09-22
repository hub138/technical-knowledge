# 多写者协作（Mac ↔ dev）

## 基本事实

- 两侧都能写：Mac 侧仓库与 dev 侧克隆（路径随机器而定，用 `KNOWLEDGE_REPO` 环境变量或技能目录同级的 `technical-knowledge` 定位，不写死绝对路径）。
- **GitHub 是唯一枢纽**，两侧不直连。
- 自动同步只**拉取不推送**：dev 每 5 分钟、Mac 每 60 秒。所以「让另一端看到」= 必须 push。

## commit 与 push 的边界（别混）

- **commit = 本地落地（必做）**：工作区有未提交内容会直接挡住 `git pull`，导致部署卡住。改完就提交，别留脏工作区。
- **push = 交付到另一端（看目的）**：
  - 只想在本机保住工作 → commit 足够，**不必 push**。
  - 要让另一端/线上/Pages 看到 → **必须 push**。
- 未 push 的本地提交属于「进行中未同步」：另一端看不到、Pages 不重建，且与上游形成分叉，后续 pull 需 `--rebase`。**不要把它当成已上线**。

## 标准流程（任一侧改完）

```bash
git add -A
git commit -m "..."                 # 必做：先让工作区干净
git pull --rebase origin main       # 变基到上游，保持线性历史；冲突就地解决
git push origin HEAD:main           # 需要跨端同步时才做（显式分支名，dev 本地分支曾叫 master）
```

## 拉取被挡的处理

- 症状：`git pull` 报「请提交或贮藏它们」。
- 原因：工作区有未提交改动（站主的直改、运行时数据文件如 favorites.json、其他会话的实验结果）。
- 处理顺序：
  1. `git status --short` **先看是什么**，不要盲目丢弃——可能包含站主的真实工作或真实收藏数据。
  2. 属于要保留的工作 → `git add -A && git commit`，再 `--rebase` 合并，然后 push。
  3. 来历不明或暂时不需要 → `git stash`（安全保存，可 `git stash pop` 恢复），再 pull。
- 禁止：直接 `git checkout -- .` 或 `reset --hard` 清掉未确认的改动。

## 发布后核对

- push 后三端核对：`localhost:18787`（隧道）/ woa 域名 / Pages。
- 核对方式：curl 服务端内容 grep 新代码标记（注意 URL 是 `/static/`，不是 `/site/`）。
- 提醒浏览器硬刷新（Cmd+Shift+R），否则看到的是缓存的旧页面。

## 运营数据不参与这套流程

- 钉选头条、反馈、收藏、访问记录 → 直接写 dev `data/*.json`，**即时生效，无需 commit/push**。
- 唯一例外：`data/favorites.json` 是被 git 跟踪的（跨机共享收藏），它变了会显示成脏文件——提交它即可。
