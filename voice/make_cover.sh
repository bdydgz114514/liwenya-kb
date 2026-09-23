#!/bin/bash
# 翻唱流水线：RVC 转换人声 -> 与伴奏混合 -> 回贴视频
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
cd /root/dsh/rvc/webui
export PYTHONPATH=/root/dsh/rvc/webui
TAG=${1:?用法: make_cover.sh <标签> <模型.pth> [索引.index]}
MODEL=${2:?缺少模型路径}
INDEX=${3:-}
WORK=/root/dsh/liwenya-kb/voice/cover
TARGET=/root/dsh/liwenya-kb/voice/target
SEP=$(ls -d $TARGET/separated/htdemucs/*/ | head -1)
mkdir -p "$WORK"
VOCALS="$SEP/vocals.wav"
INST="$SEP/no_vocals.wav"
OUT_V="$WORK/vocals_$TAG.wav"
OUT_MIX="$WORK/cover_$TAG.m4a"
OUT_VID="$WORK/cover_$TAG.mp4"
echo "== [1/3] RVC 转换 ($TAG)"
ARGS=(--model "$MODEL" --input "$VOCALS" --output "$OUT_V" --f0-method rmvpe --index-rate 0.75 --protect 0.33 --format wav --overwrite)
if [ -n "$INDEX" ]; then ARGS+=(--index "$INDEX"); fi
python -m infer.cli "${ARGS[@]}" 2>&1 | tail -4
echo "== [2/3] 混音"
ffmpeg -v error -y -i "$OUT_V" -i "$INST" -filter_complex "[0:a]volume=1.0[v];[1:a]volume=0.85[i];[v][i]amix=inputs=2:duration=longest:normalize=0" -c:a aac -b:a 192k "$OUT_MIX"
echo "== [3/3] 回贴视频"
VID=$(ls $TARGET/*.mp4 | head -1)
ffmpeg -v error -y -i "$VID" -i "$OUT_MIX" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest "$OUT_VID"
ls -la "$OUT_VID" "$OUT_MIX"
echo COVER_DONE $OUT_VID