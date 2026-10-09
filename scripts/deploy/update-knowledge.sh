#!/usr/bin/env bash
# 带门禁的发布：候选版本先在临时 worktree 里过测试与内容门禁，两道都过才切换并重启。
#
# 原来的做法是 git pull --ff-only 之后直接 systemctl restart。两个后果：
#   1. 新版本有问题也已经进了工作目录，重启前那一刻线上跑的是旧进程 + 新代码，
#      两者不一致；重启失败就停在这个状态，读者看到的是半新半旧
#   2. 门禁根本没跑——测试与内容检查都在发布之外，坏内容照样上线
# 现在的做法：拉到临时 worktree 里跑门禁，工作目录一个字节都不动。门禁不过就
# 什么都不做，线上旧版本继续服务，原因写进 .editorial/reports/deploy-<时间>.md，
# 中台的「知识保鲜」板块会显示这一句。
#
# 门禁两道，顺序固定：
#   1. python3 -m pytest tests -q            站点行为
#   2. knowledge-governor/scripts/check_knowledge.sh   内容契约与脱敏，ERROR 必须为 0
# WARN 不阻断（过复查日、缺 tags 这类天天都有，拿它挡发布等于门禁永远关着），
# 但会记进报告。
#
# 仓库路径从脚本自身位置推导（scripts/deploy → 仓库根），不写固定值：
# 同一个脚本在开发机、服务器、临时 worktree 里都要能跑。
#
# 可覆盖的环境变量：
#   KNOWLEDGE_REMOTE        远端名，默认 origin
#   KNOWLEDGE_BRANCH        分支名，默认 main
#   KNOWLEDGE_RESTART_CMD   重启命令，默认 systemctl restart knowledge-site
#   KNOWLEDGE_CHECK_SCRIPT  内容门禁脚本，默认 <仓库根>/../knowledge-governor/scripts/check_knowledge.sh
#   PYTHON                  python 解释器，默认 python3
#
# 退出码：0 无更新或发布成功；1 门禁拦下或发布失败；2 环境不完整。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
cd "$REPO" || exit 2

REMOTE="${KNOWLEDGE_REMOTE:-origin}"
BRANCH="${KNOWLEDGE_BRANCH:-main}"
RESTART_CMD="${KNOWLEDGE_RESTART_CMD:-systemctl restart knowledge-site}"
PYTHON="${PYTHON:-python3}"
CHECK_SCRIPT="${KNOWLEDGE_CHECK_SCRIPT:-$(dirname "$REPO")/knowledge-governor/scripts/check_knowledge.sh}"
REPORTER="$SCRIPT_DIR/write_deploy_report.py"
WORK_ROOT="$REPO/.editorial/deploy"

log() { echo "$(date '+%F %T') $*"; }

OLD=""
NEW=""

# 门禁拦下：写报告，不切换、不重启
block() {
  local stage="$1" reason="$2" detail_file="$3"
  local report
  report=$("$PYTHON" "$REPORTER" --repo "$REPO" --stage "$stage" --result blocked \
    --reason "$reason" --detail-file "$detail_file" --old "$OLD" --new "$NEW")
  log "门禁拦下（$stage）：$reason"
  log "线上保持旧版本 ${OLD:0:7} 继续服务，原因见 $report"
}

pass_report() {
  local note="$1" detail_file="$2"
  "$PYTHON" "$REPORTER" --repo "$REPO" --stage restart --result passed \
    --reason "$note" --detail-file "$detail_file" --old "$OLD" --new "$NEW" >/dev/null
}

[ -f "$REPORTER" ] || { echo "缺少报告脚本: $REPORTER" >&2; exit 2; }
[ -f "$CHECK_SCRIPT" ] || { echo "缺少内容门禁脚本: $CHECK_SCRIPT（可用 KNOWLEDGE_CHECK_SCRIPT 指定）" >&2; exit 2; }

OLD=$(git rev-parse HEAD) || exit 2
git fetch "$REMOTE" "$BRANCH" --quiet 2>/dev/null || exit 0
NEW=$(git rev-parse "$REMOTE/$BRANCH") || exit 2
[ "$OLD" = "$NEW" ] && exit 0

