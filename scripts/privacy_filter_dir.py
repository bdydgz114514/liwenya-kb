#!/usr/bin/env python3
# 对目录内的 JSON/JSONL/MD 文本做隐私过滤（用于发布前的仓库副本）
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from kb import clean


def filter_file(p):
    try:
        if p.suffix == ".json":
            d = json.loads(p.read_text(encoding="utf-8"))
            txt = json.dumps(d, ensure_ascii=False)
            new = clean(txt)
            if new != txt:
                p.write_text(new, encoding="utf-8")
                return True
        elif p.suffix in (".jsonl", ".md", ".txt", ".csv"):
            txt = p.read_text(encoding="utf-8", errors="ignore")
            new = clean(txt)
            if new != txt:
                p.write_text(new, encoding="utf-8")
                return True
    except Exception:
        pass
    return False


def main():
    root = Path(sys.argv[1])
    n = 0
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".json", ".jsonl", ".md", ".txt", ".csv"):
            if filter_file(p):
                n += 1
    print("[privacy] 已脱敏文件:", n)


if __name__ == "__main__":
    main()