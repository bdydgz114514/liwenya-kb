#!/bin/bash
# v3：RNN 降噪(arnndn) + 门限 + 齿音/箱音处理 + 高频激励(aexciter) + 限制器；再混音出片
set -e
WORK=/root/dsh/liwenya-kb/voice/clean
FT=$(ls -d /root/dsh/liwenya-kb/voice/target/separated_ft/htdemucs_ft/*/ | head -1)
TAG=${1:-v3}
SRC=${2:-$WORK/vocal_ai_v2.clean.wav}
VIDEO=${3:-/root/dsh/liwenya-kb/voice/faceswap/faceswap_full.mp4}
OUT=/root/dsh/liwenya-kb/voice/faceswap
RNNN=/root/dsh/rvc/models/bd.rnnn

ORIG_LUFS=$(ffmpeg -v error -i "$FT/vocals.wav" -af loudnorm=print_format=json -f null - 2>&1 | python3 -c "import sys,json,re; t=sys.stdin.read(); m=re.search(r'\{[^{}]*input_i[^{}]*\}', t, re.S); print(json.loads(m.group(0))['input_i'] if m else '-20')")
echo "原唱人声响度 $ORIG_LUFS LUFS"

echo "== [1/3] 深度清理与提亮 $(date '+%T')"
ffmpeg -v error -y -i "$SRC" -af "arnndn=m=$RNNN,agate=threshold=0.003:ratio=8,equalizer=f=320:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.5:g=2.5,aexciter=amount=2:drive=8:freq=5500:ceil=16000,treble=g=3:f=7000,acompressor=threshold=-16dB:ratio=2:attack=10:release=200,alimiter=limit=0.9,loudnorm=I=${ORIG_LUFS}:TP=-1.5:LRA=11" -ar 48000 -ac 2 "$WORK/vocal_ai_$TAG.wav"

echo "== [2/3] 混音与母带 $(date '+%T')"
ffmpeg -v error -y -i "$WORK/vocal_ai_$TAG.wav" -i "$FT/no_vocals.wav" -filter_complex \
  "[0:a]volume=1.0[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.0:LRA=11" \
  -c:a aac -b:a 256k "$WORK/cover_$TAG.m4a"

echo "== [3/3] 合成视频 $(date '+%T')"
ffmpeg -v error -y -i "$VIDEO" -i "$WORK/cover_$TAG.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest "$OUT/ai_liwenya_$TAG.mp4"
ls -la "$OUT/ai_liwenya_$TAG.mp4" "$WORK/cover_$TAG.m4a"
echo V3_DONE