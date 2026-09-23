#!/bin/bash
# v6：修复『高音上不去』——关键发现：预处理链（deesser/afftdn/压缩）会把高音削掉
#     原始分离人声+pm 基频提取 才能保住高音（90分位 697Hz vs 532Hz）
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
WORK=/root/dsh/liwenya-kb/voice/clean
FT=$(ls -d /root/dsh/liwenya-kb/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v6}
VIDEO=${2:-/root/dsh/liwenya-kb/voice/faceswap/faceswap_full.mp4}
MODEL=/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
OUT=/root/dsh/liwenya-kb/voice/faceswap

measure_lufs() { ffmpeg -v info -i "$1" -af loudnorm=print_format=summary -f null - 2>&1 | grep 'Input Integrated' | head -1 | sed 's/.*: *//; s/ *LUFS.*//'; }

echo "== [1/5] 仅去低频隆隆声（不做任何削高频处理）$(date '+%T')"
ffmpeg -v error -y -i "$FT/vocals.wav" -af "highpass=f=60" -ar 48000 -ac 1 "$WORK/vocal_v6_in.wav"

echo "== [2/5] RVC 转换（pm 基频 + index 0.75 + protect 0.33）$(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_v6_in.wav" \
  --output "$WORK/vocal_ai_$TAG.raw.wav" --f0-method pm --index-rate 0.75 --protect 0.33 --format wav --overwrite 2>&1 | tail -1

echo "== [3/5] 轻量后处理（不削高音）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.raw.wav" -af \
  "highpass=f=80,equalizer=f=300:t=q:w=1.2:g=-1.5,equalizer=f=3500:t=q:w=1.5:g=2,acompressor=threshold=-14dB:ratio=1.4:attack=20:release=300:makeup=1,loudnorm=I=-13.0:TP=-1.0:LRA=16" \
  -ar 48000 -ac 2 "$WORK/vocal_ai_$TAG.wav"
echo "    AI 人声响度: $(measure_lufs "$WORK/vocal_ai_$TAG.wav") LUFS"

echo "== [4/5] 混音 $(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.wav" -i "$FT/no_vocals.wav" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=0.88[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.97,loudnorm=I=-13.5:TP=-1.0:LRA=16" \
  -c:a aac -b:a 256k "$WORK/cover_$TAG.m4a"
echo "    成品响度: $(measure_lufs "$WORK/cover_$TAG.m4a") LUFS"

echo "== [5/5] 合成视频 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_$TAG.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_$TAG.mp4"
ls -la "$OUT/ai_liwenya_$TAG.mp4"
echo V6_DONE