#!/usr/bin/env python3
# 生成人声活动掩码：把分离人声轨里的“真正在唱”的部分标出来
# 用法: vocal_mask.py <vocals.wav> <masked.wav> <mask.npy>
import sys
import numpy as np
import soundfile as sf

src, out_wav, out_mask = sys.argv[1], sys.argv[2], sys.argv[3]
d, sr = sf.read(src, dtype="float32")
if d.ndim > 1:
    d = d.mean(axis=1)
win, hop = int(0.03 * sr), int(0.01 * sr)
n = 1 + max(0, (len(d) - win) // hop)
e = np.array([np.sqrt(np.mean(d[i * hop:i * hop + win] ** 2) + 1e-12) for i in range(n)])
peak = np.percentile(e, 97)
thr = max(peak * 0.02, 10 ** (-52 / 20.0))   # 低于峰值 34dB 或绝对 -52dB 视为静音
active = e > thr
# 形态学平滑：先扩张 0.25s（避免切断尾音），再收缩 0.35s（去掉短促误检）
def dilate(a, k):
    if k <= 0:
        return a
    out = a.copy()
    idx = np.where(a)[0]
    for i in idx:
        out[max(0, i - k):min(len(a), i + k + 1)] = True
    return out
def erode(a, k):
    if k <= 0:
        return a
    out = a.copy()
    for i in range(len(a)):
        if a[i] and not np.all(a[max(0, i - k):min(len(a), i + k + 1)]):
            out[i] = False
    return out
k_d = int(0.25 / 0.01)
k_e = int(0.35 / 0.01)
active = erode(dilate(active, k_d), k_e)
# 转成采样级掩码 + 10ms 淡入淡出（避免爆音）
m = np.repeat(active, hop)[:len(d)]
if len(m) < len(d):
    m = np.pad(m, (0, len(d) - len(m)))
fade = int(0.01 * sr)
kernel = np.ones(fade) / fade
mf = np.convolve(m.astype("float32"), kernel, mode="same")
out = d * mf
sf.write(out_wav, out, sr)
np.save(out_mask, mf.astype("float32"))
cov = float(mf.mean())
print("[mask] 人声占比 %.1f%% | 阈值 %.5f | 输出 %s" % (cov * 100, thr, out_wav))