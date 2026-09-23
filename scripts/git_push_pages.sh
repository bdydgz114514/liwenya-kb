#!/bin/bash
# 用原生 git push 发布 Pages（比 API 快得多）
set -u
TOKEN=$(cat /root/.github_token)
cd /tmp/ghpages
git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/bdydgz114514.github.io.git"
echo "[$(date +%T)] 同步 dist…"
rsync -a --delete --exclude='.git' --exclude='CNAME' /root/dsh/liwenya-kb/site/dist/ /tmp/ghpages/
git add -A
git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "李文亚 Wiki：长篇传记（30 章）、电影页、预告片与在线全片（480p 三段）" && echo "[$(date +%T)] 已提交 $(git rev-parse --short HEAD)" || echo "[$(date +%T)] 无改动"
echo "[$(date +%T)] git push…"
if timeout 900 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin main 2>&1 | tail -3; then
  echo "[$(date +%T)] ✅ Pages 推送完成"
else
  echo "[$(date +%T)] ❌ Pages 推送失败"
fi
echo PAGES_PUSH_DONE