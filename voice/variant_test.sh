#!/bin/bash
# 针对“哑音”做多组推理参数对比（同一模型、同一掩码、同一混音母带口径）
set -u
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
KB=/root/dsh/liwenya-kb
WORK=$KB/voice/clean
FT=$(ls -d $KB/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
MODEL=/root/dsh/rvc/webui/assets/weights/liwenya_e250.pth
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
MASKED=$WORK/vocal_v11_masked.wav
MASK=$WORK/vocal_v11_mask.npy

measure_lufs() { ffmpeg -v info -i "$1" -af loudnorm=print_format=summary -f null - 2>&1 | grep 'Input Integrated' | head -1 | sed 's/.*: *//; s/ *LUFS.*//'; }

run() {
  local TAG=$1 F0=$2 IR=$3 PR=$4
  echo "== 变体 $TAG: f0=$F0 index=$IR protect=$PR $(date '+%T')"
  python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$MASKED" \
    --output "$WORK/var_${TAG}.raw.wav" --f0-method "$F0" --index-rate "$IR" --protect "$PR" --format wav --overwrite 2>&1 | tail -1
  python3 $KB/voice/apply_mask.py "$WORK/var_${TAG}.raw.wav" "$MASK" "$FT/vocals.wav" "$WORK/var_${TAG}.wav"
  ffmpeg -v error -y -i "$WORK/var_${TAG}.wav" -af "highpass=f=85,equalizer=f=400:t=q:w=1.0:g=-1.5,equalizer=f=3500:t=q:w=1.5:g=2.5,equalizer=f=8000:t=q:w=2:g=1.5,alimiter=limit=0.95" -ar 48000 -ac 2 "$WORK/var_${TAG}.eq.wav"
  python3 $KB/voice/calibrate_vocal.py "$WORK/var_${TAG}.eq.wav" "$MASK" 0.18 "$WORK/var_${TAG}.cal.wav"
  ffmpeg -v error -y -i "$WORK/var_${TAG}.cal.wav" -i "$FT/no_vocals.wav" -filter_complex \
    "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0" -c:a pcm_s16le "$WORK/var_${TAG}.mix.wav"
  local L=$(measure_lufs "$WORK/var_${TAG}.mix.wav")
  local G=$(python3 -c "print(round(-13.5 - (${L}), 2))")
  ffmpeg -v error -y -i "$WORK/var_${TAG}.mix.wav" -af "volume=${G}dB,alimiter=limit=0.95" -c:a aac -b:a 256k "$WORK/cover_var_${TAG}.m4a"
  ffmpeg -v error -y -i "$(ls $KB/voice/target/*.mp4 | head -1)" -i "$WORK/cover_var_${TAG}.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$KB/voice/cover/cover_var_${TAG}.mp4"
  echo "   完成 cover_var_${TAG}.mp4"
}

# run A rmvpe 0.75 0.33  (已完成)
run B pm 0.50 0.50
run C pm 0.90 0.25
run D rmvpe 0.60 0.45
echo VARIANTS_DONE