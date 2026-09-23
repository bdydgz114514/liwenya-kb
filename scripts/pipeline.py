#!/usr/bin/env python3
# 李文亚知识库 · 多模态理解流水线 (L0-L5)
# 子命令: probe | asr | frames | vision | ocr | status
import argparse, json, os, sqlite3, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/root/dsh/liwenya-kb")
VIDEO_ROOT = Path("/root/李文亚全集_解压/李文亚全集(2026-8-3)视频压缩版/李文亚世界v2.0_full_compressed/李文亚世界v2.0_full_compressed")
DATA = ROOT / "data"
DB = DATA / "index.sqlite"
AUDIO = DATA / "audio"
FRAMES = DATA / "frames"
TRANS = DATA / "transcripts"
VISION = DATA / "vision"
OCR = DATA / "ocr"
ASR_MODEL = str(ROOT / "models/whisper-large-v3-ct2")
VLM_MODEL = "/.autodl/Qwen/Qwen3-VL-8B-Instruct"
TERMS = "李文亚，文亚宇宙，民科，黑体生物，白体生物，清醒人格，孙笑川，二阶堂希罗，诺委会，狱卒，话疗，民科大学，米哈游，原神，贴吧，B站"
BILI_ROOT = ROOT / "sources/bilibili"


def video_path(rel, source="archive"):
    return (BILI_ROOT if source == "bilibili" else VIDEO_ROOT) / rel

for d in (DATA, AUDIO, FRAMES, TRANS, VISION, OCR):
    d.mkdir(parents=True, exist_ok=True)


def connect():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS asset(
        id INTEGER PRIMARY KEY, relpath TEXT UNIQUE, series TEXT, title TEXT,
        duration REAL, width INTEGER, height INTEGER, vcodec TEXT, acodec TEXT,
        size INTEGER, mtime REAL, probed_at REAL, asr_done INTEGER DEFAULT 0,
        frames_done INTEGER DEFAULT 0, vision_done INTEGER DEFAULT 0)""")
    try:
        conn.execute("ALTER TABLE asset ADD COLUMN source TEXT DEFAULT 'archive'")
    except Exception:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS transcript(
        asset_id INTEGER, start REAL, end REAL, text TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS scene(
        asset_id INTEGER, idx INTEGER, t0 REAL, t1 REAL, keyframes TEXT)""")
    conn.commit()
    return conn


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ffprobe(path):
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path])
    if r.returncode != 0:
        return None
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    return {
        "duration": float(j["format"].get("duration", 0) or 0),
        "size": int(j["format"].get("size", 0) or 0),
        "width": int(v.get("width", 0) or 0),
        "height": int(v.get("height", 0) or 0),
        "vcodec": v.get("codec_name", ""),
        "acodec": a.get("codec_name", ""),
    }


def cmd_probe(args):
    conn = connect()
    root = Path(args.root) if args.root else VIDEO_ROOT
    src = args.source
    if not root.is_absolute():
        root = (ROOT / root).resolve()
    files = sorted(root.rglob("*.mkv"))
    print("found", len(files), "videos")

    def one(p):
        rel = str(p.relative_to(root))
        info = ffprobe(str(p))
        if not info:
            return None
        parts = rel.split(os.sep)
        series = os.sep.join(parts[:-1]) or "根目录"
        return (rel, series, p.stem, info["duration"], info["width"], info["height"],
                info["vcodec"], info["acodec"], info["size"], p.stat().st_mtime, time.time(), src)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        rows = [r for r in ex.map(one, files) if r]
    conn.executemany("""INSERT INTO asset(relpath, series, title, duration, width, height,
        vcodec, acodec, size, mtime, probed_at, source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(relpath) DO UPDATE SET duration=excluded.duration, size=excluded.size,
        width=excluded.width, height=excluded.height, probed_at=excluded.probed_at""", rows)
    conn.commit()
    cur = conn.execute("SELECT COUNT(*), SUM(duration), SUM(size) FROM asset")
    n, dur, size = cur.fetchone()
    print("indexed %d videos, %.2f hours, %.2f GiB" % (n, (dur or 0) / 3600, (size or 0) / 2**30))


