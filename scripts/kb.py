#!/usr/bin/env python3
# L6 知识库：实体/关系/文档/检索单元 + FTS5 全文 + FAISS 向量 + 站点数据导出
# 子命令: build | embed | export | query | stats
import argparse, glob, json, os, re, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import connect, DATA

ROOT = Path("/root/dsh/liwenya-kb")
KB = ROOT / "kb"
KB.mkdir(parents=True, exist_ok=True)
DB = KB / "liwenya_kb.sqlite"
CARDS = DATA / "cards"
EXPORT = KB / "export"
EMB_MODEL = "/.autodl/jinaai/jina-embeddings-v3"

# 隐私过滤：参考站点自身声明不收录住址/健康等私密信息，此处强制剔除
PRIVACY = [
    (re.compile(r"(丰泽苑|花洲街道|邓州市?[^。，,\s]{0,6}(小区|社区|街道|路|号))"), "[已隐去住址]"),
    (re.compile(r"1[3-9]\d{9}"), "[已隐去手机号]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[已隐去证件号]"),
    (re.compile(r"(糖尿病|癌|住院|手术|病历|确诊)[^。，,\n]{0,12}"), "[已隐去健康信息]"),
]


def clean(text):
    if not text:
        return text
    for pat, rep in PRIVACY:
        text = pat.sub(rep, text)
    return text


def kdb():
    conn = sqlite3.connect(DB, timeout=60)
    conn.executescript("""
      PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS entity(id TEXT PRIMARY KEY, name TEXT, type TEXT, aliases TEXT, summary TEXT, tags TEXT, sources TEXT);
      CREATE TABLE IF NOT EXISTS relation(id INTEGER PRIMARY KEY, src TEXT, dst TEXT, type TEXT, evidence TEXT, source TEXT, video_ref TEXT);
      CREATE TABLE IF NOT EXISTS doc(id TEXT PRIMARY KEY, kind TEXT, title TEXT, source TEXT, meta TEXT, body TEXT);
      CREATE TABLE IF NOT EXISTS chunk(id INTEGER PRIMARY KEY, doc_id TEXT, kind TEXT, asset_id INTEGER, t0 REAL, t1 REAL, text TEXT);
      CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(text, content='chunk', content_rowid='id', tokenize='trigram');
    """)
    conn.commit()
    return conn


def insert_chunks(conn, rows):
    conn.executemany("INSERT INTO chunk(doc_id, kind, asset_id, t0, t1, text) VALUES(?,?,?,?,?,?)", rows)
    conn.commit()


