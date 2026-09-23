#!/bin/bash
# 一键重发：站点构建 → 三个仓库推送 → 离线发布包
set -u
SRC=/root/dsh/liwenya-kb
TOKEN=$(cat /root/.github_token)
USER=bdydgz114514
LOG=$SRC/logs/republish.log
mkdir -p "$SRC/logs"; : > "$LOG"
exec >>"$LOG" 2>&1
log(){ echo "[$(date +%H:%M:%S)] $*"; }

push_retry(){  # $1=仓库目录 $2=分支 $3=名称 $4=owner/repo
  local d=$1 br=$2 label=$3 full=$4
  # 先试一次原生 git push（快，一次传完增量）；失败则改用 GitHub Git Data API。
  # 本机 github.com:443 时通时断：git push 会卡住或报 Authentication failed，而 api.github.com 一直可用。
  if timeout 90 git -C "$d" -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -q -f origin "$br" 2>&1; then
    log "$label git 推送成功"; return 0
  fi
  log "$label git 推送不可用，改用 GitHub API 推送"
  if python3 "$SRC/scripts/api_push.py" "$d" "$full" "$br" "$label：$(date +%F) 更新" 2>&1 | tail -4; then
    log "$label API 推送成功"; return 0
  fi
  log "$label 推送失败"; return 1
}

log "=== 1) 构建站点 ==="
cd "$SRC/site" && npm run build 2>&1 | tail -4
log "首页字节：$(wc -c < dist/index.html)"

log "=== 2) 组装仓库 ==="
cd /root && bash "$SRC/scripts/build_repos.sh" 2>&1 | tail -3

log "=== 3) GitHub Pages 发布分支 ==="
GH=/tmp/ghpages
if [ ! -d "$GH/.git" ]; then
  rm -rf "$GH"; git clone -q "https://$USER:$TOKEN@github.com/$USER/$USER.github.io.git" "$GH"
fi
git -C "$GH" remote set-url origin "https://$USER:$TOKEN@github.com/$USER/$USER.github.io.git"
rsync -a --delete --exclude='.git' --exclude='CNAME' "$SRC/site/dist/" "$GH/"
git -C "$GH" add -A
git -C "$GH" -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "李文亚 Wiki：理论页新增教科书级讲解与 3D 物理模型演示（$(date +%Y-%m-%d)）" || log "无改动可提交"
push_retry "$GH" main Pages "$USER/$USER.github.io"

log "=== 4) 站点源码仓库 ==="
WIKI=/root/dsh/liwenya-wiki
if [ ! -d "$WIKI/.git" ]; then git -C "$WIKI" init -q -b main; fi
git -C "$WIKI" remote remove origin 2>/dev/null
git -C "$WIKI" remote add origin "https://$USER:$TOKEN@github.com/$USER/liwenya-wiki.git"
git -C "$WIKI" add -A
git -C "$WIKI" -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "站点源码：教科书级讲解 + 3D 模型演示（$(date +%Y-%m-%d)）" || log "无改动可提交"
push_retry "$WIKI" main liwenya-wiki "$USER/liwenya-wiki"

log "=== 5) 知识库仓库 ==="
KB=/root/dsh/liwenya-kb-repo
if [ ! -d "$KB/.git" ]; then git -C "$KB" init -q -b main; fi
git -C "$KB" remote remove origin 2>/dev/null
git -C "$KB" remote add origin "https://$USER:$TOKEN@github.com/$USER/liwenya-kb.git"
git -C "$KB" add -A
git -C "$KB" -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "知识库：理论教科书数据 textbook.json 与最新导出（$(date +%Y-%m-%d)）" || log "无改动可提交"
push_retry "$KB" main liwenya-kb "$USER/liwenya-kb"

log "=== 6) 离线发布包 ==="
bash "$SRC/scripts/pack_release.sh" 2>&1 | tail -6

log "=== 完成 ==="
ls -la /root/output_videos/*.zip /root/output_videos/*.html | awk '{print $5, $9}'
echo REPUBLISH_DONE
