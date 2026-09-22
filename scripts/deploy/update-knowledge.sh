#!/bin/sh
set -eu
cd /data/code/technical-knowledge
OLD=$(git rev-parse HEAD)
git fetch origin main --quiet 2>/dev/null || exit 0
NEW=$(git rev-parse origin/main)
[ "$OLD" = "$NEW" ] && exit 0
BASE=$(git merge-base "$OLD" "$NEW" 2>/dev/null || echo "")
if [ "$BASE" = "$OLD" ]; then
  git pull --ff-only origin main
  systemctl restart knowledge-site
  echo "$(date '+%F %T') updated ${OLD:0:7} -> ${NEW:0:7} ($(git diff --name-only "$OLD" "$NEW" | wc -l) files); site restarted"
elif [ "$BASE" = "$NEW" ]; then
  exit 0
else
  echo "$(date '+%F %T') diverged (local ${OLD:0:7} vs origin ${NEW:0:7}) — manual fix needed"
  exit 1
fi
