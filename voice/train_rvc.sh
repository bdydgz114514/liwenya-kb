#!/bin/bash
# RVC v2 训练驱动：预处理 -> f0 -> HuBERT 特征 -> 训练 -> 索引
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate rvc
cd /root/dsh/rvc/webui
export PYTHONPATH=/root/dsh/rvc/webui
EXP=${EXP:-liwenya}
DATASET=${DATASET:-/root/dsh/liwenya-kb/voice/rvc_dataset/liwenya}
SR=${SR:-48000}
EPOCHS=${EPOCHS:-150}
SAVE_EVERY=${SAVE_EVERY:-25}
BATCH=${BATCH:-8}
NP=${NP:-8}
LOGDIR=/root/dsh/rvc/webui/logs/$EXP
mkdir -p "$LOGDIR"
echo "== [1/5] 数据切分 ($(date '+%T'))"
python train/preprocess.py "$DATASET" $SR $NP "$LOGDIR" False 3.7 2>&1 | tail -5
ls "$LOGDIR"
echo "== [2/5] F0 提取 ($(date '+%T'))"
python train/dataset/extract_f0.py cuda 1 0 0 "$LOGDIR" true 2>&1 | tail -5
echo "== [3/5] HuBERT 特征 ($(date '+%T'))"
python train/dataset/extract_hubert_feature.py cuda 1 0 0 "$LOGDIR" v2 true 2>&1 | tail -5
echo "== [4/5] 训练 ($(date '+%T'))"
RVC_CUDA_GRAPH=0 python train/train.py -e "$EXP" -sr 48k -f0 1 -bs $BATCH -g 0 -te $EPOCHS -se $SAVE_EVERY -pg pretrained_v2/f0G48k.pth -pd pretrained_v2/f0D48k.pth -l 1 -c 0 -sw 1 -v v2
echo "== [5/5] 索引 ($(date '+%T'))"
python train/train_index.py "$EXP" v2 "logs/$EXP" 8 auto 2>&1 | tail -3
echo RVC_TRAIN_DONE