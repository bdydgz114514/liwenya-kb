#!/usr/bin/env python3
# 语音数据集构建 L1：扫描（VAD 切分 + 说话人嵌入 + 质量指标）
import argparse, json, os, subprocess, sys, tempfile, time
from pathlib import Path
import numpy as np

ROOT = Path("/root/dsh/liwenya-kb")
sys.path.insert(0, str(ROOT / "scripts"))
from pipeline import connect, video_path

VOICE = ROOT / "voice"
SCAN = VOICE / "scan"
SCAN.mkdir(parents=True, exist_ok=True)

_vad = None
_emb = None


def get_vad():
    global _vad
    if _vad is None:
        from silero_vad import load_silero_vad
        _vad = load_silero_vad()
    return _vad


def get_emb():
    global _emb
    if _emb is None:
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        dev = "cuda" if os.environ.get("VOICE_GPU") == "1" else "cpu"
        _emb = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                              savedir=str(VOICE / "models/ecapa"),
                                              run_opts={"device": dev})
    return _emb


def embed_np(chunk):
    import torch
    clf = get_emb()
    t = torch.from_numpy(chunk).unsqueeze(0)
    with torch.no_grad():
        e = clf.encode_batch(t).squeeze().cpu().numpy()
    return e.astype("float32")


def split_segments(ts, min_sec=2.0, max_sec=10.0):
    out = []
    for t in ts:
        s, e = float(t["start"]), float(t["end"])
        if e - s < min_sec:
            continue
        while e - s > max_sec:
            out.append((s, s + max_sec))
            s += max_sec
        if e - s >= min_sec:
            out.append((s, e))
    return out


def scan_one(aid, src):
    import soundfile as sf
    from silero_vad import get_speech_timestamps
    import torch
    tmp = Path(tempfile.gettempdir()) / ("vad_%d.wav" % aid)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "pcm_s16le", str(tmp)], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.decode()[-150:])
    data, sr = sf.read(str(tmp), dtype="float32")
    tmp.unlink(missing_ok=True)
    if data.ndim > 1:
        data = data.mean(axis=1)
    ts = get_speech_timestamps(torch.from_numpy(data), get_vad(), sampling_rate=16000,
                               min_silence_duration_ms=300, min_speech_duration_ms=700,
                               return_seconds=True)
    segs = split_segments(ts)
    recs = []
    for s, e in segs:
        a, b = int(s * 16000), int(e * 16000)
        chunk = data[a:b]
        if chunk.size < 16000:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)) + 1e-9)
        zcr = float(np.mean(np.abs(np.diff(np.sign(chunk)))) / 2)
        rec = {"aid": aid, "start": round(s, 2), "end": round(e, 2),
               "dur": round(e - s, 2), "rms_db": round(20 * np.log10(rms), 1), "zcr": round(zcr, 4)}
        rec["emb"] = [round(float(x), 5) for x in embed_np(chunk)]
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default=None)
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--min-dur", type=float, default=20.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    conn = connect()
    rows = list(conn.execute("SELECT id, relpath, title, duration, source FROM asset WHERE duration > ? ORDER BY id", (args.min_dur,)))
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        rows = [r for r in rows if r[0] % n == k]
    rows = rows[:args.limit]
    print("[scan] 本进程待处理 %d 个视频" % len(rows), flush=True)
    done = 0
    for aid, rel, title, dur, source in rows:
        out = SCAN / ("%d.jsonl" % aid)
        if out.exists() and not args.force:
            continue
        t0 = time.time()
        try:
            recs = scan_one(aid, str(video_path(rel, source or "archive")))
        except Exception as e:
            print("[scan][ERR] %d %s" % (aid, str(e)[:150]), flush=True)
            continue
        with open(out, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        done += 1
        if done % 5 == 0:
            print("[scan] %d 完成 (最新 %d: %d 段, %.1fs) 用时 %.0fs" % (done, aid, len(recs), dur, time.time() - t0), flush=True)
    print("[scan] 本进程结束，共 %d 个视频" % done, flush=True)


if __name__ == "__main__":
    main()