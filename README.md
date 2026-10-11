# 李文亚知识库（Li Wenya Knowledge Base）

> 对一个中国互联网亚文化现象（民间科学爱好者「李文亚」，网称「李文亚教授 / 文亚宇宙」）的**可溯源多模态归档与知识化**项目。
> 全部内容来源于公开视频与公开 wiki 页面，仅用于**个人资料归档、亚文化研究与社会现象观察**。



## 大文件下载（GitHub Release）

仓库装不下的大件（电影成片、离线包、逐轮翻唱、RVC 权重）放在 Release 里：

- 发布页：https://github.com/bdydgz114514/liwenya-kb/releases/tag/film-v1

| 资产 | 说明 |
|---|---|
| `李文亚传_电影_1080p.mp4` | AI 纪录电影成片（1080p / 硬字幕 / 约 72 分钟） |
| `电影_480p_第1-11章.mp4` 等三段 | 供在线观看的 480p 版本 |
| `李文亚Wiki_离线版.zip` | 完整离线站点（含长篇传记、年表、知识库数据、电影页） |
| `李文亚Wiki_单文件版.html` | 单文件版（双击即看） |
| `李文亚传_定本.md` / `.txt` | 传记定本全文（30 章约 8.6 万字） |
| `liwenya_e250/e300/e350/e375/e400/e425/e450.pth` | RVC v2 各里程碑声音模型（约 55 MB/个） |
| `20b/21b/22b/23b_cover_*.mp4` | 各里程碑翻唱（原画面版，便于试听） |
| `liwenya_kb.sqlite` / `faiss.index` / `embeddings.npy` / `transcripts.zip` / `cards.zip` | 知识库数据（站点 /kb 页也有同样一份） |

## 这是什么

把 1206 个视频（1193 个本地归档 + 13 个 B 站视频，共 170 小时）逐视频「看懂」：

- **听**：Whisper large-v3 转写（VAD 只跑语音段，速度快一倍），得到带时间码的台词；
- **看**：PySceneDetect 场景切分 + Qwen3-VL-8B 逐关键帧结构化描述（场景/人物/动作/**画面文字**/风格/情绪）；
- **读**：OCR 补画面内文字，并与归档自带的 1108 份字幕交叉对齐；
- **融合**：按场景合成「场景卡」（台词 + 画面 + 文字 + 人物），再由本地 Qwen3-8B 生成视频级摘要、人物/理论/梗标签；
- **入库**：SQLite(FTS5 全文) + FAISS(语义) + 实体关系图，所有结论都带 `video_id + 时间码` 可回溯。

### 另收录一部书稿

《人民科学原理》三卷全（人民物理学 / 人民化学 / 人民生物学，原书 236 页、43 章、约 13.6 万字）
录为 `doc.kind='book'`，doc_id `book:people-science-principles`。

它**不是视频转写**，引用口径不同：书稿用「书中称」「《人民科学原理》第 N 章（原书 p…）」，
视频用「视频中称 + 时间码」，两者不要混用。检索结果里书稿显示**页码**（`p127–130`），
视频显示时间码（`@00:00-07:57`）。详细抽取方法与隐私口径见 `docs/KB_README.md`。

## 目录结构

```text
docs/
  DESIGN.md        总体方案（五层流水线 L0–L7）
  LESSONS.md       工程经验教训（28 条，含踩坑与决策依据）
  VOICE_RVC.md     「AI 李文亚」RVC v2 声音克隆全流程与客观评测
scripts/
  pipeline.py      资产索引 + Whisper 全量转写（含 VAD 跳过、幻觉过滤）
  vision.py        场景切分 + 关键帧 + Qwen3-VL 画面理解 + OCR
  fuse.py          场景卡融合 + 视频级摘要（本地 Qwen3-8B）
  kb.py            知识库构建 / 向量 / 检索 / 站点数据导出（含隐私过滤）
kb/
  liwenya_kb.sqlite  SQLite 知识库（entity/relation/doc/chunk + FTS5）
  export/*.json      站点数据契约（videos/people/theories/events/glossary/graph/bilibili/site）
data/
  transcripts/*.jsonl  逐视频转写（时间码 + 文本）
  cards/*.json         场景卡与视频摘要
  book.json            《人民科学原理》三卷全（结构化书稿，43 章）
sources/
  wiki_refs/           参考 wiki 采集原文、结构化实体与来源日志
voice/
  *.py / *.sh          RVC 数据构建、训练、里程碑翻唱脚本
  cover/*.m4a          里程碑试听片段（不含训练数据与完整模型）
```

## 数据字典（核心表）

| 表 | 含义 |
|---|---|
| `asset` | 视频资产：路径、系列、时长、编码、处理进度标记 |
| `transcript` | 转写片段：asset_id、起止秒、文本 |
| `scene` | 场景：asset_id、序号、起止秒、关键帧路径 |
| `entity` | 实体：人物/理论/术语/梗，含别名与出处 |
| `relation` | 实体关系：批判、采访、扮演、衍生……含证据与来源 |
| `doc` | 文档：视频（`video`）、事件（`event`）、B 站条目（`bilibili`）、书稿（`book`） |
| `chunk` + `chunk_fts` | 检索单元与全文索引（FTS5）。`kind='book'` 时 `t0/t1` 表示**页码**而非秒 |

## 快速使用

```bash
# 全文检索
python scripts/kb.py query --text "黑体生物"
# 重建知识库与站点数据
python scripts/kb.py build && python scripts/kb.py export --thumbs
```

## 隐私与合规

- 本项目**主动剔除**住址、健康、证件、电话等私密信息（`kb.py` 内置正则过滤，落库前替换为「已隐去」）；
  **一处刻意例外**：书稿不套用「健康词」规则——实测命中 22 处全部是书的论证对象（「你不需要手术」是节标题、「癌基因」是批判对象），套用会损毁正文；书稿只用另外三条，命中 0 处。理由见 `docs/KB_README.md`；
- 参考站点自身声明内容为社群虚构创作、不对任何主张作真实性背书，本项目沿袭该口径；
- 所有引用均标注来源 URL；B 站视频版权归原作者，仓库仅保留元数据与链接；
- 归档内容涉及真实人物，请勿用于骚扰、冒充或误导性传播。

## 许可

代码 MIT；文档与结构化数据 CC BY-NC-SA 4.0；原始视频与音频不随本仓库分发。