BASE=$(git merge-base "$OLD" "$NEW" 2>/dev/null || echo "")
if [ "$BASE" = "$NEW" ]; then
  # 本地已经领先远端，没有可发布的新版本
  exit 0
fi
if [ "$BASE" != "$OLD" ]; then
  log "本地 ${OLD:0:7} 与远端 ${NEW:0:7} 已分叉，需要人工处理"
  exit 1
fi

mkdir -p "$WORK_ROOT"
STAMP="$(date '+%Y%m%d-%H%M%S')"
WORKTREE="$WORK_ROOT/candidate-$STAMP"
LOGFILE="$WORK_ROOT/gate-$STAMP.log"
: > "$LOGFILE"

cleanup() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || rm -rf "$WORKTREE"
  git worktree prune >/dev/null 2>&1
}
trap cleanup EXIT

if ! git worktree add --detach --quiet "$WORKTREE" "$NEW" >>"$LOGFILE" 2>&1; then
  block "worktree" "临时 worktree 创建失败，无法在不动线上目录的前提下跑门禁" "$LOGFILE"
  exit 1
fi

# 1. 站点测试。在 worktree 里跑，线上目录不受影响
log "门禁 1/2：在 $WORKTREE 跑 pytest"
echo "=== python3 -m pytest tests -q（$WORKTREE）===" >>"$LOGFILE"
(cd "$WORKTREE" && "$PYTHON" -m pytest tests -q) >>"$LOGFILE" 2>&1
TEST_RC=$?
echo "pytest 退出码 $TEST_RC" >>"$LOGFILE"
if [ "$TEST_RC" -ne 0 ]; then
  failed=$(grep -cE '^(FAILED|ERROR) ' "$LOGFILE")
  block "pytest" "站点测试未通过（退出码 $TEST_RC，$failed 条 FAILED/ERROR），详见报告里的输出" "$LOGFILE"
  exit 1
fi

# 2. 内容门禁。只有 ERROR 阻断，WARN 记录
log "门禁 2/2：对候选版本跑 check_knowledge.sh"
AUDIT_LOG="$WORK_ROOT/audit-$STAMP.log"
KNOWLEDGE_REPO="$WORKTREE" bash "$CHECK_SCRIPT" >"$AUDIT_LOG" 2>&1
AUDIT_RC=$?
cat "$AUDIT_LOG" >>"$LOGFILE"
ERRORS=$(awk '/^ERROR:/ {print $2}' "$AUDIT_LOG" | tail -1)
WARNS=$(awk '/^ERROR:/ {print $4}' "$AUDIT_LOG" | tail -1)
ERRORS="${ERRORS:-未知}"
WARNS="${WARNS:-0}"
if [ "$ERRORS" != "0" ]; then
  block "knowledge-audit" "内容门禁 ERROR $ERRORS 条（WARN $WARNS 条不阻断）" "$LOGFILE"
  exit 1
fi
if [ "$AUDIT_RC" -ne 0 ]; then
  block "knowledge-audit" "内容门禁退出码 $AUDIT_RC，ERROR 计数读不出来" "$LOGFILE"
  exit 1
fi
log "内容门禁通过：ERROR 0，WARN $WARNS（只记录不阻断）"

# 门禁两道都过，才动线上目录
if ! git pull --ff-only "$REMOTE" "$BRANCH" --quiet >>"$LOGFILE" 2>&1; then
  block "switch" "快进合并失败，线上目录未改动" "$LOGFILE"
  exit 1
fi

if ! eval "$RESTART_CMD" >>"$LOGFILE" 2>&1; then
  # 代码已经切换但服务没起来：这是必须说清的状态，否则会以为发布成功了
  block "restart" "新版本已切换但重启失败，进程仍是旧版本，需要人工重启" "$LOGFILE"
  exit 1
fi

CHANGED=$(git diff --name-only "$OLD" "$NEW" | wc -l | tr -d ' ')
pass_report "改动 $CHANGED 个文件，内容门禁 WARN $WARNS 条（只记录）" "$LOGFILE"
log "已发布 ${OLD:0:7} -> ${NEW:0:7}（$CHANGED 个文件），站点已重启"
exit 0
