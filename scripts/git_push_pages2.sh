#!/bin/bash
# 用原生 git push 发布 Pages：先把本地新提交“搬”到远端历史之上，避免 non-fast-forward
set -u
TOKEN=$(cat /root/.github_token)
cd /tmp/ghpages
git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/bdydgz114514.github.io.git"
echo "[$(date +%T)] 同步 dist…"
rsync -a --delete --exclude='.git' --exclude='CNAME' /root/dsh/liwenya-kb/site/dist/ /tmp/ghpages/

echo "[$(date +%T)] 拉取远端历史…"
timeout 300 git -c http.version=HTTP/1.1 fetch origin main 2>&1 | tail -2
git reset --soft origin/main
git add -A
git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "李文亚 Wiki：长篇传记（30 章）、电影页、预告片与在线全片（480p 三段）" && echo "[$(date +%T)] 已提交 $(git rev-parse --short HEAD)（父提交 $(git rev-parse --short HEAD^)）"

echo "[$(date +%T)] git push…"
timeout 1200 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin main > /tmp/push_out.txt 2>&1
rc=$?
tail -3 /tmp/push_out.txt
if [ "$rc" = "0" ]; then echo "[$(date +%T)] ✅ Pages 推送成功"; else echo "[$(date +%T)] ❌ Pages 推送失败（退出码 $rc）"; fi
echo PAGES_PUSH_DONE