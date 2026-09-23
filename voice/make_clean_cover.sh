#!/bin/bash
# 干净版翻唱流水线（音频重做）
# 1) htdemucs_ft 高质量分离  2) 伴奏二次分离去残留人声  3) 人声清理
# 4) RVC 转换  5) 转换后再清理并与原唱响度对齐  6) 混音 + 限制器 + 响度归一  7) 合成到换脸视频
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
WORK=/root/dsh/liwenya-kb/voice/clean
FT=$(ls -d /root/dsh/liwenya-kb/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-clean}
MODEL=${2:-/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth}
INDEX=${3:-/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index}
VIDEO=${4:-/root/dsh/liwenya-kb/voice/faceswap/faceswap_full.mp4}
OUT=/root/dsh/liwenya-kb/voice/faceswap
mkdir -p "$WORK"

echo "== [1/6] 伴奏二次分离（去除残留人声）$(date '+%T')"
if [ ! -f "$WORK/pass2/htdemucs_ft/$(basename "$FT")/no_vocals.wav" ]; then
  python -m demucs.separate -n htdemucs_ft --two-stems=vocals -d cuda -o "$WORK/pass2" "$FT/no_vocals.wav" >/dev/null 2>&1 || true
fi
INST2=$(ls "$WORK"/pass2/htdemucs_ft/*/no_vocals.wav 2>/dev/null | head -1)
[ -z "$INST2" ] && INST2="$FT/no_vocals.wav"
echo "    伴奏: $INST2"

echo "== [2/6] 人声清理（高通/降噪/去齿音/轻压缩）$(date '+%T')"
ffmpeg -v error -y -i "$FT/vocals.wav" -af "highpass=f=85,afftdn=nf=-28,deesser=i=0.4,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=180" -ar 48000 -ac 1 "$WORK/vocal_clean.wav"

echo "== [3/6] RVC 转换 $(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_clean.wav" \
  --output "$WORK/vocal_ai_raw.wav" --f0-method rmvpe --index-rate 0.80 --protect 0.33 --format wav --overwrite 2>&1 | tail -2

echo "== [4/6] 转换后清理 + 与原唱响度对齐 $(date '+%T')"
ORIG_LUFS=$(ffmpeg -v error -i "$FT/vocals.wav" -af loudnorm=print_format=json -f null - 2>&1 | python3 -c "import sys,json,re; t=sys.stdin.read(); m=re.search(r'\{[^{}]*input_i[^{}]*\}', t, re.S); print(json.loads(m.group(0))['input_i'] if m else '-20')")
echo "    原唱人声响度: ${ORIG_LUFS} LUFS"
ffmpeg -v error -y -i "$WORK/vocal_ai_raw.wav" -af "highpass=f=85,afftdn=nf=-30,acompressor=threshold=-16dB:ratio=2:attack=10:release=200,loudnorm=I=${ORIG_LUFS}:TP=-1.5:LRA=11" -ar 48000 -ac 2 "$WORK/vocal_ai_clean.wav"

echo "== [5/6] 混音 + 限制 + 母带响度 $(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_clean.wav" -i "$INST2" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.0:LRA=11" \
  -c:a aac -b:a 256k "$WORK/cover_${TAG}.m4a"

echo "== [6/6] 合成到换脸视频 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_${TAG}.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_${TAG}.mp4"
ls -la "$OUT/ai_liwenya_${TAG}.mp4" "$WORK/cover_${TAG}.m4a"
echo CLEAN_COVER_DONE