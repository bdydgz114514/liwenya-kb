#!/bin/bash
# 组装两个发布仓库：liwenya-wiki（站点） + liwenya-kb（知识库）
set -e
SRC=/root/dsh/liwenya-kb
WIKI=/root/dsh/liwenya-wiki
KB=/root/dsh/liwenya-kb-repo
rm -rf "$WIKI" "$KB"
mkdir -p "$WIKI" "$KB"/{docs,scripts,kb/export,data,voice,sources}
# 1) 站点源码（不含 node_modules/构建产物）
tar -C "$SRC/site" --exclude=node_modules --exclude=dist --exclude=.astro -cf - . | tar -C "$WIKI" -xf -
# 2) 知识库
cp "$SRC"/docs/*.md "$KB/docs/"
cp "$SRC"/scripts/*.py "$SRC"/scripts/*.sh "$KB/scripts/"
cp "$SRC"/kb/export/*.json "$KB/kb/export/"
cp "$SRC"/kb/liwenya_kb.sqlite "$KB/kb/" 2>/dev/null || true
cp -r "$SRC"/data/transcripts "$KB/data/" 2>/dev/null || true
cp -r "$SRC"/data/cards "$KB/data/" 2>/dev/null || true
cp "$SRC"/sources/wiki_refs/*.md "$SRC"/sources/wiki_refs/*.json "$SRC"/sources/wiki_refs/*.txt "$KB/sources/" 2>/dev/null || true
cp "$SRC"/voice/*.py "$SRC"/voice/*.sh "$KB/voice/" 2>/dev/null || true
mkdir -p "$KB/voice/cover" && cp "$SRC"/voice/cover/*.m4a "$KB/voice/cover/" 2>/dev/null || true
# 2b) 发布前隐私脱敏（净化仓库副本里的 JSON/JSONL/MD 文本）
python3 "$SRC/scripts/privacy_filter_dir.py" "$KB" || true
# 2c) 知识库 README 与文档
cp "$SRC"/kb/README.md "$KB/README.md" 2>/dev/null || true
cp "$SRC"/docs/KB_README.md "$KB/README.md" 2>/dev/null || true
# 3) 通用文件
for R in "$WIKI" "$KB"; do
  printf 'node_modules/\ndist/\n.astro/\n__pycache__/\n*.pyc\n.venv/\n*.log\nmodels/\n*.wav\n*.mp4\n!voice/cover/*.m4a\n.github_token\n.credentials*\n' > "$R/.gitignore"
done
echo REPOS_BUILT