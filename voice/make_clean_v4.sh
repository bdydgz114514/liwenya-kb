#!/bin/bash
# v4：修正响度（人声不再被埋）+ 温和处理保高音
# 关键修正：v3 的 ORIG_LUFS 解析失败退化成 -20，导致 AI 人声比原唱低 4.8 dB、被伴奏盖住。
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
WORK=/root/dsh/liwenya-kb/voice/clean
FT=$(ls -d /root/dsh/liwenya-kb/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v4}
IR=${2:-0.75}
PROTECT=${3:-0.33}
VOCAL_TARGET=${4:--13.5}
INST_GAIN=${5:-0.90}
MASTER=${6:--13.5}
MODEL=/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
VIDEO=${7:-/root/dsh/liwenya-kb/voice/faceswap/faceswap_full.mp4}
F0METHOD=${8:-rmvpe}
OUT=/root/dsh/liwenya-kb/voice/faceswap

measure_lufs() {
  ffmpeg -v info -i "$1" -af loudnorm=print_format=summary -f null - 2>&1 | grep 'Input Integrated' | head -1 | sed 's/.*: *//; s/ *LUFS.*//'
}

echo "原唱人声 $(measure_lufs "$FT/vocals.wav") LUFS | 伴奏 $(measure_lufs "$FT/no_vocals.wav") LUFS"

echo "== [1/4] RVC 转换 (index=$IR protect=$PROTECT) $(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_clean.wav" \
  --output "$WORK/vocal_ai_$TAG.raw.wav" --f0-method "$F0METHOD" --index-rate "$IR" --protect "$PROTECT" --format wav --overwrite 2>&1 | tail -1

echo "== [2/4] 温和清理（保动态/保高音）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.raw.wav" -af \
  "highpass=f=85,arnndn=m=/root/dsh/rvc/models/bd.rnnn,deesser=i=0.3,equalizer=f=300:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.5:g=2,acompressor=threshold=-14dB:ratio=1.6:attack=15:release=250:makeup=2,loudnorm=I=${VOCAL_TARGET}:TP=-1.0:LRA=14" \
  -ar 48000 -ac 2 "$WORK/vocal_ai_$TAG.wav"
echo "    AI 人声响度: $(measure_lufs "$WORK/vocal_ai_$TAG.wav") LUFS（目标 $VOCAL_TARGET）"

echo "== [3/4] 混音（人声 1.0 / 伴奏 $INST_GAIN）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.wav" -i "$FT/no_vocals.wav" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=${INST_GAIN}[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.97,loudnorm=I=${MASTER}:TP=-1.0:LRA=14" \
  -c:a aac -b:a 256k "$WORK/cover_$TAG.m4a"
echo "    成品响度: $(measure_lufs "$WORK/cover_$TAG.m4a") LUFS"

echo "== [4/4] 合成视频 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_$TAG.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_$TAG.mp4"
ls -la "$OUT/ai_liwenya_$TAG.mp4"
echo V4_DONE $TAG