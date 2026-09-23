#!/bin/bash
# 反复重试 git push，直到 github.com 可达（当前提交已在本地做好）
set -u
cd /tmp/ghpages
TOKEN=$(cat /root/.github_token)
git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/bdydgz114514.github.io.git"
for i in $(seq 1 40); do
  echo "[$(date +%T)] 第 $i 次尝试 push 84175dc…"
  if timeout 240 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -q origin main 2>/tmp/push_try.txt; then
    echo "[$(date +%T)] ✅ Pages 推送成功（第 $i 次）"
    echo PAGES_RETRY_OK
    exit 0
  fi
  tail -1 /tmp/push_try.txt | cut -c1-100
  sleep 45
done
echo "[$(date +%T)] ❌ 40 次仍未成功"
echo PAGES_RETRY_FAIL