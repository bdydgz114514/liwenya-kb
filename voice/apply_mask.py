#!/usr/bin/env python3
# 把掩码应用到 RVC 输出（消除静音段生成的噪声），并只按“人声区”对齐响度
# 用法: apply_mask.py <ai_raw.wav> <mask.npy> <ref_vocals.wav> <out.wav>
import sys
import numpy as np
import soundfile as sf

ai_p, mask_p, ref_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
ai, sr = sf.read(ai_p, dtype="float32")
if ai.ndim > 1:
    ai = ai.mean(axis=1)
m = np.load(mask_p)
if len(m) < len(ai):
    m = np.pad(m, (0, len(ai) - len(m)))
m = m[:len(ai)]
ai = ai * m
ref, sr2 = sf.read(ref_p, dtype="float32")
if ref.ndim > 1:
    ref = ref.mean(axis=1)

def vocal_rms(x, mask):
    n = min(len(x), len(mask))
    x, mask = x[:n], mask[:n]
    sel = mask > 0.5
    if sel.sum() < sr:
        return float(np.sqrt(np.mean(x ** 2) + 1e-12))
    return float(np.sqrt(np.mean(x[sel] ** 2) + 1e-12))

r_ai = vocal_rms(ai, m)
r_ref = vocal_rms(ref, np.ones(len(ref), dtype="float32"))
gain = r_ref / max(r_ai, 1e-9)
gain = float(np.clip(gain, 0.1, 8.0))
ai = ai * gain
# 再对整轨做一次温和限制，防止削波
peak = float(np.abs(ai).max())
if peak > 0.95:
    ai *= 0.95 / peak
sf.write(out_p, ai, sr)
print("[mask] 人声区 RMS: AI %.4f -> 目标 %.4f (增益 %.2fx) | 峰值 %.3f" % (r_ai, r_ref, gain, float(np.abs(ai).max())))