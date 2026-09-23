#!/usr/bin/env python3
# 语音数据集构建 L2：聚类选人（找出李文亚本人音色）+ 质量过滤
# 子命令: cluster | select | sample | stats
import argparse, glob, json, random, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path("/root/dsh/liwenya-kb")
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import connect

VOICE = ROOT / "voice"
SCAN = VOICE / "scan"


def load_segments(limit_files=None):
    segs = []
    files = sorted(glob.glob(str(SCAN / "*.jsonl")))
    if limit_files:
        files = files[:limit_files]
    for fp in files:
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("emb"):
                segs.append(d)
    return segs


def cluster(args):
    from sklearn.cluster import MiniBatchKMeans
    segs = load_segments()
    print("总段数:", len(segs))
    X = np.array([s["emb"] for s in segs], dtype="float32")
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    k = args.k
    km = MiniBatchKMeans(n_clusters=k, batch_size=4096, n_init=5, random_state=0).fit(X)
    labels = km.labels_
    conn = connect()
    series = {r[0]: (r[1] or "") for r in conn.execute("SELECT id, series FROM asset")}
    stats = defaultdict(lambda: {"n": 0, "dur": 0.0, "series": Counter()})
    for s, lb in zip(segs, labels):
        st = stats[int(lb)]
        st["n"] += 1
        st["dur"] += s.get("dur", 0)
        st["series"][series.get(s["aid"], "?")] += 1
    print("%-4s %-8s %-10s %s" % ("簇", "段数", "时长(分)", "主要来源"))
    for lb in sorted(stats, key=lambda x: -stats[x]["n"]):
        st = stats[lb]
        top = "; ".join("%s(%d)" % (a, b) for a, b in st["series"].most_common(3))
        print("%-4d %-8d %-10.1f %s" % (lb, st["n"], st["dur"] / 60, top))
    np.save(VOICE / "labels.npy", labels)
    with open(VOICE / "cluster_meta.json", "w", encoding="utf-8") as f:
        json.dump({"k": k, "sizes": {str(lb): stats[lb]["n"] for lb in stats},
                   "centroids": km.cluster_centers_.tolist()}, f)
    print("已保存 labels.npy / cluster_meta.json")


def select(args):
    segs = load_segments()
    labels = np.load(VOICE / "labels.npy")
    assert len(labels) == len(segs), "段数与标签不一致，请重新 cluster"
    X = np.array([s["emb"] for s in segs], dtype="float32")
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    big = int(np.bincount(labels).argmax())
    cent = X[labels == big].mean(axis=0)
    cent /= np.linalg.norm(cent)
    sim = X @ cent
    conn = connect()
    series = {r[0]: (r[1] or "") for r in conn.execute("SELECT id, series FROM asset")}
    exclude = ("互动系列",)
    keep = set(int(x) for x in args.clusters.split(",")) if args.clusters else None
    out = []
    for s, lb, sm in zip(segs, labels, sim):
        lb = int(lb)
        if keep is not None and lb not in keep:
            continue
        if sm < args.min_sim:
            continue
        ser = series.get(s["aid"], "")
        if any(e in ser for e in exclude):
            continue
        if not (args.min_dur <= s.get("dur", 0) <= args.max_dur):
            continue
        if not (args.min_rms <= s.get("rms_db", -99) <= args.max_rms):
            continue
        if s.get("zcr", 1) > args.max_zcr:
            continue
        s2 = dict(s)
        s2.pop("emb", None)
        s2["cluster"] = lb
        s2["sim"] = round(float(sm), 4)
        out.append(s2)
    # 每个视频设上限，保证说话人多样性（避免个别视频占满）
    if getattr(args, "max_per_video", 0):
        cap = args.max_per_video
        byvid = defaultdict(list)
        for s in out:
            byvid[s["aid"]].append(s)
        out = [x for v in byvid.values() for x in v[:cap]]
    # 按“说话人相似度 + 音量”排序后取前 N，而不是随机抽
    out.sort(key=lambda s: (-s.get("sim", 0), -abs(s.get("rms_db", -30) + 20)))
    random.seed(0)
    total = sum(x["dur"] for x in out)
    budget = args.hours * 3600
    picked, acc = [], 0.0
    for s in out:
        if acc + s["dur"] > budget:
            continue
        picked.append(s)
        acc += s["dur"]
    outp = VOICE / args.out
    with open(outp, "w", encoding="utf-8") as f:
        for s in picked:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print("过滤后候选 %d 段 / %.1f 小时；按预算 %.1f 小时选中 %d 段" % (len(out), total / 3600, args.hours, len(picked)))
    print("涉及视频数:", len(set(x["aid"] for x in picked)))
    print("平均说话人相似度: %.3f" % (sum(x.get("sim", 0) for x in picked) / max(len(picked), 1)))
    print("已写入", outp)


def sample(args):
    import subprocess, tempfile
    from pipeline import video_path
    conn = connect()
    meta = {r[0]: r for r in conn.execute("SELECT id, relpath, source FROM asset")}
    segs = [json.loads(l) for l in open(VOICE / "selected.jsonl", encoding="utf-8")]
    random.seed(args.seed)
    picks = random.sample(segs, min(args.n, len(segs)))
    outdir = VOICE / "samples"
    outdir.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(picks):
        row = meta.get(s["aid"])
        if not row:
            continue
        dst = outdir / ("sample_%02d_aid%d_%05.1f.wav" % (i, s["aid"], s["start"]))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["start"]), "-t", str(s["dur"]),
                        "-i", str(video_path(row[1], row[2] or "archive")), "-ac", "1", "-ar", "48000",
                        "-c:a", "pcm_s16le", str(dst)], capture_output=True)
    print("样本写入:", outdir, len(picks), "个")


def stats(args):
    segs = load_segments()
    durs = np.array([s.get("dur", 0) for s in segs])
    rms = np.array([s.get("rms_db", -99) for s in segs])
    print("段数 %d | 总时长 %.1f 小时 | 平均 %.2f 秒 | 时长分位 25/50/75: %.1f/%.1f/%.1f"
          % (len(segs), durs.sum() / 3600, durs.mean(), *np.percentile(durs, [25, 50, 75])))
    print("rms_db 分位 5/50/95: %.1f / %.1f / %.1f" % tuple(np.percentile(rms, [5, 50, 95])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cluster", "select", "sample", "stats"])
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--clusters", default=None)
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--min-dur", type=float, default=2.5)
    ap.add_argument("--max-dur", type=float, default=10.0)
    ap.add_argument("--min-rms", type=float, default=-34.0)
    ap.add_argument("--max-rms", type=float, default=-8.0)
    ap.add_argument("--max-zcr", type=float, default=0.28)
    ap.add_argument("--min-sim", type=float, default=0.66)
    ap.add_argument("--max-per-video", type=int, default=0)
    ap.add_argument("--out", default="selected.jsonl")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    {"cluster": cluster, "select": select, "sample": sample, "stats": stats}[args.cmd](args)


if __name__ == "__main__":
    main()