HALLUCINATION_PATTERNS = [
    "请不吝点赞", "订阅", "转发", "打赏支持", "明镜与点点栏目", "中文字幕", "字幕由",
    "字幕志愿者", "谢谢观看", "感谢观看", "MING PAO", "amara.org", "感谢您收看",
    "請不吝點贊", "訂閱", "轉發",
]


def is_hallucination(text):
    if not text:
        return True
    t = text.strip()
    if len(t) < 2:
        return True
    hits = sum(1 for p in HALLUCINATION_PATTERNS if p in t)
    return hits >= 2 or (hits >= 1 and len(t) < 25)


def to_simplified(text):
    try:
        from zhconv import convert
        return convert(text, "zh-cn")
    except Exception:
        return text


def extract_audio(path, out):
    if out.exists() and out.stat().st_size > 1000:
        return out
    r = run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1",
             "-ar", "16000", "-c:a", "pcm_s16le", str(out)])
    if r.returncode != 0:
        raise RuntimeError("ffmpeg audio failed: " + r.stderr[-300:])
    return out


ASR_HF = "/.autodl/openai/whisper-large-v3"
_asr_pipe = None


def get_asr(batch_size=16):
    global _asr_pipe
    if _asr_pipe is None:
        import torch
        from transformers import pipeline
        t0 = time.time()
        _asr_pipe = pipeline("automatic-speech-recognition", model=ASR_HF, dtype=torch.bfloat16,
                             device=0, chunk_length_s=30, batch_size=batch_size)
        _asr_pipe.model.generation_config.language = "zh"
        _asr_pipe.model.generation_config.task = "transcribe"
        print("[asr] model loaded in %.0fs" % (time.time() - t0), flush=True)
    return _asr_pipe


def load_scan_segments(aid):
    p = ROOT / "voice" / "scan" / ("%d.jsonl" % aid)
    if not p.exists():
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        try:
            d = json.loads(line)
            out.append((float(d["start"]), float(d["end"])))
        except Exception:
            pass
    out.sort()
    return out


def build_speech_wav(aid, src):
    import numpy as np
    import soundfile as sf
    segs = load_scan_segments(aid)
    if len(segs) < 2:
        return None
    full = Path(tempfile.gettempdir()) / ("full_%d.wav" % aid)
    r = run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(full)])
    if r.returncode != 0:
        return None
    data, sr = sf.read(str(full), dtype="float32")
    full.unlink(missing_ok=True)
    if data.ndim > 1:
        data = data.mean(axis=1)
    pad = 0.15
    gap = int(0.25 * sr)
    pieces, mapping, cursor = [], [], 0
    for s, e in segs:
        a = max(0, int((s - pad) * sr))
        b = min(len(data), int((e + pad) * sr))
        if b - a < int(0.7 * sr):
            continue
        pieces.append(data[a:b])
        mapping.append((cursor, cursor + (b - a), a / float(sr)))
        cursor += (b - a) + gap
        pieces.append(np.zeros(gap, dtype="float32"))
    if not pieces:
        return None
    speech = np.concatenate(pieces)
    out = Path(tempfile.gettempdir()) / ("speech_%d.wav" % aid)
    sf.write(str(out), speech, sr)
    return out, mapping


def map_time(t, mapping):
    for a, b, orig_a in mapping:
        if a <= t < b:
            return orig_a + (t - a)
    last = 0.0
    for a, b, orig_a in mapping:
        if t >= b:
            last = orig_a + (b - a)
    return last


def prepare_audio(aid, rel, source, vad_skip):
    """解码并（可选）按语音段拼接，返回 (wav_path, mapping)"""
    src = str(video_path(rel, source or "archive"))
    wav = AUDIO / ("%d.wav" % aid)
    if vad_skip:
        sp = build_speech_wav(aid, src)
        if sp:
            return sp
    extract_audio(src, wav)
    return (wav, None)


