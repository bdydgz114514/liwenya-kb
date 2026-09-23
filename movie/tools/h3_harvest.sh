#!/bin/bash
# 把本次会话生成的 H3 镜头搬到下载目录（中文目录 + ASCII 副本，便于直接给链接）
set -u
SRC=/root/ComfyUI/output
DST="/root/output_videos/h3样片"
ALT=/root/output_videos
CUT=/tmp/h3_cutoff
[ -f "$CUT" ] || date +%s > "$CUT"
mkdir -p "$DST"
i=1
while true; do
  for f in "$SRC"/*-audio.mp4; do
    [ -f "$f" ] || continue
    base=$(basename "$f")
    stamp="$DST/.seen_$base"
    [ -f "$stamp" ] && continue
    if [ "$(stat -c %Y "$f")" -lt "$(cat "$CUT")" ]; then touch "$stamp"; continue; fi
    name=$(printf "h3_%02d.mp4" $i)
    if cp -f "$f" "$DST/$name"; then
      cp -f "$f" "$ALT/sample_h3_$(printf '%02d' $i).mp4"
      touch "$stamp"
      echo "[$(date +%T)] 新增 $name → sample_h3_$(printf '%02d' $i).mp4 （$(stat -c %s "$f" | awk '{printf "%.1f MB", $1/1048576}')）"
      i=$((i+1))
    fi
  done
  sleep 30
done