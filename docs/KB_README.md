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

另收录**一部书稿**：《人民科学原理》三卷全（`doc.kind='book'`）。它不是视频转写，来源与引用口径都不同，见下节。

## 书稿：《人民科学原理》三卷全

| 项 | 值 |
|---|---|
| doc_id | `book:people-science-principles` |
| kind | `book` |
| 作者 / 卷数 | 李文亚 / 3 卷（人民物理学、人民化学、人民生物学） |
| 规模 | 原书 236 页，43 章，约 13.6 万字 |
| 数据文件 | `data/book.json`（`meta.volumes` 分卷，`chapters[].text` 正文，`chapters[].pages` 原书页码） |
| 原始摘录 | `sources/05_book_人民科学原理三卷_全文.txt`、`05_book_逐页原始抽取.jsonl`、`05_book_抽取与结构报告.txt` |

**抽取方法**（该 PDF 的文字层每个汉字单独一行，是 PDFium 导出的）：

1. 逐页拼接还原（逐页结果留在 `sources/05_book_逐页原始抽取.jsonl`，可复核）
2. 章边界取自**正文**——章首一律在页首，`第N章` / `第X章` 两种写法都可正则识别
3. 章标题取自**目录**——正文里标题与正文之间没有分隔符，无法可靠切分；
   两者按卷内序号对齐，实测三卷章数 14/15/14 与目录完全吻合
4. 原书编号有个别错误（第二卷第三篇把第 3–6 章又编成第 6–9 章），**如实保留 `srcNo`**，
   另给顺序号 `seq` / `seqInVol`；引用时以顺序号为准

**检索与引用**：

```bash
node liwenya-search.mjs search "翻滚前进"
# → book:people-science-principles [book] p33–35  人民科学原理（三卷全…）
```

书稿的 `chunk.t0/t1` 存的是**原书页码**（视频条目存的是秒）。`liwenya-search.mjs` 的 `fmtLoc()`
按 `kind` 分流：书显示 `p127–130`，视频显示 `@00:00-07:57`。

引用书稿请写「书中称」或「《人民科学原理》第 N 章（原书 p…）」，
**不要与视频条目的「视频中称」混用**——两者来源性质不同。

**重建时不会丢**：`python scripts/kb.py build` 的第 4 步读 `data/book.json` 重新录入
（`cmd_build_book()`）。

## 目录结构

```text
docs/
  DESIGN.md        总体方案（五层流水线 L0–L7）
  LESSONS.md       工程经验教训（58 条，含踩坑与决策依据；含单文件游戏调试专题）
  H3_FILM_PIPELINE.md  AI 电影流水线（H3）
  DEPLOY_CHINA.md / DEPLOY_EDGEONE.md  国内与边缘节点部署
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
| `doc` | 文档：视频、事件、B 站条目 |
| `chunk` + `chunk_fts` | 检索单元与全文索引（FTS5） |

## 快速使用

```bash
# 全文检索
python scripts/kb.py query --text "黑体生物"
# 重建知识库与站点数据
python scripts/kb.py build && python scripts/kb.py export --thumbs
```

## 隐私与合规

- 本项目**主动剔除**住址、健康、证件、电话等私密信息（`kb.py` 内置正则过滤，落库前替换为「已隐去」）；

  **一处刻意例外**：书稿《人民科学原理》不套用「健康词」规则。实测该规则在本书命中 22 处，
  命中内容**全部是本书的论证对象**——「你不需要手术」是节标题，「癌基因」「糖尿病基因」
  「癌症研究可重复性危机」是批判对象。套用会把正文挖出几十个洞、使小节标题失真，
  而它保护的并非任何第三方的私密健康信息。书稿只用另外三条（住址/手机号/证件号），实测命中 0 处。
  理由同时写在 `kb.py` 的 `cmd_build_book()` 注释里。

- 书稿是**作者的理论著作**，其中的医学、健康论述属虚构理论主张，项目只作归档，
  **不作真实性背书，不构成任何医学建议**；
- 参考站点自身声明内容为社群虚构创作、不对任何主张作真实性背书，本项目沿袭该口径；
- 所有引用均标注来源 URL；B 站视频版权归原作者，仓库仅保留元数据与链接；
- 归档内容涉及真实人物，请勿用于骚扰、冒充或误导性传播。

## 许可

代码 MIT；文档与结构化数据 CC BY-NC-SA 4.0；原始视频与音频不随本仓库分发。