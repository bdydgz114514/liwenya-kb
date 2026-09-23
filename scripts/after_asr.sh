#!/bin/bash
# 流水线接力：ASR 结束 -> VLM 全量 -> 视频摘要 -> 知识库重建与导出
cd /root/dsh/liwenya-kb
export HF_ENDPOINT=https://hf-mirror.com
echo "[chain] 等待 ASR 结束 $(date '+%T')"
while pgrep -f "pipeline.py asr" > /dev/null; do sleep 60; done
echo "[chain] ASR 结束，开始 VLM $(date '+%T')"
python scripts/vision.py vision --limit 2000 --batch 6 > logs/vision_batch2.log 2>&1
echo "[chain] VLM 结束，开始视频摘要 $(date '+%T')"
python scripts/fuse.py summarize > logs/summarize.log 2>&1
echo "[chain] 摘要结束，重建知识库 $(date '+%T')"
python scripts/kb.py build > logs/kb_build.log 2>&1
python scripts/kb.py export --thumbs > logs/kb_export.log 2>&1
echo "[chain] 全部完成 $(date '+%T')"
echo CHAIN_DONE