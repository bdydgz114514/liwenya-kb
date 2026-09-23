#!/bin/bash
# 磁盘守卫：每 15 分钟检查一次，低于阈值时清理「可安全再生」的中间产物
# 安全清单：RVC 预处理中间产物、/tmp 大文件、HF 未完成下载、voice/clean 旧标签、重复大文件硬链接
set -u
LOG=/root/dsh/liwenya-kb/logs/disk_guard.log
WARN=15   # GB：低于此值开始清理
CRIT=8    # GB：低于此值追加清理

free_gb(){ df -BG --output=avail / | tail -1 | tr -dc '0-9'; }
log(){ echo "[$(date '+%m-%d %H:%M')] free=$(free_gb)GB $*" >> "$LOG"; }

mkdir -p "$(dirname "$LOG")"
log "守卫启动"

while true; do
  f=$(free_gb)
  if [ "$f" -lt "$WARN" ]; then
    log "低于预警线，开始清理"
    # 1) RVC 预处理中间产物（train.py 不读）
    rm -rf /root/dsh/rvc/webui/logs/liwenya/0_gt_wavs /root/dsh/rvc/webui/logs/liwenya/1_16k_wavs 2>/dev/null
    # 2) /tmp 大文件与打包临时目录
    find /tmp -maxdepth 1 -type f -size +20M -mmin +30 -delete 2>/dev/null
    rm -rf /tmp/pack.* /tmp/hf_* 2>/dev/null
    # 3) HuggingFace 未完成下载
    find /root -path "*/.cache/huggingface/download/*" -name "*.incomplete" -mmin +30 -delete 2>/dev/null
    # 4) voice/clean 只保留最新标签
    newest=$(ls -t /root/dsh/liwenya-kb/voice/clean 2>/dev/null | head -1 | grep -oE "(r|v)[0-9]+" | head -1)
    if [ -n "$newest" ]; then
      find /root/dsh/liwenya-kb/voice/clean -type f ! -name "*${newest}*" -delete 2>/dev/null
    fi
    # 5) 重复大文件改硬链接
    python3 /root/dsh/liwenya-kb/scripts/dedupe_hardlink.py >/dev/null 2>&1
    log "清理完成 free=$(free_gb)GB"
  fi
  if [ "$f" -lt "$CRIT" ]; then
    log "低于紧急线：清理旧翻唱与旧离线包"
    # 旧里程碑翻唱只保留最新两个（下载目录里的 *_换脸版.mp4，工作目录有硬链接）
    ls -t /root/output_videos/*换脸版.mp4 2>/dev/null | tail -n +3 | while read -r f2; do rm -f "$f2"; done
    ls -t /root/output_videos/2*_cover_*.mp4 2>/dev/null | tail -n +4 | while read -r f2; do rm -f "$f2"; done
    log "紧急清理完成 free=$(free_gb)GB"
  fi
  sleep 900
done