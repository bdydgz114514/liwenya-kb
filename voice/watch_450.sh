#!/bin/bash
# 250→450 续训的里程碑守望：每 25 轮存档后自动出翻唱（用当前最佳流程）
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
cd /root/dsh/rvc/webui
export PYTHONPATH=/root/dsh/rvc/webui
LOG=/root/dsh/liwenya-kb/voice/train_rvc_450.log
KB=/root/dsh/liwenya-kb
MODEL_DIR=/root/dsh/rvc/webui/assets/weights
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
for m in 275 300 325 350 375 400 425 450; do
  while true; do
    ep=$(grep -oE 'Epoch: [0-9]+' "$LOG" 2>/dev/null | tail -1 | grep -oE '[0-9]+')
    [ -z "$ep" ] && ep=250
    [ "$ep" -ge "$m" ] && break
    sleep 45
  done
  s1=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0); sleep 10; s2=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0)
  while [ "$s1" != "$s2" ] || [ "$s2" = "0" ]; do s1=$s2; sleep 10; s2=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0); done
  echo "[m450] epoch $m 存档完成，开始出翻唱 $(date '+%T')"
  python extract_ckpt.py "$m" logs/liwenya/G_2333333.pth 2>&1 | tail -1
  if [ -f "$MODEL_DIR/liwenya_e${m}.pth" ]; then
    bash $KB/voice/make_clean_v9.sh "r${m}" "$KB/voice/faceswap/faceswap_full.mp4" "$MODEL_DIR/liwenya_e${m}.pth" -13.5 0.18 2>&1 | tail -2
    cp -f "$KB/voice/faceswap/ai_liwenya_r${m}.mp4" "$KB/voice/cover/cover_e${m}_clean.mp4" 2>/dev/null || true
  fi
done
echo MILESTONES_450_DONE