def cmd_build(args):
    conn = kdb()
    # 1) 参考 wiki 实体
    ref = ROOT / "sources/wiki_refs/entities.json"
    if ref.exists():
        d = json.load(open(ref, encoding="utf-8"))
        for e in d.get("entities", []):
            conn.execute("INSERT OR REPLACE INTO entity(id,name,type,aliases,summary,tags,sources) VALUES(?,?,?,?,?,?,?)",
                (e.get("name"), e.get("name"), e.get("type"), json.dumps(e.get("aliases", []), ensure_ascii=False),
                 clean(e.get("summary", ""))[:1000], json.dumps(e.get("tags", []), ensure_ascii=False),
                 json.dumps(e.get("sources", []), ensure_ascii=False)))
        for r in d.get("relations", []):
            conn.execute("INSERT INTO relation(src,dst,type,evidence,source) VALUES(?,?,?,?,?)",
                (r.get("from"), r.get("to"), r.get("type"), clean(str(r.get("evidence", "")))[:500], r.get("source")))
        for ev in d.get("events", []):
            conn.execute("INSERT OR REPLACE INTO doc(id,kind,title,source,meta,body) VALUES(?,?,?,?,?,?)",
                ("event:" + str(ev.get("title"))[:60], "event", clean(ev.get("title", "")), ev.get("source", ""),
                 json.dumps({"date": ev.get("date")}, ensure_ascii=False), clean(ev.get("summary", ""))))
        for g in d.get("glossary", []):
            conn.execute("INSERT OR REPLACE INTO entity(id,name,type,aliases,summary,tags,sources) VALUES(?,?,?,?,?,?,?)",
                ("term:" + str(g.get("term")), g.get("term"), "术语", "[]", clean(g.get("definition", ""))[:800], "[]",
                 json.dumps([g.get("source")], ensure_ascii=False)))
        conn.commit()
        print("[kb] 参考 wiki 实体导入完成")
    # 2) 视频摘要 + 场景卡 -> chunk
    n_chunk = 0
    summarized = set()
    for sp in sorted(glob.glob(str(CARDS / "*.summary.json"))):
        s = json.load(open(sp, encoding="utf-8"))
        aid = s["asset_id"]
        title = clean(s.get("title", ""))
        body = json.dumps(s.get("summary", {}), ensure_ascii=False)
        conn.execute("INSERT OR REPLACE INTO doc(id,kind,title,source,meta,body) VALUES(?,?,?,?,?,?)",
            ("video:%d" % aid, "video", title, "local-archive", json.dumps({"series": s.get("series")}, ensure_ascii=False), clean(body)))
        summ = s.get("summary", {})
        if isinstance(summ, dict):
            text = "%s。要点：%s。人物：%s。理论：%s。梗：%s。标签：%s" % (
                summ.get("summary", ""), "；".join(summ.get("key_points", []) or []),
                "、".join(summ.get("people", []) or []), "、".join(summ.get("theories", []) or []),
                "、".join(summ.get("memes", []) or []), "、".join(summ.get("tags", []) or []))
            insert_chunks(conn, [("video:%d" % aid, "summary", aid, 0.0, 0.0, clean(title + "。" + text))])
            n_chunk += 1
        cp = CARDS / ("%d.json" % aid)
        if cp.exists():
            data = json.load(open(cp, encoding="utf-8"))
            rows = []
            for sc in data.get("scenes", []):
                txt = " | ".join([x for x in [" ".join(sc.get("dialogue", [])[:6]), " ".join(sc.get("visual", []))[:400], " ".join(sc.get("ocr", [])[:3])] if x])
                if txt.strip():
                    rows.append(("video:%d" % aid, "scene", aid, sc.get("t0", 0.0), sc.get("t1", 0.0), clean(txt)[:2000]))
            insert_chunks(conn, rows)
            n_chunk += len(rows)
        summarized.add(aid)
    # 2b) 尚无摘要的视频：先入库场景卡，保证知识库覆盖全量
    for cp in sorted(glob.glob(str(CARDS / "[0-9]*.json"))):
        if cp.endswith(".summary.json"):
            continue
        aid = int(os.path.basename(cp)[:-5])
        if aid in summarized:
            continue
        try:
            data = json.load(open(cp, encoding="utf-8"))
        except Exception:
            continue
        title = clean(data.get("title", ""))
        conn.execute("INSERT OR REPLACE INTO doc(id,kind,title,source,meta,body) VALUES(?,?,?,?,?,?)",
            ("video:%d" % aid, "video", title, "local-archive",
             json.dumps({"series": data.get("series")}, ensure_ascii=False), ""))
        rows = []
        for sc in data.get("scenes", []):
            txt = " | ".join([x for x in [" ".join(sc.get("dialogue", [])[:6]), " ".join(sc.get("visual", []))[:400], " ".join(sc.get("ocr", [])[:3])] if x])
            if txt.strip():
                rows.append(("video:%d" % aid, "scene", aid, sc.get("t0", 0.0), sc.get("t1", 0.0), clean(txt)[:2000]))
        insert_chunks(conn, rows)
        n_chunk += len(rows)
    # 3) B 站视频元数据
    for jp in glob.glob(str(ROOT / "sources/bilibili/*/*.info.json")):
        try:
            d = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        vid = d.get("id")
        desc = clean((d.get("description") or "")[:4000])
        conn.execute("INSERT OR REPLACE INTO doc(id,kind,title,source,meta,body) VALUES(?,?,?,?,?,?)",
            ("bili:" + str(vid), "bilibili", clean(d.get("title", "")), d.get("webpage_url", ""),
             json.dumps({"uploader": d.get("uploader"), "duration": d.get("duration"), "view_count": d.get("view_count"), "like_count": d.get("like_count")}, ensure_ascii=False), desc))
        insert_chunks(conn, [("bili:" + str(vid), "meta", None, 0.0, 0.0, clean((d.get("title") or "") + "。" + desc)[:2000])])
    conn.commit()
    conn.execute("INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild')")
    conn.commit()
    print("[kb] 构建完成: chunk=%d" % n_chunk)


