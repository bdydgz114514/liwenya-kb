# -*- coding: utf-8 -*-
"""给各轮 RVC 翻唱打分：与「李文亚本人声音质心」的说话人相似度 + 音质指标。

用法：python3 voice/score_voice.py [文件...]
默认对比：老数据集各轮（e50…e250）+ 新数据集最新一轮（r350）。
"""
import random
import sys
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
import torch

KB = Path("/root/dsh/liwenya-kb")
DATASET = KB / "voice/rvc_dataset2/liwenya"
COVER = KB / "voice/cover"
CLEAN = KB / "voice/clean"

random.seed(0)
torch.manual_seed(0)


def load_ecapa():
    from speechbrain.inference.speaker import EncoderClassifier
    return EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                          savedir="/root/.cache/spkrec-ecapa",
                                          run_opts={"device": "cpu"})


def embed(classifier, wav, sr, win=3.0, hop=1.5, min_rms=0.008):
    if sr != 16000:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)
    embs = []
    n = int(win * 16000)
    step = int(hop * 16000)
    for i in range(0, max(len(wav) - n, 1), step):
        seg = wav[i:i + n]
        if len(seg) < n // 2:
            continue
        if float(np.sqrt(np.mean(seg ** 2))) < min_rms:
            continue
        t = torch.tensor(seg, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            e = classifier.encode_batch(t).squeeze().cpu().numpy()
        embs.append(e / (np.linalg.norm(e) + 1e-9))
    if not embs:
        return None
    v = np.mean(embs, axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def hnr(wav, sr):
    """用 HPSS 近似谐噪比：谐波能量 / 非谐波能量，dB。"""
    y = librosa.effects.hpss(wav)
    h = float(np.sum(y[0] ** 2)) + 1e-12
    p = float(np.sum(y[1] ** 2)) + 1e-12
    return 10 * np.log10(h / p)


def main():
    files = sys.argv[1:]
    clf = load_ecapa()

    # 参考质心：训练集里随机 150 段（李文亚本人声音）
    segs = sorted(DATASET.glob("*.wav"))
    random.shuffle(segs)
    ref = []
    for p in segs[:150]:
        w, sr = sf.read(p, dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        v = embed(clf, w, sr)
        if v is not None:
            ref.append(v)
    centroid = np.mean(ref, axis=0)
    centroid /= np.linalg.norm(centroid) + 1e-9
    print(f"参考：李文亚语音质心（{len(ref)} 段训练样本）\n")

    if not files:
        files = ([str(COVER / f"vocals_e{e}.wav") for e in (50, 100, 150, 200, 250)]
                 + [str(CLEAN / "vocal_ai_r350.wav")])
    print(f"{'文件':<28}{'相似度':>8}{'时长':>8}{'谐噪比':>8}")
    print("-" * 54)
    for f in files:
        p = Path(f)
        if not p.exists():
            print(f"{p.name:<28}{'缺失':>8}")
            continue
        w, sr = sf.read(p, dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        v = embed(clf, w, sr)
        sim = float(np.dot(v, centroid)) if v is not None else float("nan")
        label = p.stem.replace("vocal_ai_", "").replace("vocals_", "")
        print(f"{label:<28}{sim:>8.3f}{len(w)/sr:>7.0f}s{hnr(w, sr):>7.1f}dB")


if __name__ == "__main__":
    main()
