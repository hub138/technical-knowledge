---
title: Git 操作先区分工作区、索引与历史
type: reference
status: active
updated: 2026-08-31
review_after: 2027-02-28
change_rate: medium
confidence: high
tags:
  - "software/version-control"
  - "software/version-control"
sources:
  - "https://git-scm.com/docs"
  - "https://git-scm.com/docs/git-reflog"
  - "https://git-scm.com/docs/git-worktree"
---

# Git 操作先区分工作区、索引与历史

Git 的安全原则是先观察 refs、工作区和索引，再选择是否创建新历史、移动引用或修改文件。命令分类比背命令更重要。

## 机制与三层状态（要解决的问题：变更为什么需要中间状态）

```text
HEAD/commit 历史 <-> index/staging <-> working tree
                  refs/branches/tags
```

- `git status --short --branch`：当前分支、暂存和未暂存状态。
- `git diff`：工作区与 index；`git diff --staged`：index 与 HEAD。
- `git log --oneline --decorate --graph --all`：引用和历史拓扑。
- `git reflog`：本地引用移动日志，常用于找回误 reset/rebase 前的位置。

## 日常安全路径

```bash
git fetch --prune origin
git switch feature/name
git status --short --branch
git diff
git add path/to/intended-file
git diff --staged
git commit -m "type(scope): explain outcome"
```

默认显式 `git add <paths>`，避免把无关日志、密钥或生成物一起提交。push 前确认 upstream 和远端差异：

```bash
git branch -vv
git log --oneline --left-right --cherry-pick HEAD...@{upstream}
```

## 撤销方式按“是否共享”选择

| 目标 | 推荐 | 结果 |
| --- | --- | --- |
| 取消未暂存文件修改 | `git restore -- path` | 覆盖工作区文件，先看 diff |
| 取消暂存、保留工作区 | `git restore --staged -- path` | 只改 index |
| 撤销已共享 commit | `git revert <commit>` | 创建反向 commit，保留历史 |
| 修改尚未共享历史 | interactive rebase/reset | 移动/重写历史，先建 backup branch |
| 找回误操作前位置 | `git reflog` 后建新 branch | 先恢复引用，不立刻再 reset |

`reset --hard`、`clean -fdx`、强制 push、删除分支都可能造成难恢复损失；执行前精确列出目标、确认 diff/状态并建立引用。若确需更新重写后的远端历史，用 `--force-with-lease` 检查远端是否仍是预期位置，不能把它当无风险命令。

## Merge 与 Rebase

- merge 保留分支拓扑，适合共享分支或希望保留合并上下文。
- rebase 重放 commit 形成线性历史，适合尚未共享的个人分支整理。
- 冲突解决后必须运行测试并检查最终 diff；“Git 冲突已解决”只表示文本索引无冲突，不表示语义正确。
- 可用 `git merge --abort` / `git rebase --abort` 返回操作前状态；中途不要混入无关修改。

## Worktree 与自动化任务

`git worktree` 让多个工作目录共享同一 Git 仓库元数据。任务系统必须为 worktree 绑定 owner、revision、task generation 和 lease；其他任务仍在使用时不得 prune/remove 其元数据。每个任务报告实际 `git rev-parse HEAD` 与 dirty state，不能只相信计划中的分支名。见 [[工程知识/AI 系统工程：从模型能力到生产能力/安全与治理/执行证据必须独立于AI结论]]。

## 提交与审查

- 一个 commit 表达一个可审查结果，并同时包含相应测试/迁移。
- commit message 说明“为什么和结果”，代码 diff 说明“怎么做”。
- 不提交密钥、大型生成物、临时日志和个人环境配置；用 `.gitignore` 和 secret scan 门禁。
- 大规模 rename/format 与语义修改分开，便于 review 和 `git bisect`。

## 故障恢复顺序

1. 停止继续写历史，保存 `git status`、`git reflog`、HEAD 和相关日志。
2. 为当前与目标位置创建临时 backup refs/branches。
3. 在新 worktree/临时分支验证恢复点，不直接破坏当前目录。
4. 恢复后比较 diff、构建和测试，再决定移动正式引用。

关联：[[工程知识/软件构建：让变化可以理解、验证与交付/软件构建：让变化可以理解、验证与交付]]、[[工程知识/后端系统：在并发、失败与变化中维持服务/分布式可靠性/租约必须配合FencingToken阻止过期持有者]]、[[工程知识/软件构建：让变化可以理解、验证与交付/测试与交付/测试策略从风险选择证据]]。

## 边界

历史改写的安全边界只到未共享为止：push 后的提交改写要通知全部协作者并走强制推送流程，共享历史在协作场景的改写成本随人数上涨——已共享的历史用 revert 生成反向提交，回退的语义是追加，改写只留给私有分支。

## 效果与代价

三层模型的收益是变更的中间状态可控（工作区随意改、暂存区精选提交、历史按共享边界保护），代价是要维护三层的心理模型与配套命令；直接跳过暂存区（commit -a）的快，代价是提交粒度失控——提交历史是给未来读者看的账本，粒度失控的账本在回溯与 revert 时的成本远超日常的分层操作。

