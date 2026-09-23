#!/usr/bin/env python3
# 视觉层 L2: 场景切分 + 关键帧抽取 + Qwen3-VL 画面理解 + RapidOCR
# 子命令: frames | vision | ocr
import argparse, json, os, sqlite3, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import connect, VIDEO_ROOT, DATA, FRAMES, VISION, OCR, video_path

VLM_MODEL = "/.autodl/Qwen/Qwen3-VL-8B-Instruct"
PROMPT = ("你是视频画面分析助手。请仔细观察这一帧，用中文输出严格的 JSON（不要多余文字）："
          "{\"scene\":\"场景环境描述\",\"people\":[\"出现的人物及其外观/身份线索\"],"
          "\"action\":\"正在发生的动作或镜头内容\",\"onscreen_text\":\"画面中出现的文字，逐字抄录，没有则空字符串\","
          "\"style\":\"画面形式（自拍/录屏/PPT/字幕卡/影视混剪等）\",\"mood\":\"整体情绪基调\"}")


def to_sec(x):
    return float(x.get_seconds()) if hasattr(x, "get_seconds") else float(x)


def pick_keyframes(scene_list, duration, max_frames):
    scenes = [(to_sec(s), to_sec(e)) for s, e in scene_list] if scene_list else [(0.0, float(duration))]
    n = len(scenes)
    total = sum(max(e - s, 0.1) for s, e in scenes) or float(duration) or 1.0
    target = max(3, min(max_frames, int(total // 12) + 2))
    picks = []
    for idx, (t0, t1) in enumerate(scenes):
        if t1 - t0 < 0.4:
            t1 = t0 + 0.4
        span = t1 - t0
        k = max(1, round(target * (span / total)))
        for j in range(k):
            frac = (j + 0.5) / k
            picks.append((idx, round(t0 + span * frac, 3)))
    if len(picks) > target:
        step = len(picks) / target
        picks = [picks[int(i * step)] for i in range(target)]
    return picks, n, scenes


def cmd_frames(args):
    from scenedetect import open_video, SceneManager, ContentDetector
    conn = connect()
    if args.ids:
        q = "SELECT id, relpath, title, duration, source FROM asset WHERE id IN (%s)" % ",".join(str(int(i)) for i in args.ids)
    else:
        q = "SELECT id, relpath, title, duration, source FROM asset WHERE frames_done=0 ORDER BY duration LIMIT %d" % args.limit
    rows = list(conn.execute(q))
    for aid, rel, title, dur, source in rows:
        path = str(video_path(rel, source or "archive"))
        outdir = FRAMES / str(aid)
        outdir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        try:
            video = open_video(path)
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))
            sm.detect_scenes(video, show_progress=False)
            scenes = sm.get_scene_list()
            picks, nscene, norm_scenes = pick_keyframes(scenes, dur, args.max_frames)
            meta = []
            for idx, ts in picks:
                fp = outdir / ("s%03d_%08.2f.jpg" % (idx, ts))
                if not fp.exists():
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ts), "-i", path,
                                    "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(fp)],
                                   capture_output=True)
                if fp.exists():
                    meta.append({"scene": idx, "t": ts, "frame": str(fp)})
            conn.execute("DELETE FROM scene WHERE asset_id=?", (aid,))
            for idx, (s, e) in enumerate(norm_scenes):
                kf = [m["frame"] for m in meta if m["scene"] == idx]
                conn.execute("INSERT INTO scene(asset_id, idx, t0, t1, keyframes) VALUES(?,?,?,?,?)",
                             (aid, idx, s, e, json.dumps(kf)))
            with open(FRAMES / (str(aid) + ".jsonl"), "w") as f:
                for m in meta:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
            conn.execute("UPDATE asset SET frames_done=1 WHERE id=?", (aid,))
            conn.commit()
            print("[frames] id=%d scenes=%d frames=%d %.1fs %s" % (aid, nscene, len(meta), time.time() - t0, title[:36]), flush=True)
        except Exception as e:
            print("[frames][ERROR] id=%d %s: %s" % (aid, title[:36], e), flush=True)


_vlm = None


