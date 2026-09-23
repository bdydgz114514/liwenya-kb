#!/usr/bin/env python3
# 语音数据集构建 L3：导出 RVC 训练集（48k 单声道 + 高通滤波 + 降噪 + 响度归一）
import argparse, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/root/dsh/liwenya-kb")
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import connect, video_path

VOICE = ROOT / "voice"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(VOICE / "rvc_dataset/liwenya"))
    ap.add_argument("--sr", type=int, default=48000)
    ap.add_argument("--denoise", action="store_true", default=True)
    ap.add_argument("--selected", default="selected.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    conn = connect()
    meta = {r[0]: r for r in conn.execute("SELECT id, relpath, source FROM asset")}
    segs = [json.loads(l) for l in open(VOICE / args.selected, encoding="utf-8")]
    if args.limit:
        segs = segs[:args.limit]
    print("待导出片段: %d（并行 %d 路）" % (len(segs), args.workers), flush=True)
    rnnn = "/root/dsh/rvc/models/bd.rnnn"
    if args.denoise and Path(rnnn).exists():
        af = "highpass=f=70,arnndn=m=%s,equalizer=f=200:t=q:w=1:g=-1,loudnorm=I=-20:TP=-2" % rnnn
    elif args.denoise:
        af = "highpass=f=75,afftdn=nf=-28,dynaudnorm=f=150:g=15"
    else:
        af = "highpass=f=75,dynaudnorm=f=150:g=15"
    counter = {"ok": 0, "dur": 0.0, "fail": 0}

    def one(s):
        row = meta.get(s["aid"])
        if not row:
            return
        src = str(video_path(row[1], row[2] or "archive"))
        dst = outdir / ("%d_%08.2f.wav" % (s["aid"], s["start"]))
        if dst.exists() and dst.stat().st_size > 1000:
            counter["ok"] += 1
            counter["dur"] += s.get("dur", 0)
            return
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["start"]), "-t", str(s["dur"] + 0.05),
                            "-i", src, "-vn", "-ac", "1", "-ar", str(args.sr), "-af", af,
                            "-c:a", "pcm_s16le", str(dst)], capture_output=True)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
            counter["ok"] += 1
            counter["dur"] += s.get("dur", 0)
        else:
            counter["fail"] += 1
            dst.unlink(missing_ok=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(one, segs))
    print("导出完成: %d 段 / %.1f 分钟（失败 %d）-> %s" % (counter["ok"], counter["dur"] / 60, counter["fail"], outdir))


if __name__ == "__main__":
    main()