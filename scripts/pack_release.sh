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
# 档案播放服务（把归档目录接上后，站点里的视频页可以直接播放原件）
cp /root/dsh/movie/tools/site_server.py "$TMP/wiki_win/档案播放服务.py" 2>/dev/null || true
cat > "$TMP/wiki_win/档案播放说明.txt" <<'EOF'
档案视频播放（可选）
====================
站点里的每个视频页都带播放器，但视频原件（AV1/Opus 的 MKV，共 1206 个、约 170 小时）
没有随包分发——包只有几个 GB，放不下。若你手上有归档目录，可以这样在本机播放：

1) 安装 Python 3 与 ffmpeg（命令行里能直接运行 python 和 ffmpeg 即可）；
2) 把本文件所在目录（wiki_win）与归档目录放在同一台机器上；
3) 在本目录执行（把路径换成你的归档根目录，即包含「核心视频本体」等子目录的那一层）：
     python 档案播放服务.py --port 8898 --root site --archive "D:\李文亚世界v2.0_full_compressed"
4) 浏览器打开 http://localhost:8898/ ，进入任意视频页，播放器会自动接上并实时转码播放。

说明：转码是实时的（H.264 + AAC），CPU 占用较高；播放页右上角会显示「档案服务已连接」。
若只想看文字与图片，直接双击「启动Wiki.bat」即可，不需要这一步。
EOF

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
