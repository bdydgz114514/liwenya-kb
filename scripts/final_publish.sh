#!/bin/bash
# 收尾发布：Pages 增量（预告片 + 在线分段 + 电影页）→ 站点源码仓库 → 知识库仓库
set -u
SRC=/root/dsh/liwenya-kb
USER=bdydgz114514
LOG=$SRC/logs/final_publish.log
: > "$LOG"
exec >>"$LOG" 2>&1
log(){ echo "[$(date +%H:%M:%S)] $*"; }

log "=== 1) Pages 增量推送 ==="
GH=/tmp/ghpages
git -C "$GH" remote set-url origin "https://$USER:$(cat /root/.github_token)@github.com/$USER/$USER.github.io.git"
rsync -a --delete --exclude='.git' --exclude='CNAME' "$SRC/site/dist/" "$GH/"
git -C "$GH" add -A
git -C "$GH" -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "李文亚 Wiki：电影页加入预告片与在线全片（480p 三段）" || log "无改动"
python3 -u "$SRC/scripts/api_push.py" "$GH" "$USER/$USER.github.io" main "电影页：预告片与在线全片" 2>&1 | tail -3

log "=== 2) 组装并推送两个源码仓库 ==="
cd /root && bash "$SRC/scripts/build_repos.sh" 2>&1 | tail -1
for spec in "liwenya-wiki:站点源码：长篇传记与电影页" "liwenya-kb:知识库：小说定本、电影元数据与经验文档"; do
  name=$(printf '%s' "$spec" | cut -d: -f1)
  msg=$(printf '%s' "$spec" | cut -d: -f2-)
  d=/root/dsh/$name
  [ "$name" = "liwenya-kb" ] && d=/root/dsh/liwenya-kb-repo
  git -C "$d" init -q -b main 2>/dev/null
  git -C "$d" -c user.email=kb@local -c user.name=liwenya-kb add -A
  git -C "$d" -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "$msg" || log "$name 无改动"
  python3 -u "$SRC/scripts/api_push.py" "$d" "$USER/$name" main "$msg" 2>&1 | tail -2
done

log "=== 完成 ==="
echo FINAL_PUBLISH_DONE
