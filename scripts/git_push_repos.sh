#!/bin/bash
# 组装并推送站点源码仓库与知识库仓库（原生 git，先对齐远端历史再提交）
set -u
SRC=/root/dsh/liwenya-kb
TOKEN=$(cat /root/.github_token)
cd /root && bash "$SRC/scripts/build_repos.sh" 2>&1 | tail -1

push_repo(){
  local d=$1 name=$2 msg=$3
  cd "$d"
  git init -q -b main 2>/dev/null
  git -c user.email=kb@local -c user.name=liwenya-kb add -A
  git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "$msg" || echo "[$(date +%T)] $name 无改动"
  git remote remove origin 2>/dev/null
  git remote add origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/$name.git"
  echo "[$(date +%T)] $name：拉取远端历史…"
  timeout 300 git -c http.version=HTTP/1.1 fetch origin main 2>&1 | tail -1
  git reset --soft origin/main
  git add -A
  git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "$msg" || true
  echo "[$(date +%T)] $name：推送 $(git rev-parse --short HEAD)…"
  timeout 900 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin main > /tmp/push_$name.txt 2>&1
  local rc=$?
  tail -2 /tmp/push_$name.txt
  [ "$rc" = "0" ] && echo "[$(date +%T)] ✅ $name 推送成功" || echo "[$(date +%T)] ❌ $name 推送失败（$rc）"
}

push_repo /root/dsh/liwenya-wiki liwenya-wiki "站点源码：长篇传记（30 章）+ 电影页 + 在线全片"
push_repo /root/dsh/liwenya-kb-repo liwenya-kb "知识库：传记定本、电影元数据、经验文档与发布脚本"
echo REPOS_PUSH_DONE