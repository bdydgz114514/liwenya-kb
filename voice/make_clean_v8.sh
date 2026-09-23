#!/bin/bash
# v8：v7 的修正版 —— 混音后用「线性增益」而非动态 loudnorm，避免把前奏抬起来
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
KB=/root/dsh/liwenya-kb
WORK=$KB/voice/clean
FT=$(ls -d $KB/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v8}
VIDEO=${2:-$KB/voice/faceswap/faceswap_full.mp4}
OUT=$KB/voice/faceswap
MODEL=${3:-/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth}
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
TARGET_LUFS=${4:--13.5}

measure_lufs() { ffmpeg -v info -i "$1" -af loudnorm=print_format=summary -f null - 2>&1 | grep 'Input Integrated' | head -1 | sed 's/.*: *//; s/ *LUFS.*//'; }

echo "== [1/6] 人声活动掩码 $(date '+%T')"
python3 $KB/voice/vocal_mask.py "$FT/vocals.wav" "$WORK/vocal_${TAG}_masked.wav" "$WORK/vocal_${TAG}_mask.npy"

echo "== [2/6] RVC 只转换人声段 $(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_${TAG}_masked.wav" \
  --output "$WORK/vocal_ai_${TAG}.raw.wav" --f0-method pm --index-rate 0.75 --protect 0.33 --format wav --overwrite 2>&1 | tail -1

echo "== [3/6] 掩码去噪 + 响度对齐原唱人声 $(date '+%T')"
python3 $KB/voice/apply_mask.py "$WORK/vocal_ai_${TAG}.raw.wav" "$WORK/vocal_${TAG}_mask.npy" "$FT/vocals.wav" "$WORK/vocal_ai_${TAG}.wav"

echo "== [4/6] 轻处理 $(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_${TAG}.wav" -af "highpass=f=85,equalizer=f=3500:t=q:w=1.5:g=2,alimiter=limit=0.95" -ar 48000 -ac 2 "$WORK/vocal_ai_${TAG}.final.wav"

echo "== [5/6] 混音 + 线性母带（不动态压缩）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_${TAG}.final.wav" -i "$FT/no_vocals.wav" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0" -c:a pcm_s16le "$WORK/mix_${TAG}_raw.wav"
L=$(measure_lufs "$WORK/mix_${TAG}_raw.wav")
GAIN=$(python3 -c "print(round(${TARGET_LUFS} - (${L}), 2))")
echo "    混音响度 $L LUFS -> 目标 $TARGET_LUFS LUFS (线性增益 ${GAIN} dB)"
ffmpeg -v error -y -i "$WORK/mix_${TAG}_raw.wav" -af "volume=${GAIN}dB,alimiter=limit=0.95" -c:a aac -b:a 256k "$WORK/cover_${TAG}.m4a"
echo "    成品响度 $(measure_lufs "$WORK/cover_${TAG}.m4a") LUFS"

echo "== [6/6] 与静音换脸画面合成 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_${TAG}.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_${TAG}.mp4"
ls -la "$OUT/ai_liwenya_${TAG}.mp4"
echo V8_DONE