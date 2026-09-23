#!/bin/bash
# 耐心版：源码仓库推送（fetch 最多重试 20 次，间隔 30 秒）
set -u
TOKEN=$(cat /root/.github_token)
push_repo(){
  local d=$1 name=$2 msg=$3
  cd "$d" || return 1
  git remote set-url origin "https://bdydgz114514:$TOKEN@github.com/bdydgz114514/$name.git"
  echo "[$(date +%T)] $name：fetch…"
  local ok=0
  for i in $(seq 1 20); do
    if timeout 120 git -c http.version=HTTP/1.1 fetch -q origin main 2>/dev/null; then ok=1; break; fi
    echo "  [$(date +%T)] fetch 第 $i 次失败"; sleep 30
  done
  if [ "$ok" != "1" ]; then echo "[$(date +%T)] ❌ $name 仍无法获取远端历史"; return 1; fi
  git reset --soft origin/main
  git add -A
  git -c user.email=kb@local -c user.name=liwenya-kb commit -q -m "$msg" || true
  echo "[$(date +%T)] $name：push $(git rev-parse --short HEAD)…"
  for i in $(seq 1 10); do
    if timeout 900 git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -q origin main 2>/tmp/e_$name.txt; then
      echo "[$(date +%T)] ✅ $name 推送成功"; return 0
    fi
    echo "  [$(date +%T)] push 第 $i 次失败：$(tail -1 /tmp/e_$name.txt | cut -c1-80)"; sleep 30
  done
  echo "[$(date +%T)] ❌ $name 推送失败"; return 1
}
push_repo /root/dsh/liwenya-wiki liwenya-wiki "站点源码：长篇传记 + 电影 + 年表扩充（38 条）"
push_repo /root/dsh/liwenya-kb-repo liwenya-kb "知识库：事件年表扩充至 38 条、传记与电影数据、经验文档"
echo REPOS_PUSH3_DONE