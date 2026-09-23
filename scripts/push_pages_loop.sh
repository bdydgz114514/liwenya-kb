#!/bin/bash
# 同步最新 dist → 提交 → 反复重试 push（github.com 时通时断）
set -u
TOKEN=$(cat /root/.github_token)
cd /tmp/ghpages
git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/bdydgz114514.github.io.git"
echo "[$(date +%T)] 同步 dist…"
rsync -a --delete --exclude='.git' --exclude='CNAME' /root/dsh/liwenya-kb/site/dist/ /tmp/ghpages/
timeout 300 git -c http.version=HTTP/1.1 fetch -q origin main 2>/dev/null && git reset --soft origin/main || echo "  （拉取远端历史失败，基于本地 origin/main 继续）"
git add -A
git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "站点：新增「知识库」入口页（数据下载 + 检索说明）、视频播放器与缩略图修复" && echo "  已提交 $(git rev-parse --short HEAD)"
for i in $(seq 1 60); do
  echo "[$(date +%T)] 第 $i 次 push…"
  if timeout 240 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -q origin main 2>/tmp/push_try.txt; then
    echo "[$(date +%T)] ✅ 推送成功（第 $i 次）"; echo PAGES_OK; exit 0
  fi
  tail -1 /tmp/push_try.txt | cut -c1-90
  sleep 45
done
echo "[$(date +%T)] ❌ 60 次仍未成功"; echo PAGES_FAIL