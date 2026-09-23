# AI 李文亚：RVC v2 声音克隆全流程实录

## 目标
从 1193 个原始视频中提取**李文亚本人**的干净语音，训练 RVC v2 音色模型，并每到一个训练里程碑就用翻唱 BV1ENmhBTE5M（《如果把黄轩演唱的摇滚换成〈燕无歇〉摇滚版……》）做效果验证。

## 流水线

```text
1193 视频
  └─ L1 语音扫描  voice/scan_voice.py      Silero VAD 切分 + ECAPA 说话人向量 + 质量指标
       └─ 87,630 段（1204 个视频）
  └─ L2 说话人筛选 voice/select_voice.py   16 簇聚类 → 以最大簇质心为「李文亚音色」参考
       └─ 相似度阈值 0.66 + 时长/响度/过零率过滤
       └─ 33,451 段 / 41.6 小时候选 → 按预算取 1,604 段 / 2.0 小时（覆盖 657 个视频）
  └─ L3 数据集导出 voice/export_dataset.py 48kHz 单声道 + 75Hz 高通 + FFT 降噪 + 动态响度归一
       └─ 666 MB 训练集
  └─ RVC v2 训练（conda env: rvc, torch 2.14+cu130）
       ├─ preprocess  → 2,528 个 3.7s 切片
       ├─ RMVPE f0 + HuBERT(ContentVec) 特征（崩溃隔离式提取，2,516 个有效）
       ├─ train.py -v v2 -sr 48k -f0 1 -bs 8 -te 150 -se 25（44 秒/轮，约 1.8 小时）
       └─ train_index.py → added_IVF256_Flat_nprobe_1_liwenya_v2.index
  └─ 里程碑翻唱 voice/make_cover.sh        demucs 分离人声 → RVC 转换 → 与伴奏混音 → 回贴视频
```

## 关键工程决策（含踩坑）

| 问题 | 现象 | 解决 |
|---|---|---|
| 旧 torch 在新 GPU | torch 2.1.2+cu121 跑 RMVPE 报 `CUDA error: an illegal memory access`，成功率 3% | 换 torch 2.14+cu130（Blackwell 原生支持） |
| 特征提取易崩 | 单个坏文件让整个进程 sticky error，后续全失败 | 分轮重启 + 坏文件隔离（`run_features.py`），成功率 95% |
| RVC 脚本导入 | `python train/train.py` 触发 `train` 包名冲突（circular import） | 一律用 `python -m train.train` + `PYTHONPATH=<repo>` |
| 缺 assets | rmvpe.pt / pretrained_v2 / hubert_base 缺失导致各种 FileNotFoundError | 统一放置在 `assets/`；HuBERT 用 Transformers 版 ContentVec + 补 `preprocessor_config.json` |
| 静音样本无法提 f0 | mute 样本全零音高被跳过 | filelist 不写 mute（本仓库训练不依赖） |
| 小模型导出失败 | epoch 25 存档时 `assets/weights` 目录不存在 | 预先 `mkdir -p assets/weights` |
| 推理缺索引 | `rvc-cli: No usable added index` | 先跑 `train_index.py` 生成 faiss 索引 |

## 效果验证（客观指标）

以训练集说话人质心为参考，计算翻唱人声的 ECAPA 余弦相似度：

| 里程碑 | 相似度 | 备注 |
|---|---|---|
| 原唱（黄轩摇滚版） | 0.180 | 基线 |
| e25 | 0.725 | 歌词尚模糊 |
| e50 | 0.799 | 歌词明显变清晰 |
| e75 | 0.750 | |
| e100 | 0.799 | |
| e125 | 0.783 | |
| **e150（最终）** | **0.794** | 李文亚本人语音段的相似度区间为 0.65–0.74 |

结论：约 epoch 50 后音色已稳定进入目标音色空间，后续提升主要体现在发音清晰度与稳定性上。

## 复现命令

```bash
# 1) 扫描（CPU，6 进程约 1 小时）
python voice/scan_voice.py --shard 0/6   # 0..5
# 2) 聚类与筛选
python voice/select_voice.py cluster --k 16
python voice/select_voice.py select --hours 2 --min-sim 0.66
# 3) 导出数据集
python voice/export_dataset.py --out voice/rvc_dataset/liwenya
# 4) 训练（RVC 环境）
bash voice/train_rvc.sh          # 或分步：preprocess → extract_f0 → extract_hubert → train
# 5) 里程碑翻唱
bash voice/make_cover.sh e150 <模型.pth> <索引.index>
```

## 合规说明
仅用于个人研究/技术验证；声音模型与翻唱产物不随知识库公开发布（仓库只保留脚本、配置与少量试听片段），请勿用于冒充本人或误导性传播。