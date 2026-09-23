#!/bin/bash
# 一键：生成场景卡 → 导出知识库数据 → 同步到站点 → 构建
set -e
cd /root/dsh/liwenya-kb
echo '[1/4] 生成场景卡…'
python scripts/fuse.py cards | tail -1
echo '[2/4] 导出知识库数据…'
python scripts/kb.py export --thumbs | tail -2
echo '[3/4] 同步到站点数据目录…'
cp kb/export/site.json kb/export/people.json kb/export/theories.json kb/export/events.json kb/export/glossary.json kb/export/videos.json kb/export/graph.json kb/export/bilibili.json kb/export/textbook.json kb/export/novel.json site/src/data/
echo '[4/4] 构建站点…'
cd site && npm run build 2>&1 | tail -6