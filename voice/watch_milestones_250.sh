#!/bin/bash
# 里程碑守望（第二段：175/200/225/250）——存档后自动提取模型并出翻唱
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
cd /root/dsh/rvc/webui
export PYTHONPATH=/root/dsh/rvc/webui
LOG=/root/dsh/liwenya-kb/voice/train_rvc_250.log
WORK=/root/dsh/liwenya-kb/voice/cover
INDEX=/root/dsh/rvc/webui/logs/liwenya/added_IVF256_Flat_nprobe_1_liwenya_v2.index
for m in 175 200 225 250; do
  while true; do
    ep=$(grep -oE 'Epoch: [0-9]+' "$LOG" 2>/dev/null | tail -1 | grep -oE '[0-9]+')
    [ -z "$ep" ] && ep=150
    [ "$ep" -ge "$m" ] && break
    sleep 30
  done
  s1=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0); sleep 8; s2=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0)
  while [ "$s1" != "$s2" ] || [ "$s2" = "0" ]; do s1=$s2; sleep 8; s2=$(stat -c %s logs/liwenya/G_2333333.pth 2>/dev/null || echo 0); done
  echo "[milestone250] epoch $m 存档完成，提取模型 $(date '+%T')"
  python extract_ckpt.py "$m" logs/liwenya/G_2333333.pth 2>&1 | tail -2
  if [ -f "assets/weights/liwenya_e${m}.pth" ]; then
    bash /root/dsh/liwenya-kb/voice/make_cover.sh "e${m}" "/root/dsh/rvc/webui/assets/weights/liwenya_e${m}.pth" "$INDEX" 2>&1 | tail -3
  fi
done
echo MILESTONES_250_DONE