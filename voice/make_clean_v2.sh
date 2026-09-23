#!/bin/bash
# 干净版 v2：门限降噪 + 去齿音 + 亮度补偿 + 限制器；可切换 RVC 参数做多版本
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
export PYTHONPATH=/root/dsh/rvc/webui
WORK=/root/dsh/liwenya-kb/voice/clean
FT=$(ls -d /root/dsh/liwenya-kb/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v2}
IR=${2:-0.90}
PROTECT=${3:-0.40}
MODEL=${4:-/root/dsh/rvc/webui/assets/weights/liwenya_e150.pth}
INDEX=${5:-/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index}
VIDEO=${6:-/root/dsh/liwenya-kb/voice/faceswap/faceswap_full.mp4}
OUT=/root/dsh/liwenya-kb/voice/faceswap
mkdir -p "$WORK"

echo "== [1/4] RVC 转换 (index-rate=$IR protect=$PROTECT) $(date '+%T')"
python -m infer.cli --model "$MODEL" --index "$INDEX" --input "$WORK/vocal_clean.wav" \
  --output "$WORK/vocal_ai_$TAG.raw.wav" --f0-method rmvpe --index-rate "$IR" --protect "$PROTECT" --format wav --overwrite 2>&1 | tail -1

echo "== [2/4] 干净化处理 $(date '+%T')"
ORIG_LUFS=$(ffmpeg -v error -i "$FT/vocals.wav" -af loudnorm=print_format=json -f null - 2>&1 | python3 -c "import sys,json,re; t=sys.stdin.read(); m=re.search(r'\{[^{}]*input_i[^{}]*\}', t, re.S); print(json.loads(m.group(0))['input_i'] if m else '-20')")
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.raw.wav" -af \
  "highpass=f=90,afftdn=nr=18:nf=-50:tn=1,agate=threshold=0.004:ratio=6:attack=5:release=140,deesser=i=0.5,equalizer=f=320:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.5:g=2.5,treble=g=2.5:f=8000,acompressor=threshold=-16dB:ratio=2:attack=10:release=200,alimiter=limit=0.9,loudnorm=I=${ORIG_LUFS}:TP=-1.5:LRA=11" \
  -ar 48000 -ac 2 "$WORK/vocal_ai_$TAG.clean.wav"

echo "== [3/4] 混音与母带 $(date '+%T')"
INST="$FT/no_vocals.wav"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.clean.wav" -i "$INST" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.0:LRA=11" \
  -c:a aac -b:a 256k "$WORK/cover_$TAG.m4a"

echo "== [4/4] 合成视频 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_$TAG.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_$TAG.mp4"
ls -la "$OUT/ai_liwenya_$TAG.mp4"
echo CLEAN_V2_DONE $TAG