def cmd_asr(args):
    conn = connect()
    if args.ids:
        q = "SELECT id, relpath, title, source FROM asset WHERE id IN (%s)" % ",".join(str(int(i)) for i in args.ids)
    else:
        q = "SELECT id, relpath, title, source FROM asset WHERE asr_done=0 ORDER BY duration LIMIT %d" % args.limit
    if getattr(args, "shard", None):
        k, n = (int(x) for x in args.shard.split("/"))
        rows = [r for r in rows if r[0] % n == k]
    rows = list(conn.execute(q))
    model = get_asr(getattr(args, "batch", 16))
    # 预取：在 GPU 转写当前视频时，用后台线程解码/拼接下一个视频的音频
    pool = ThreadPoolExecutor(max_workers=1)
    prep = None
    for idx, (aid, rel, title, source) in enumerate(rows):
        t0 = time.time()
        wav = AUDIO / ("%d.wav" % aid)
        try:
            if prep is None:
                prep = pool.submit(prepare_audio, aid, rel, source, getattr(args, "vad_skip", False))
            try:
                target, mapping = prep.result()
            except Exception as e:
                prep = None
                raise
            if idx + 1 < len(rows):
                na, nr, nt, ns = rows[idx + 1]
                prep = pool.submit(prepare_audio, na, nr, ns, getattr(args, "vad_skip", False))
            else:
                prep = None
            gk = {"language": "zh", "task": "transcribe"}
            try:
                gk["prompt_ids"] = model.tokenizer.get_prompt_ids(TERMS, return_tensors="pt").to("cuda")
            except Exception:
                pass
            res = model(str(target), generate_kwargs=gk, return_timestamps=True)
            if mapping is not None:
                try:
                    target.unlink()
                except Exception:
                    pass
            out = TRANS / ("%d.jsonl" % aid)
            lines = []
            with open(out, "w") as f:
                for ch in res.get("chunks") or []:
                    ts = ch.get("timestamp") or (None, None)
                    if mapping is not None:
                        s0 = map_time(ts[0] or 0.0, mapping)
                        s1 = map_time(ts[1] if ts[1] is not None else (ts[0] or 0.0) + 5.0, mapping)
                    else:
                        s0, s1 = ts[0] or 0.0, (ts[1] if ts[1] is not None else (ts[0] or 0.0) + 5.0)
                    item = {"asset_id": aid, "start": round(s0, 3), "end": round(s1, 3),
                            "text": to_simplified(ch["text"].strip())}
                    if not item["text"] or is_hallucination(item["text"]):
                        continue
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    lines.append(item)
            conn.executemany("INSERT INTO transcript(asset_id, start, end, text) VALUES(?,?,?,?)",
                [(aid, i["start"], i["end"], i["text"]) for i in lines])
            conn.execute("UPDATE asset SET asr_done=1 WHERE id=?", (aid,))
            conn.commit()
            try:
                wav.unlink()
            except Exception:
                pass
            dt = time.time() - t0
            dur = sum(i["end"] - i["start"] for i in lines)
            print("[asr] id=%d %.1fs in %.1fs (%.1fx) %s" % (aid, dur, dt, dur / max(dt, 0.01), title[:40]), flush=True)
        except Exception as e:
            print("[asr][ERROR] id=%d %s: %s" % (aid, title[:40], e), flush=True)


def cmd_status(args):
    conn = connect()
    for label, q in [("资产", "SELECT COUNT(*), SUM(duration)/3600.0 FROM asset"),
                     ("已转写", "SELECT COUNT(*) FROM asset WHERE asr_done=1"),
                     ("已抽帧", "SELECT COUNT(*) FROM asset WHERE frames_done=1"),
                     ("已视觉", "SELECT COUNT(*) FROM asset WHERE vision_done=1"),
                     ("转写片段", "SELECT COUNT(*) FROM transcript"),
                     ("场景", "SELECT COUNT(*) FROM scene")]:
        print(label, conn.execute(q).fetchone())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "asr", "status"])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--root", default=None)
    ap.add_argument("--source", default="archive")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--shard", default=None)
    ap.add_argument("--vad-skip", action="store_true")
    args = ap.parse_args()
    {"probe": cmd_probe, "asr": cmd_asr, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()