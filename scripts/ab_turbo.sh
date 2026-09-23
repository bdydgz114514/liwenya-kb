#!/bin/bash
cd /root/dsh/liwenya-kb
pkill -f 'pipeline.py asr'; sleep 2
python - > logs/ab_turbo.log 2>&1 <<'EOF'
import subprocess, time, sqlite3
from pathlib import Path
import torch
from transformers import pipeline
VID = Path("/root/李文亚全集_解压/李文亚全集(2026-8-3)视频压缩版/李文亚世界v2.0_full_compressed/李文亚世界v2.0_full_compressed")
c = sqlite3.connect("data/index.sqlite")
aid, rel, dur = c.execute("SELECT id, relpath, duration FROM asset WHERE asr_done=0 AND source='archive' AND duration > 900 ORDER BY duration LIMIT 1").fetchone()
wav = Path("/tmp/ab.wav")
subprocess.run(["ffmpeg","-v","error","-y","-i",str(VID/rel),"-t","180","-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],check=True)
print("测试音频 180 秒:", rel[:50], flush=True)
def run(mp, label):
    t0 = time.time()
    pipe = pipeline("automatic-speech-recognition", model=mp, dtype=torch.bfloat16, device=0, chunk_length_s=30, batch_size=16)
    load = time.time()-t0
    t1 = time.time()
    out = pipe(str(wav), generate_kwargs={"language":"zh","task":"transcribe"}, return_timestamps=True)
    dt = time.time()-t1
    txt = "".join(ch["text"] for ch in out.get("chunks", []))
    print("[%s] 加载 %.0fs | 推理 %.1fs | %.1f 倍实时" % (label, load, dt, 180/dt), flush=True)
    print("   文本:", txt[:200].replace(chr(10)," "), flush=True)
    del pipe; torch.cuda.empty_cache()
    return txt
a = run("/.autodl/openai/whisper-large-v3", "large-v3")
b = run("models/whisper-large-v3-turbo", "turbo")
import difflib
print("文本相似度: %.3f" % difflib.SequenceMatcher(None, a, b).ratio(), flush=True)
EOF
cd /root/dsh/liwenya-kb && nohup python scripts/pipeline.py asr --limit 2000 --batch 16 >> logs/asr_batch.log 2>&1 &
echo AB_DONE