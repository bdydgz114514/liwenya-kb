# MiniMax H3 电影生产线（本机可用，2026-09-23 实测）

> 目标：用**本地部署的 MiniMax H3**（ComfyUI）生成有真运动、真光影、带同期声的电影镜头，替代此前「静帧 + 推拉」的做法。

## 一、环境与模型（都在机器上，新实例同镜像开箱即用）

| 项 | 位置 |
|---|---|
| ComfyUI | `/root/ComfyUI`（2026-08 版，自带 `comfy_extras/nodes_minimax_h3.py`） |
| H3 主模型 | `/.autodl-model/.../MiniMax-H3/diffusion_models/`：`minimax_h3_ref2va_bf16.safetensors`（高质量）、`minimax_h3_ref2va_int8_convrot.safetensors`（快） |
| 文本编码 | `models/LLM/qwen3vl_32b_minimax_h3_int8_convrot.safetensors`（Qwen3-VL-32B，H3 专用） |
| VAE | `minimax_h3_video_vae_fp16` / `minimax_h3_audio_vae_fp32` |
| 加速与放大 | `minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16`（4 步 LoRA）、`minimax_h3_latent_upscaler_3d_fp16`（潜空间二次放大到 1376×768） |
| 工作流 | `ComfyUI/user/default/workflows/视频/0005--MiniMax H3-潜空间二次放大--参考生成视频--新.json`（137 节点） |

启动：`cd /root/ComfyUI && python3 main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch`

## 二、自动化方式（无需手动点界面）

用 Playwright 驱动 ComfyUI 前端：加载工作流 → 改节点参数 → 入队。

关键节点编号（改这几个就够）：

| 节点 | 作用 | 改什么 |
|---|---|---|
| #127 | 提示词（PrimitiveStringMultiline） | H3 的结构化提示词：`subject_definitions / summary / retention_analysis`，用 `<Subject 1>`、`<Picture 1>` 指代参考图 |
| #142/#132/#146/#144/#140/#131 | LoadImage | 换成参考图（放 `ComfyUI/input/`，如 `wenya_ref_0.jpg`） |
| **#149/#150** | **LoadAudio（参考音频）** | **换成他自己的原声（如 `wenya_voice_01.wav`）——这一步决定生成出来的嗓音像不像他** |
| #39 | UNETLoader | `minimax_h3_ref2va_bf16.safetensors`（高质量）或 int8（快） |
| #56 | LoraLoaderModelOnly（4 步加速） | 高质量档调到 0.30–0.50，速度档留 0.75 |
| #69 | BasicScheduler（步数） | 8（快）→ 14（高质量） |
| #124 | VHS_VideoCombine | 输出 mp4（24fps，带音轨） |

脚本：`movie/tools/h3_queue.js`（排队）、`movie/tools/h3_harvest.sh`（收割到下载目录）。

## 三、实测速度与整片时间估算

单支镜头 = 15 秒 / 24fps / 1376×768 / **带音轨**（H3 是音视频联合生成）。

| 档位 | 单支耗时（实测/推算） | 60 分钟正片（240 支） | 4 卡并行 | 8 卡并行 |
|---|---|---|---|---|
| int8 + 4 步（画面已像电影） | **5.6–6.7 分钟**（实测） | **≈ 24 h** | 6 h | 3 h |
| bf16 + 8 步（推荐平衡） | ≈ 10–12 分钟 | ≈ 44 h | 11 h | 5.5 h |
| bf16 + 14 步（极限高质量） | ≈ 17–20 分钟 | ≈ 72 h | 18 h | 9 h |

换算：int8 档约 **24 秒算力/秒成片**，bf16 14 步档约 **70 秒算力/秒成片**。
配音（TTS→RVC e450 或他的原声切片）240 条 ≈ 3–5 h，可与生成并行；剪辑混音 ≈ 2 h；返工余量 +20%。

**省钱要点：模型在公共模型盘，不占实例磁盘也不需重新下载；多卡并行是唯一把 3 天压到 1 天的办法。**

## 四、声音：三步走

1. **首选**：把**他自己的原声**接进 #149/#150 当参考音频，让 H3 直接生成他的嗓音（ref2va 的设计用途）；
2. **兜底**：H3 只出画面与同期声，旁白用 `voice/dub_line.sh`（edge-tts → RVC e450 → 后期），相似度实测 0.59；
3. **最保真**：整片旁白全部用归档里他自己的原声切片（170 小时转写可检索），RVC 只用于补不出来的句子。

## 五、素材与脚本

- 参考图：`/root/ComfyUI/input/wenya_ref_*.jpg`（从归档抽帧，含他本人正脸）
- 参考音频：`/root/ComfyUI/input/wenya_voice_*.wav`（从归档剪的他的原声）
- 旁白配音：`/root/dsh/liwenya-kb/voice/dub_line.sh "文本" TAG`
- 成品收割：下载目录 `/root/output_videos/sample_h3_*.mp4`

## 六、坑

- `curl --data-binary @大文件` 会 OOM（>1 GB），上传要用 `-T`；
- 磁盘低于 15 GB 时 `disk_guard.sh` 会清理，注意别把 HF 未完成下载和训练预处理目录删掉（RVC 训练启动时会 stat `0_gt_wavs`）；
- 这台机器 `github.com:443` 时通时断，git push 失败要改走 API 或 release（`uploads.github.com`）。