def get_vlm():
    global _vlm
    if _vlm is None:
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        t0 = time.time()
        proc = AutoProcessor.from_pretrained(VLM_MODEL)
        model = Qwen3VLForConditionalGeneration.from_pretrained(VLM_MODEL, dtype=torch.bfloat16, device_map="cuda")
        model.eval()
        _vlm = (proc, model)
        print("[vlm] loaded in %.0fs" % (time.time() - t0), flush=True)
    return _vlm


def caption(proc, model, image_paths):
    import torch
    from qwen_vl_utils import process_vision_info
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    messages = [[{"role": "user", "content": [
        {"type": "image", "image": p, "max_pixels": 640 * 640},
        {"type": "text", "text": PROMPT}]}] for p in image_paths]
    texts = [proc.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in messages]
    imgs = [process_vision_info(m)[0] for m in messages]
    inputs = proc(text=texts, images=imgs, padding=True, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=220, do_sample=False)
    trimmed = [o[len(i):] for i, o in zip(inputs.input_ids, out)]
    return [t.strip() for t in proc.batch_decode(trimmed, skip_special_tokens=True)]


def frames_job_running():
    r = subprocess.run(["pgrep", "-f", "vision.py frames"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def cmd_vision(args):
    proc, model = None, None
    idle = 0
    while True:
        conn = connect()
        if args.ids:
            q = "SELECT id, title FROM asset WHERE id IN (%s)" % ",".join(str(int(i)) for i in args.ids)
        else:
            q = "SELECT id, title FROM asset WHERE frames_done=1 AND vision_done=0 ORDER BY id LIMIT %d" % args.limit
        rows = list(conn.execute(q))
        if not rows:
            if not args.watch:
                print("nothing to do")
                return
            if not frames_job_running():
                print("[vision] 抽帧任务已结束且无待处理视频，退出", flush=True)
                return
            idle += 1
            time.sleep(30)
            continue
        if proc is None:
            proc, model = get_vlm()
        process_rows(conn, proc, model, rows, args)


def process_rows(conn, proc, model, rows, args):
    for aid, title in rows:
        meta = [json.loads(l) for l in open(FRAMES / (str(aid) + ".jsonl"))]
        out = VISION / (str(aid) + ".jsonl")
        done = set()
        if out.exists():
            for l in open(out):
                try:
                    done.add(json.loads(l)["frame"])
                except Exception:
                    pass
        todo = [m for m in meta if m["frame"] not in done]
        t0 = time.time()
        with open(out, "a") as f:
            for i in range(0, len(todo), args.batch):
                chunk = todo[i:i + args.batch]
                try:
                    caps = caption(proc, model, [c["frame"] for c in chunk])
                except Exception as e:
                    caps = [json.dumps({"error": str(e)[:200]}, ensure_ascii=False)] * len(chunk)
                for m, txt in zip(chunk, caps):
                    rec = {"asset_id": aid, "t": m["t"], "scene": m["scene"], "frame": m["frame"], "caption": txt}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
        conn.execute("UPDATE asset SET vision_done=1 WHERE id=?", (aid,))
        conn.commit()
        print("[vision] id=%d frames=%d %.1fs (%.2fs/frame) %s" % (aid, len(meta), time.time() - t0, (time.time() - t0) / max(len(meta), 1), title[:36]), flush=True)


def cmd_ocr(args):
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    conn = connect()
    rows = list(conn.execute("SELECT id, title FROM asset WHERE frames_done=1 LIMIT %d" % args.limit))
    for aid, title in rows:
        meta = [json.loads(l) for l in open(FRAMES / (str(aid) + ".jsonl"))]
        out = OCR / (str(aid) + ".jsonl")
        with open(out, "w") as f:
            for m in meta:
                res, _ = engine(m["frame"])
                texts = [r[1] for r in res] if res else []
                f.write(json.dumps({"asset_id": aid, "t": m["t"], "texts": texts}, ensure_ascii=False) + "\n")
        print("[ocr] id=%d frames=%d %s" % (aid, len(meta), title[:36]), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["frames", "vision", "ocr"])
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--max-frames", type=int, default=24)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    {"frames": cmd_frames, "vision": cmd_vision, "ocr": cmd_ocr}[args.cmd](args)


if __name__ == "__main__":
    main()