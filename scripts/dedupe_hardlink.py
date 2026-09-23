# -*- coding: utf-8 -*-
"""把重复的大文件替换为硬链接（先按大小分组，再按内容哈希确认，保证字节一致）。"""
import hashlib
import os
from pathlib import Path

DIRS = [
    Path('/root/output_videos'),
    Path('/root/dsh/movie/output'),
    Path('/root/dsh/liwenya-kb/voice/cover'),
    Path('/root/dsh/liwenya-kb/voice/faceswap'),
    Path('/root/dsh/faceswap'),
    Path('/root/dsh/liwenya-kb/site/public/film'),
    Path('/root/dsh/rvc/webui/assets/weights'),
]
MIN = 5_000_000


def sha(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


files = []
for d in DIRS:
    if d.exists():
        files += [p for p in d.rglob('*') if p.is_file() and p.stat().st_size >= MIN]

by_size = {}
for p in files:
    by_size.setdefault(p.stat().st_size, []).append(p)

saved = 0
linked = 0
for size, group in by_size.items():
    if len(group) < 2 or len({p.stat().st_ino for p in group}) < 2:
        continue
    by_hash = {}
    for p in group:
        try:
            by_hash.setdefault(sha(p), []).append(p)
        except OSError:
            pass
    for h, same in by_hash.items():
        if len(same) < 2:
            continue
        master = same[0]
        for dup in same[1:]:
            if dup.stat().st_ino == master.stat().st_ino:
                continue
            tmp = dup.with_suffix(dup.suffix + '.dedup')
            try:
                os.link(master, tmp)
                os.replace(tmp, dup)
                saved += size
                linked += 1
                print(f'  链接 {dup} → {master.name}（省 {size/1048576:.0f} MB）')
            except OSError as e:
                print('  失败', dup, e)
                if tmp.exists():
                    tmp.unlink()
print(f'共硬链接 {linked} 个文件，节省约 {saved/1024**3:.2f} GB')
