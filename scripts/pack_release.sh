#!/bin/bash
# 生成离线包 / 上传包（站点 dist + 单文件版）
set -eu
SRC=/root/dsh/liwenya-kb
OUT=/root/output_videos
WIN=$SRC/release/win
TMP=$(mktemp -d /tmp/pack.XXXX)
trap 'rm -rf "$TMP"' EXIT

echo "[pack] 生成单文件版 ..."
python3 "$SRC/scripts/make_single_file.py" "$OUT/李文亚Wiki_单文件版.html" | tail -1

echo "[pack] 组装 Windows 离线目录 ..."
mkdir -p "$TMP/wiki_win"
cp "$WIN/启动Wiki.bat" "$WIN/serve.ps1" "$WIN/使用说明.txt" "$TMP/wiki_win/" 2>/dev/null || true
cp "$OUT/李文亚Wiki_单文件版.html" "$TMP/wiki_win/"
cp "$SRC"/release/README_离线版.txt "$TMP/wiki_win/README.txt" 2>/dev/null || true
rsync -a "$SRC/site/dist/" "$TMP/wiki_win/site/"
# 单文件版也放进 site，便于分享
cp "$OUT/李文亚Wiki_单文件版.html" "$TMP/wiki_win/site/单文件版.html"

echo "[pack] 组装上传目录 ..."
mkdir -p "$TMP/wiki_upload"
rsync -a "$SRC/site/dist/" "$TMP/wiki_upload/"

cd "$TMP"
echo "[pack] 压缩 ..."
rm -f "$OUT/李文亚Wiki_离线版.zip" "$OUT/liwenya-wiki-offline-win.zip" "$OUT/李文亚Wiki_上传包.zip"
zip -qr "$OUT/李文亚Wiki_离线版.zip" wiki_win
cp "$OUT/李文亚Wiki_离线版.zip" "$OUT/liwenya-wiki-offline-win.zip"
zip -qr "$OUT/李文亚Wiki_上传包.zip" wiki_upload
du -h "$OUT/李文亚Wiki_离线版.zip" "$OUT/李文亚Wiki_上传包.zip" | sed 's/^/[pack] /'
echo PACK_DONE
