#!/bin/bash
# 稳健版：拉取远端历史 → 把当前工作树提交到远端之上 → push（带重试）
set -u
TOKEN=$(cat /root/.github_token)
push_repo(){
  local d=$1 name=$2 msg=$3
  cd "$d" || return 1
  git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/$name.git"
  echo "[$(date +%T)] $name：fetch…"
  local ok=0
  for i in 1 2 3 4 5; do
    if timeout 180 git -c http.version=HTTP/1.1 fetch -q origin main 2>/dev/null; then ok=1; break; fi
    echo "  fetch 第 $i 次失败，10s 重试"; sleep 10
  done
  if [ "$ok" != "1" ]; then echo "[$(date +%T)] ❌ $name 无法获取远端历史"; return 1; fi
  git reset --soft origin/main
  git add -A
  git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "$msg" || true
  echo "[$(date +%T)] $name：提交 $(git rev-parse --short HEAD)（父 $(git rev-parse --short HEAD^ 2>/dev/null)）→ push…"
  if timeout 1200 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -q origin main 2>/tmp/push_err_$name.txt; then
    echo "[$(date +%T)] ✅ $name 推送成功"
  else
    echo "[$(date +%T)] ❌ $name 推送失败：$(tail -2 /tmp/push_err_$name.txt | tr '\n' ' ')"
  fi
}
push_repo /root/dsh/liwenya-wiki liwenya-wiki "站点源码：长篇传记（30 章）+ 电影页 + 在线全片"
push_repo /root/dsh/liwenya-kb-repo liwenya-kb "知识库：传记定本、电影元数据、经验文档与发布脚本"
echo REPOS_PUSH2_DONE