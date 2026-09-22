# Mac 侧上游拉取脚本：与 dev 的 update-knowledge.sh 对等。
# GitHub 是唯一枢纽——dev/Mac 各自只 pull、各自 push，永不互相直连。
# 被 com.leoqqian.knowledge-pull LaunchAgent 每分钟调用（/bin/sh 显式解释）。
#
# 三条安全阀：
# 1. 工作区有未提交改动 → 直接跳过（Obsidian 正在写作时不搅局）；
# 2. 本地领先（有 commit 没 push）→ 跳过（绝不自动动用户的本地提交）；
# 3. 分叉（两边都有对方没有的提交）→ 只报警不硬合并，人工处理。
set -eu
cd /Users/leoqqian/Developer/technical-knowledge
if ! git diff --quiet || ! git diff --cached --quiet; then
    exit 0
fi
OLD=$(git rev-parse HEAD)
git fetch origin main --quiet 2>/dev/null || exit 0
NEW=$(git rev-parse origin/main)
[ "$OLD" = "$NEW" ] && exit 0
BASE=$(git merge-base "$OLD" "$NEW" 2>/dev/null || echo "")
if [ "$BASE" = "$OLD" ]; then
    git pull --ff-only origin main
    echo "$(date '+%F %T') pulled ${OLD:0:7} -> ${NEW:0:7} ($(git diff --name-only "$OLD" "$NEW" | wc -l) files)"
elif [ "$BASE" = "$NEW" ]; then
    exit 0
else
    echo "$(date '+%F %T') diverged (local ${OLD:0:7} vs origin ${NEW:0:7}) — manual fix needed"
    exit 1
fi
