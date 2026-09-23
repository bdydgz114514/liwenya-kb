#!/usr/bin/env python3
# L4-L5 融合层：场景卡 + 视频级摘要（本地 Qwen3-8B）
# 子命令: cards | summarize | status
import argparse, json, os, re, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import connect, VIDEO_ROOT, DATA, TRANS, VISION, OCR, FRAMES

CARDS = DATA / "cards"
CARDS.mkdir(parents=True, exist_ok=True)
LLM_MODEL = "/.autodl/Qwen/Qwen3-8B"


def load_jsonl(path):
    out = []
    if not Path(path).exists():
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


SRT_CACHE = None


def srt_index():
    global SRT_CACHE
    if SRT_CACHE is None:
        SRT_CACHE = {}
        root = Path("/root/李文亚全集_解压")
        for p in root.rglob("*.srt"):
            m = re.match(r"(\d{3,4})_", p.name)
            if m:
                SRT_CACHE.setdefault(m.group(1), str(p))
    return SRT_CACHE


def parse_srt(path):
    try:
        raw = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return []
    if raw.count(chr(0xfffd)) > 20:
        try:
            raw = open(path, encoding="gbk", errors="ignore").read()
        except Exception:
            pass
    segs = []
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n"))
    ts = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if not lines:
            continue
        m = ts.search(b)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        text = " ".join(lines[1:]) if ts.search(lines[0]) else " ".join(lines[2:])
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text:
            segs.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    return segs


def in_range(seg, t0, t1):
    return seg["end"] > t0 and seg["start"] < t1


def build_cards(aid, title):
    conn = connect()
    scenes = list(conn.execute("SELECT idx, t0, t1 FROM scene WHERE asset_id=? ORDER BY idx", (aid,)))
    if not scenes:
        row = conn.execute("SELECT duration FROM asset WHERE id=?", (aid,)).fetchone()
        scenes = [(0, 0.0, row[0] if row else 0.0)]
    asr = load_jsonl(TRANS / ("%d.jsonl" % aid))
    vis = load_jsonl(VISION / ("%d.jsonl" % aid))
    ocr = load_jsonl(OCR / ("%d.jsonl" % aid))
    m = re.match(r"(\d{3,4})_", title)
    srt = parse_srt(srt_index()[m.group(1)]) if m and m.group(1) in srt_index() else []
    cards = []
    for idx, t0, t1 in scenes:
        cards.append({
            "idx": idx, "t0": round(t0, 2), "t1": round(t1, 2),
            "dialogue": [s["text"] for s in srt if in_range(s, t0, t1)] or [s["text"] for s in asr if in_range(s, t0, t1)],
            "visual": [v["caption"] for v in vis if t0 <= v["t"] < t1],
            "ocr": sorted({t for o in ocr if t0 <= o["t"] < t1 for t in o.get("texts", [])}),
        })
    return cards


def compact_text(cards, limit=2600):
    buf = []
    for c in cards:
        d = " / ".join(c["dialogue"])[:300]
        v = " ".join(c["visual"])[:400]
        line = "[%d-%ds] 台词: %s || 画面: %s" % (c["t0"], c["t1"], d, v)
        buf.append(line)
        if sum(len(x) for x in buf) > limit:
            break
    return "\n".join(buf)


_llm = None


def get_llm():
    global _llm
    if _llm is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(LLM_MODEL)
        model = AutoModelForCausalLM.from_pretrained(LLM_MODEL, dtype=torch.bfloat16, device_map="cuda")
        model.eval()
        _llm = (tok, model)
        print("[llm] loaded in %.0fs" % (time.time() - t0), flush=True)
    return _llm


SUMMARY_PROMPT = """你是视频内容分析助手。下面是一个视频的标题、系列和逐场景理解结果（台词来自字幕/语音识别，画面来自视觉模型）。
请输出严格的 JSON（不要任何多余文字），字段：
{"summary": "80字以内的客观内容摘要", "key_points": ["要点1", "要点2"], "people": ["出现的人物"], "theories": ["涉及的理论/概念"], "memes": ["出现的网络梗"], "tags": ["标签"], "quotes": ["有代表性的原话，最多3条"], "tone": "整体语气"}
要求：只依据给定材料，不要脑补；不确定的字段给空数组。"""


def summarize(asset_id, title, series, digest):
    tok, model = get_llm()
    import torch
    user = "标题：%s\n系列：%s\n\n%s" % (title, series, digest)
    msgs = [{"role": "system", "content": SUMMARY_PROMPT}, {"role": "user", "content": user}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tok([text], return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=700, do_sample=False)
    gen = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    m = re.search(r"\{.*\}", gen, re.S)
    try:
        return json.loads(m.group(0)) if m else {"summary": gen.strip()[:300]}
    except Exception:
        return {"summary": gen.strip()[:300], "parse_error": True}


def cmd_cards(args):
    conn = connect()
    rows = list(conn.execute("SELECT id, title, series FROM asset WHERE frames_done=1"))
    n = 0
    for aid, title, series in rows:
        out = CARDS / ("%d.json" % aid)
        if out.exists() and not args.force:
            continue
        cards = build_cards(aid, title)
        json.dump({"asset_id": aid, "title": title, "series": series, "scenes": cards},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n += 1
    print("cards written:", n)


def cmd_summarize(args):
    conn = connect()
    rows = list(conn.execute("SELECT id, title, series FROM asset WHERE frames_done=1 ORDER BY id"))
    done = 0
    for aid, title, series in rows:
        out = CARDS / ("%d.summary.json" % aid)
        if out.exists() and not args.force:
            continue
        cp = CARDS / ("%d.json" % aid)
        if not cp.exists():
            continue
        data = json.load(open(cp, encoding="utf-8"))
        digest = compact_text(data["scenes"])
        try:
            s = summarize(aid, title, series, digest)
        except Exception as e:
            print("[sum][ERROR] %d %s" % (aid, str(e)[:150]), flush=True)
            continue
        json.dump({"asset_id": aid, "title": title, "series": series, "summary": s},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        done += 1
        if done % 20 == 0:
            print("[sum] %d done (last: %s)" % (done, title[:30]), flush=True)
    print("summaries written:", done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cards", "summarize", "status"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    {"cards": cmd_cards, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    main()