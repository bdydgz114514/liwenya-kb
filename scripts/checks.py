#!/usr/bin/env python3
# 三次全面检查：1) 数据完整性 2) 内容质量与合规 3) 站点与发布可用性
import glob, json, os, re, sqlite3, subprocess, sys
from pathlib import Path

ROOT = Path("/root/dsh/liwenya-kb")
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import connect, HALLUCINATION_PATTERNS
from kb import kdb, PRIVACY

FAIL = []
WARN = []


def ok(msg):
    print("  ✅ " + msg)


def bad(msg):
    FAIL.append(msg)
    print("  ❌ " + msg)


def warn(msg):
    WARN.append(msg)
    print("  ⚠️  " + msg)


def check1():
    print("\n=== 检查一 · 数据完整性 ===")
    adb = connect()
    total = adb.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    print("  资产总数: %d" % total)
    for label, col in (("ASR", "asr_done"), ("抽帧", "frames_done"), ("VLM", "vision_done")):
        n = adb.execute("SELECT COUNT(*) FROM asset WHERE %s=1" % col).fetchone()[0]
        (ok if n == total else bad)("%s 完成 %d/%d" % (label, n, total))
    cards = len(glob.glob(str(ROOT / "data/cards/[0-9]*.json")))
    sums = len(glob.glob(str(ROOT / "data/cards/*.summary.json")))
    (ok if cards >= total else bad)("场景卡 %d / %d" % (cards, total))
    (ok if sums >= total else warn)("视频摘要 %d / %d" % (sums, total))
    tr = glob.glob(str(ROOT / "data/transcripts/*.jsonl"))
    (ok if len(tr) >= total else bad)("转写文件 %d / %d" % (len(tr), total))
    empty = 0
    for f in tr:
        if os.path.getsize(f) == 0:
            empty += 1
    (ok if empty < total * 0.15 else warn)("空转写 %d 个（无语音或极短）" % empty)
    conn = kdb()
    n_doc = conn.execute("SELECT COUNT(*) FROM doc WHERE kind='video'").fetchone()[0]
    n_chunk = conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
    (ok if n_doc >= total else bad)("知识库视频文档 %d" % n_doc)
    (ok if n_chunk > 10000 else warn)("知识库检索块 %d" % n_chunk)
    idx = ROOT / "kb/faiss.index"
    (ok if idx.exists() else warn)("FAISS 索引 %s" % ("存在" if idx.exists() else "缺失"))
    for name, p in (("站点数据 videos.json", ROOT / "kb/export/videos.json"), ("SQLite", ROOT / "kb/liwenya_kb.sqlite")):
        (ok if Path(p).exists() else bad)("%s 存在" % name)


def check2():
    print("\n=== 检查二 · 内容质量与合规 ===")
    vis = glob.glob(str(ROOT / "data/vision/*.jsonl"))
    good = badj = 0
    for f in vis[:400]:
        for line in open(f, encoding="utf-8"):
            try:
                c = json.loads(line)["caption"]
                json.loads(c)
                good += 1
            except Exception:
                badj += 1
    rate = good / max(good + badj, 1)
    (ok if rate > 0.9 else warn)("VLM 描述 JSON 解析率 %.1f%%（%d/%d）" % (rate * 100, good, good + badj))
    hall = 0
    for f in glob.glob(str(ROOT / "data/transcripts/*.jsonl")):
        for line in open(f, encoding="utf-8"):
            t = json.loads(line).get("text", "")
            if sum(1 for p in HALLUCINATION_PATTERNS if p in t) >= 2:
                hall += 1
    (ok if hall == 0 else bad)("转写中的模板幻觉片段: %d" % hall)
    leaks = []
    for path in [ROOT / "kb/export/videos.json", ROOT / "kb/export/people.json", ROOT / "kb/export/events.json", ROOT / "kb/export/glossary.json"]:
        if not path.exists():
            continue
        txt = path.read_text(encoding="utf-8")
        for pat, rep in PRIVACY:
            for m in pat.finditer(txt):
                leaks.append((path.name, m.group(0)[:30]))
    (ok if not leaks else bad)("隐私扫描: %s" % ("未发现住址/健康/证件信息" if not leaks else str(leaks[:5])))
    tok = []
    for path in glob.glob(str(ROOT / "kb/export/*.json")) + glob.glob(str(ROOT / "docs/*.md")):
        pat = "gh" + "p_[A-Za-z0-9]{30,}|github_" + "pat_[A-Za-z0-9_]{30,}"
        if re.search(pat, open(path, encoding="utf-8", errors="ignore").read()):
            tok.append(path)
    (ok if not tok else bad)("仓库内无 GitHub token: %s" % ("通过" if not tok else tok))
    site = ROOT / "site/src/data"
    if site.exists():
        n = len(json.loads((site / "videos.json").read_text(encoding="utf-8")))
        (ok if n > 0 else bad)("站点视频数据 %d 条" % n)


def check3():
    print("\n=== 检查三 · 站点与发布可用性 ===")
    dist = ROOT / "site/dist"
    html = len(glob.glob(str(dist / "**/*.html"), recursive=True))
    (ok if html > 1000 else bad)("站点构建页面数 %d" % html)
    pf = dist / "pagefind"
    (ok if pf.exists() else warn)("Pagefind 搜索索引 %s" % ("存在" if pf.exists() else "缺失"))
    missing = 0
    for f in glob.glob(str(dist / "**/*.html"), recursive=True)[:200]:
        t = open(f, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r'href="(/[^"#]*)"', t):
            p = m.group(1).split("?")[0]
            if p.startswith("//") or "." in p.split("/")[-1]:
                continue
            rel = p.strip("/")
            cands = [dist / rel, dist / rel / "index.html", dist / (rel + ".html")]
            if not any(c.exists() for c in cands):
                missing += 1
    (ok if missing < 20 else warn)("抽样内部链接失效数 %d" % missing)
    for repo in ("/root/dsh/liwenya-wiki", "/root/dsh/liwenya-kb-repo"):
        (ok if os.path.isdir(repo) else warn)("发布仓库目录 %s %s" % (repo, "存在" if os.path.isdir(repo) else "未构建"))
    print("\n汇总：失败 %d 项，警告 %d 项" % (len(FAIL), len(WARN)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
    return len(FAIL) == 0


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    results = []
    if which in ("all", "1"):
        check1()
    if which in ("all", "2"):
        check2()
    if which in ("all", "3"):
        results.append(check3())
    if which == "all":
        print("\n最终：%s" % ("全部检查通过" if not FAIL else "存在 %d 项失败" % len(FAIL)))