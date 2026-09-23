#!/bin/bash
# 发布到 GitHub：创建/更新两个仓库并推送（token 只从 /root/.github_token 读取，不写入任何仓库文件）
set -e
TOKEN=$(cat /root/.github_token)
API=https://api.github.com
USER=$(curl -s -H "Authorization: Bearer $TOKEN" $API/user | python3 -c "import json,sys; print(json.load(sys.stdin)['login'])")
echo "账号: $USER"

bash /root/dsh/liwenya-kb/scripts/build_repos.sh

push_repo() {
  local DIR="$1" NAME="$2" DESC="$3"
  echo "== 发布 $NAME ($DIR)"
  curl -s -o /dev/null -w '  创建仓库 HTTP %{http_code}\n' -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" $API/user/repos \
    -d "{\"name\":\"$NAME\",\"description\":\"$DESC\",\"private\":false,\"has_issues\":true}" || true
  cd "$DIR"
  git init -q 2>/dev/null || true
  git config user.email "agent@localhost"; git config user.name "DSH Agent"
  git add -A
  git commit -qm "李文亚项目：$DESC" 2>/dev/null || echo '  （无新变更）'
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://$USER:$TOKEN@github.com/$USER/$NAME.git"
  git branch -M main 2>/dev/null || true
  git push -u origin main --force 2>&1 | tail -3
  git remote set-url origin "https://github.com/$USER/$NAME.git"
  echo "  ✅ https://github.com/$USER/$NAME"
}

push_repo /root/dsh/liwenya-wiki liwenya-wiki "李文亚 Wiki：仿 AMD 官网风格的静态百科站点（Astro + Tailwind + Pagefind）"
push_repo /root/dsh/liwenya-kb-repo liwenya-kb "李文亚知识库：1206 个视频的多模态理解结果、实体关系、检索数据与工程文档"

echo
echo "=== 安全检查：仓库内是否残留 token ==="
for d in /root/dsh/liwenya-wiki /root/dsh/liwenya-kb-repo; do
  if grep -rIl --exclude-dir=.git -E 'ghp_[A-Za-z0-9]{20,}|github_pat_' "$d" 2>/dev/null | head -3 | grep -q .; then
    echo "  ❌ $d 中发现疑似 token！"
  else
    echo "  ✅ $d 无 token 泄漏"
  fi
done
echo PUBLISH_DONE