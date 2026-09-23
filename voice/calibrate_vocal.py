#!/usr/bin/env python3
# 按“人声区 RMS”精确校准 AI 人声音量（在全部处理链之后执行）
# 用法: calibrate_vocal.py <ai.wav> <mask.npy> <target_rms> <out.wav>
import sys
import numpy as np
import soundfile as sf

ai_p, mask_p, target, out_p = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
d, sr = sf.read(ai_p, dtype="float32")
if d.ndim > 1:
    d = d.mean(axis=1)
m = np.load(mask_p)
n = min(len(d), len(m))
sel = m[:n] > 0.5
cur = float(np.sqrt(np.mean(d[:n][sel] ** 2) + 1e-12))
gain = target / max(cur, 1e-9)
gain = float(np.clip(gain, 0.05, 20.0))
d = d * gain
peak = float(np.abs(d).max())
if peak > 0.95:
    d *= 0.95 / peak
    peak = 0.95
sf.write(out_p, d, sr)
print("[calib] 人声区 RMS %.4f -> %.4f (增益 %.2fx = %+.1f dB) | 峰值 %.3f" % (cur, target, gain, 20*np.log10(gain), peak))