def cmd_stats(args):
    conn = kdb()
    for t in ("entity", "relation", "doc", "chunk"):
        print(t, conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0])
    print("video_docs", conn.execute("SELECT COUNT(*) FROM doc WHERE kind='video'").fetchone()[0])


def cmd_embed(args):
    import numpy as np
    conn = kdb()
    rows = list(conn.execute("SELECT id, text FROM chunk ORDER BY id"))
    if not rows:
        print("no chunks"); return
    model_dir = "/.autodl/jinaai/jina-embeddings-v3"
    texts = [r[1] for r in rows]
    embs = None
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
        sess = ort.InferenceSession(model_dir + "/onnx/model_fp16.onnx",
                                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        print("[kb] ONNX 向量模型已加载，开始编码 %d 条" % len(texts), flush=True)
        out = []
        B = 1  # 该 ONNX 导出只支持 batch=1（内部 Reshape 固定形状）
        for i in range(0, len(texts), B):
            batch = texts[i:i + B]
            enc = tok(batch, padding=True, truncation=True, max_length=512, return_tensors="np")
            res = sess.run(None, {"input_ids": enc["input_ids"].astype("int64"),
                                  "attention_mask": enc["attention_mask"].astype("int64"),
                                  "task_id": np.full(len(batch), 1, dtype="int64")})
            e = np.asarray(res[1] if len(res) > 1 else res[0], dtype="float32")
            if e.ndim == 3:
                mask = enc["attention_mask"].astype("float32")[..., None]
                e = (e * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
            e /= (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
            out.append(e)
            if (i // B) % 25 == 0:
                print("   %d/%d" % (i + len(batch), len(texts)), flush=True)
        embs = np.vstack(out)
    except Exception as e:
        print("[kb] ONNX 路线失败(%s)，回退 sentence-transformers" % str(e)[:80], flush=True)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMB_MODEL, trust_remote_code=True)
        embs = model.encode(texts, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
    np.save(KB / "embeddings.npy", embs.astype("float32"))
    json.dump([r[0] for r in rows], open(KB / "chunk_ids.json", "w"))
    try:
        import faiss
        index = faiss.IndexFlatIP(embs.shape[1])
        index.add(embs.astype("float32"))
        faiss.write_index(index, str(KB / "faiss.index"))
        print("[kb] FAISS 索引已写入", embs.shape)
    except Exception as e:
        print("[kb] FAISS 不可用，仅保存 numpy 向量:", str(e)[:120])


def cmd_query(args):
    conn = kdb()
    q = args.text
    print("=== 全文检索 ===")
    try:
        for cid, txt in conn.execute("SELECT c.id, c.text FROM chunk_fts f JOIN chunk c ON c.id=f.rowid WHERE chunk_fts MATCH ? LIMIT 5", (q,)):
            print("-", txt[:160])
    except Exception as e:
        print("FTS 失败:", str(e)[:120])
    if (KB / "faiss.index").exists():
        print("=== 语义检索 ===")
        import numpy as np, faiss, onnxruntime as ort
        from transformers import AutoTokenizer
        md = "/.autodl/jinaai/jina-embeddings-v3"
        tk = AutoTokenizer.from_pretrained(md, trust_remote_code=True)
        ss = ort.InferenceSession(md + "/onnx/model_fp16.onnx",
                                  providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        enc = tk([q], padding=True, truncation=True, max_length=256, return_tensors="np")
        rr = ss.run(None, {"input_ids": enc["input_ids"].astype("int64"),
                           "attention_mask": enc["attention_mask"].astype("int64"),
                           "task_id": np.zeros(1, dtype="int64")})
        v = np.asarray(rr[1] if len(rr) > 1 else rr[0], dtype="float32")
        if v.ndim == 3:
            mk = enc["attention_mask"].astype("float32")[..., None]
            v = (v * mk).sum(axis=1) / np.maximum(mk.sum(axis=1), 1e-9)
        v /= (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
        idx = faiss.read_index(str(KB / "faiss.index"))
        D, I = idx.search(v, 5)
        ids = json.load(open(KB / "chunk_ids.json"))
        for score, i in zip(D[0], I[0]):
            row = conn.execute("SELECT text FROM chunk WHERE id=?", (ids[i],)).fetchone()
            if row:
                print("- %.3f %s" % (score, row[0][:160]))


def _latest_video_rows(conn):
    rows = []
    sums = {}
    for sp in sorted(glob.glob(str(CARDS / "*.summary.json"))):
        try:
            s = json.load(open(sp, encoding="utf-8"))
            sums[s["asset_id"]] = s
        except Exception:
            pass
    for cp in sorted(glob.glob(str(CARDS / "[0-9]*.json"))):
        if cp.endswith(".summary.json"):
            continue
        try:
            d = json.load(open(cp, encoding="utf-8"))
        except Exception:
            continue
        aid = d.get("asset_id")
        merged = dict(d)
        merged["summary"] = sums.get(aid, {}).get("summary", {})
        rows.append(merged)
    return rows


def parse_caption(txt):
    if not txt:
        return {"scene": ""}
    s = txt.strip()
    try:
        d = json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        try:
            d = json.loads(m.group(0)) if m else {"scene": s[:200]}
        except Exception:
            d = {"scene": s[:200]}
    if not isinstance(d, dict):
        d = {"scene": str(d)[:200]}
    out = {"scene": clean(str(d.get("scene", "")))[:200],
           "action": clean(str(d.get("action", "")))[:200],
           "people": [clean(str(x))[:80] for x in (d.get("people") or [])][:4],
           "onscreen_text": clean(str(d.get("onscreen_text", "")))[:200],
           "style": clean(str(d.get("style", "")))[:60],
           "mood": clean(str(d.get("mood", "")))[:60]}
    return out


def cmd_export(args):
    import subprocess
    conn = kdb()
    EXPORT.mkdir(parents=True, exist_ok=True)
    adb = connect()
    meta = {r[0]: r for r in adb.execute("SELECT id, series, duration, relpath, source, title FROM asset")}
    cards, sums = {}, {}
    for s in _latest_video_rows(conn):
        cards[s["asset_id"]] = s
    for sp in glob.glob(str(CARDS / "*.summary.json")):
        try:
            sm = json.load(open(sp, encoding="utf-8"))
            sums[sm["asset_id"]] = sm.get("summary", {})
        except Exception:
            pass
    videos = []
    for aid in sorted(meta):
        a = meta[aid]
        s = cards.get(aid, {"asset_id": aid, "title": a[5] or a[3], "series": a[1]})
        cp = CARDS / ("%d.json" % aid)
        scenes = []
        if cp.exists():
            d = json.load(open(cp, encoding="utf-8"))
            for sc in d.get("scenes", []):
                scenes.append({"t0": sc.get("t0"), "t1": sc.get("t1"),
                               "visual": [parse_caption(v) for v in sc.get("visual", [])][:3],
                               "dialogue": [clean(x)[:200] for x in sc.get("dialogue", [])][:6],
                               "ocr": [clean(x)[:120] for x in sc.get("ocr", [])][:4]})
        summ = sums.get(aid, {})
        rel = a[3] or ""
        videos.append({"id": str(aid), "title": clean(s.get("title", "")), "series": a[1] or s.get("series", ""),
                       "source": a[4] or "archive", "path": clean(rel),
                       "bilibili": ("https://www.bilibili.com/video/" + rel.split("_")[0] + "/") if (a[4] == "bilibili" and rel) else "",
                       "duration": round(a[2] or 0, 1), "summary": clean(summ.get("summary", "")),
                       "key_points": [clean(x) for x in summ.get("key_points", []) or []],
                       "people": [clean(x)[:60] for x in (summ.get("people", []) or [])],
                       "theories": [clean(x)[:60] for x in (summ.get("theories", []) or [])],
                       "memes": [clean(x)[:60] for x in (summ.get("memes", []) or [])],
                       "tags": [clean(x)[:40] for x in (summ.get("tags", []) or [])],
                       "quotes": [clean(x)[:200] for x in summ.get("quotes", []) or []],
                       "tone": summ.get("tone", ""), "thumb": "thumbs/%d.jpg" % aid,
                       "scenes": scenes[:40]})
    json.dump(videos, open(EXPORT / "videos.json", "w", encoding="utf-8"), ensure_ascii=False)
    def ents(kind):
        out = []
        for eid, name, typ, aliases, summary, tags, sources in conn.execute(
                "SELECT id,name,type,aliases,summary,tags,sources FROM entity WHERE type=?", (kind,)):
            out.append({"id": clean(str(eid)), "name": clean(name), "type": typ,
                        "aliases": [clean(x) for x in json.loads(aliases or "[]")], "summary": clean(summary or ""),
                        "tags": json.loads(tags or "[]"), "sources": json.loads(sources or "[]"),
                        "videoRefs": []})
        return out
    def keywords_for(name, aliases):
        kws = []
        for s in [name] + list(aliases or []):
            s = clean(str(s))
            if len(s) >= 2:
                kws.append(s)
            for part in re.split(r"[\s/、,，（）()·\-—]+", s):
                part = part.strip()
                if len(part) >= 2:
                    kws.append(part)
                if len(part) >= 5:  # 长名字再取滑窗子串，提高命中率
                    for i in range(0, len(part) - 3):
                        kws.append(part[i:i + 4])
        seen, out = set(), []
        for k in kws:
            if k not in seen and len(k) >= 2:
                seen.add(k)
                out.append(k)
        return out[:10]

    def mentions(name, aliases, limit=30):
        """按名称/别名/子串在检索块里找提及，按命中关键词数排序"""
        if not name or len(name) < 2:
            return []
        hits = {}
        for kw in keywords_for(name, aliases):
            try:
                cur = conn.execute(
                    "SELECT asset_id, t0, text FROM chunk WHERE asset_id IS NOT NULL AND text LIKE ? "
                    "ORDER BY (CASE kind WHEN 'scene' THEN 0 ELSE 1 END), id LIMIT 20",
                    ("%" + kw + "%",))
            except Exception:
                continue
            for aid, t0, txt in cur:
                key = int(aid)
                rec = hits.setdefault(key, {"aid": key, "t0": float(t0 or 0.0), "text": txt or "", "score": 0})
                rec["score"] += 1
        rows = sorted(hits.values(), key=lambda r: (-r["score"], r["aid"]))
        return [(r["aid"], r["t0"], r["text"]) for r in rows[:limit]]

    def enrich(items, kind):
        for it in items:
            ms = mentions(it["name"], it.get("aliases"))
            quotes = []
            refs = []
            seen = set()
            for aid, t0, txt in ms:
                if aid in seen:
                    continue
                seen.add(aid)
                snip = clean(txt)
                snip = snip.split("。")[0][:160] if kind != "term" else clean(it["summary"])[:200]
                if kind == "theory":
                    quotes.append({"videoId": str(aid), "t": round(t0, 1), "note": snip})
                refs.append(str(aid))
                if len(refs) >= 10:
                    break
            it["videoRefs"] = refs
            it["mentionCount"] = len(refs)
            if kind == "theory":
                it["evidence"] = quotes
                detail = it["summary"]
                if quotes:
                    detail += "\n\n（以下为视频中的相关说法，点击可跳转到对应视频与时间点）"
                it["detail"] = detail
            if kind == "term":
                it["term"] = it["name"]
                d = it["summary"]
                if refs:
                    d += "（在 %d 个视频中被提及）" % len(refs)
                it["definition"] = d
            if kind == "person":
                it["videoRefs"] = refs
        return items

    people = enrich(ents("人物"), "person")
    theories = enrich(ents("理论"), "theory")
    glossary = enrich(ents("术语") + ents("梗"), "term")
    events = []
    for did, title, source, meta_j, body in conn.execute("SELECT id,title,source,meta,body FROM doc WHERE kind='event'"):
        try:
            m = json.loads(meta_j or "{}")
        except Exception:
            m = {}
        events.append({"id": did, "date": m.get("date", ""), "title": title, "summary": clean(body or ""),
                       "people": [], "sources": [source] if source else [], "videoRefs": []})
    bili = []
    for did, title, source, meta_j, body in conn.execute("SELECT id,title,source,meta,body FROM doc WHERE kind='bilibili'"):
        try:
            m = json.loads(meta_j or "{}")
        except Exception:
            m = {}
        bili.append({"id": did, "title": title, "url": source, "summary": clean((body or "")[:600]),
                     "uploader": m.get("uploader"), "duration": m.get("duration"), "views": m.get("view_count")})
    nodes, links, seen = [], [], set()
    for src, dst, typ in conn.execute("SELECT src,dst,type FROM relation"):
        for n in (src, dst):
            if n and n not in seen:
                seen.add(n)
                nodes.append({"id": n, "label": n, "type": "entity"})
        if src and dst:
            links.append({"source": src, "target": dst, "type": typ or "关联"})
    stats = {"videos": len(videos), "hours": round(sum(v["duration"] for v in videos) / 3600, 1),
             "entities": conn.execute("SELECT COUNT(*) FROM entity").fetchone()[0],
             "events": len(events), "glossary": len(glossary), "bilibili": len(bili)}
    json.dump({"title": "李文亚 Wiki", "tagline": "一个互联网亚文化现象的客观记录",
               "stats": stats, "updatedAt": time.strftime("%Y-%m-%d %H:%M")},
              open(EXPORT / "site.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for name, data in (("people", people), ("theories", theories), ("glossary", glossary),
                       ("events", events), ("bilibili", bili), ("graph", {"nodes": nodes, "links": links})):
        json.dump(data, open(EXPORT / (name + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if args.thumbs:
        tdir = ROOT / "site/public/thumbs"
        tdir.mkdir(parents=True, exist_ok=True)
        made = 0
        for v in videos:
            src = sorted(glob.glob(str(DATA / "frames" / str(v["id"]) / "*.jpg")))
            if not src:
                continue
            dst = tdir / ("%s.jpg" % v["id"])
            if dst.exists():
                continue
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src[len(src) // 2],
                            "-vf", "scale=320:-2", "-q:v", "6", str(dst)], capture_output=True)
            made += 1
        print("[export] 缩略图生成:", made)
    print("[export] 导出完成:", stats)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "embed", "export", "query", "stats"])
    ap.add_argument("--text", default="李文亚的黑体生物理论是什么")
    ap.add_argument("--thumbs", action="store_true")
    args = ap.parse_args()
    {"build": cmd_build, "embed": cmd_embed, "stats": cmd_stats, "query": cmd_query, "export": cmd_export}[args.cmd](args)


if __name__ == "__main__":
    main()