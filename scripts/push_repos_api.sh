#!/bin/bash
# 用 API 推送两个源码仓库（差额小，很快）
set -u
S=/root/dsh/liwenya-kb/scripts/api_push.py
echo "[$(date +%T)] 推送站点源码仓库"
python3 -u $S /root/dsh/liwenya-wiki bdydgz114514/liwenya-wiki main "站点源码：知识库入口页 + 视频播放器 + 缩略图修复" 2>&1 | tail -4
echo "[$(date +%T)] 推送知识库仓库"
python3 -u $S /root/dsh/liwenya-kb-repo bdydgz114514/liwenya-kb main "知识库：年表 38 条、传记与电影数据、文档更新" 2>&1 | tail -4
echo "[$(date +%T)] 完成"
echo REPOS_API_DONE