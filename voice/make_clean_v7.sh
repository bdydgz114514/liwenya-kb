#!/bin/bash
# v7：按“正确流程”重做 —— 分离人声/伴奏 → 只在人声段做 RVC → 掩码去噪 → 与伴奏混音 → 与静音换脸视频合成
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
KB=/root/dsh/liwenya-kb
WORK=$KB/voice/clean
FT=$(ls -d $KB/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v7}
VIDEO=${2:-$KB/voice/faceswap/faceswap_full.mp4}   # 该文件本身无音轨（静音画面）
OUT=$KB/voice/faceswap
MODEL=/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index

echo "== [1/6] 人声活动掩码 $(date '+%T')"
python3 $KB/voice/vocal_mask.py "$FT/vocals.wav" "$WORK/vocal_${TAG}_masked.wav" "$WORK/vocal_${TAG}_mask.npy"

echo "== [2/6] RVC 只转换人声段 $(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_${TAG}_masked.wav" \
  --output "$WORK/vocal_ai_${TAG}.raw.wav" --f0-method pm --index-rate 0.75 --protect 0.33 --format wav --overwrite 2>&1 | tail -1

echo "== [3/6] 掩码去噪 + 响度对齐 $(date '+%T')"
python3 $KB/voice/apply_mask.py "$WORK/vocal_ai_${TAG}.raw.wav" "$WORK/vocal_${TAG}_mask.npy" "$FT/vocals.wav" "$WORK/vocal_ai_${TAG}.wav"

echo "== [4/6] 轻处理（不加压缩器，避免抬升底噪）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_${TAG}.wav" -af "highpass=f=85,equalizer=f=3500:t=q:w=1.5:g=2,alimiter=limit=0.95" -ar 48000 -ac 2 "$WORK/vocal_ai_${TAG}.final.wav"

echo "== [5/6] 与伴奏混音（人声 1.0 / 伴奏 1.0）$(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_${TAG}.final.wav" -i "$FT/no_vocals.wav" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.97,loudnorm=I=-13.5:TP=-1.0:LRA=16" \
  -c:a aac -b:a 256k "$WORK/cover_${TAG}.m4a"

echo "== [6/6] 与静音换脸画面合成 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_${TAG}.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_${TAG}.mp4"
ls -la "$OUT/ai_liwenya_${TAG}.mp4"
echo V7_DONE