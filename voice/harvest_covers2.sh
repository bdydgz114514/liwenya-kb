#!/bin/bash
# 把训练守望脚本产出的里程碑翻唱导出到下载目录（带中文名，供 8899 端口下载）
# 每个里程碑导出两份：换脸版（大，完整成品）+ 原画面版（小，便于快速试听）
KB=/root/dsh/liwenya-kb
OUT=/root/output_videos
LOG=$KB/logs/harvest_covers.log
ORIG=$(ls $KB/voice/target/*.mp4 2>/dev/null | head -1)
mkdir -p "$KB/logs"

num_for() {
  case "$1" in
    275) echo 20;; 300) echo 21;; 325) echo 22;; 350) echo 23;;
    375) echo 24;; 400) echo 25;; 425) echo 26;; 450) echo 27;;
  esac
}

for i in $(seq 1 1440); do
  for m in 275 300 325 350 375 400 425 450; do
    src=$(printf '%s/voice/cover/cover_e%s_clean.mp4' "$KB" "$m")
    audio=$(printf '%s/voice/clean/cover_r%s.m4a' "$KB" "$m")
    n=$(num_for "$m")
    dst=$(printf '%s/%s_cover_e%s_重训_换脸版.mp4' "$OUT" "$n" "$m")
    dst2=$(printf '%s/%sb_cover_e%s_原画面.mp4' "$OUT" "$n" "$m")
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
      s1=$(stat -c %s "$src"); sleep 6; s2=$(stat -c %s "$src")
      if [ "$s1" = "$s2" ] && [ "$s1" -gt 1000000 ]; then
        cp -f "$src" "$dst" && echo "[$(date +%T)] 导出 e$m 换脸版 → $(basename "$dst") ($((s1/1048576)) MB)" >> "$LOG"
      fi
    fi
    if [ -f "$audio" ] && [ -n "$ORIG" ] && [ ! -f "$dst2" ]; then
      ffmpeg -v error -y -i "$ORIG" -i "$audio" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$dst2" \
        && echo "[$(date +%T)] 导出 e$m 原画面版 → $(basename "$dst2") ($(stat -c %s "$dst2" | awk '{print int($1/1048576)}') MB)" >> "$LOG"
    fi
  done
  sleep 60
done
echo HARVEST_DONE
