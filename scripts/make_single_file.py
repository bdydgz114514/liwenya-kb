#!/usr/bin/env python3
# 生成「单文件版」Wiki：把全部数据与样式内联进一个 HTML，双击即可离线浏览（国内用户最方便）
import json, re, sys
from pathlib import Path

EXPORT = Path("/root/dsh/liwenya-kb/kb/export")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/output_videos/李文亚Wiki_单文件版.html")

def load(name, default):
    p = EXPORT / (name + ".json")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

site = load("site", {})
videos = load("videos", [])
people = load("people", [])
theories = load("theories", [])
events = load("events", [])
glossary = load("glossary", [])
graph = load("graph", {})
bili = load("bilibili", [])
textbook = load("textbook", {})

data = {
    "site": site, "videos": videos, "people": people, "theories": theories,
    "events": events, "glossary": glossary, "graph": graph, "bilibili": bili, "textbook": textbook,
}
DATA_JSON = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

CSS = """
:root{--bg:#0b0b0f;--bg2:#111318;--card:#16181f;--line:#262a35;--fg:#e8eaf0;--muted:#9aa2b1;--accent:#e23a2e;--accent2:#ff6a4d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 system-ui,-apple-system,'Segoe UI','Microsoft YaHei',sans-serif}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
header{position:sticky;top:0;z-index:20;background:linear-gradient(180deg,rgba(11,11,15,.98),rgba(11,11,15,.86));backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
.top{display:flex;align-items:center;gap:18px;padding:14px 0;flex-wrap:wrap}
.brand{font-weight:800;letter-spacing:.5px;font-size:20px}.brand span{color:var(--accent)}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
nav a{padding:7px 13px;border-radius:9px;color:var(--muted);font-size:14px}nav a:hover{background:#1b1e26;color:var(--fg);text-decoration:none}
nav a.on{background:var(--accent);color:#fff}
.hero{padding:54px 0 30px;border-bottom:1px solid var(--line);background:radial-gradient(900px 380px at 15% -10%,rgba(226,58,46,.20),transparent)}
.hero h1{margin:0 0 10px;font-size:clamp(30px,5vw,52px);line-height:1.12;font-weight:850}
.hero p{color:var(--muted);max-width:760px;margin:0 0 22px}
.stats{display:flex;gap:12px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:120px}
.stat b{display:block;font-size:22px;color:#fff}.stat i{color:var(--muted);font-size:12px;font-style:normal}
section{padding:34px 0}
h2{font-size:24px;margin:0 0 6px}.sub{color:var(--muted);font-size:14px;margin:0 0 20px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(268px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;transition:.18s}
.card:hover{transform:translateY(-3px);border-color:#3a4050;box-shadow:0 14px 34px rgba(0,0,0,.42)}
.tag{display:inline-block;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:2px 9px;margin:3px 4px 0 0}
.meta{color:var(--muted);font-size:12px;margin-top:8px}
input[type=search],input[type=text]{width:100%;padding:13px 15px;border-radius:11px;border:1px solid var(--line);background:#0f1117;color:var(--fg);font-size:15px;outline:none}
input:focus{border-color:var(--accent)}
.btn{display:inline-block;padding:9px 16px;border-radius:10px;border:1px solid var(--line);background:#151821;color:var(--fg);cursor:pointer;font-size:14px}
.btn:hover{border-color:var(--accent);color:#fff}
.empty{color:var(--muted);padding:26px 0}
.quote{border-left:2px solid var(--accent);padding:6px 0 6px 12px;margin:8px 0;color:#cfd4de;font-size:14px}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:13px;padding:26px 0;margin-top:40px}
.kbd{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:#1a1d26;border:1px solid var(--line);border-radius:6px;padding:1px 6px}
@media(max-width:720px){nav{margin-left:0;width:100%}.hero{padding:34px 0 22px}}
"""

JS = """
const D=window.WIKI_DATA;
const $=(s,r=document)=>r.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const vid=x=>'#/video/'+x.id;
const fmt=n=>String(n).replace(/\B(?=(\d{3})+(?!\d))/g,',');
const dur=s=>{s=Math.round(s||0);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
const TYPE={video:'视频',person:'人物',theory:'理论',event:'事件',term:'词条'};

function route(){const h=location.hash.replace(/^#\/?/,'')||'home';const [page,id]=h.split('/');render(page,id)}
window.addEventListener('hashchange',route);

function nav(page){return ['home','people','theories','events','glossary','videos'].map(p=>{const t={home:'首页',people:'人物志',theories:'理论体系',events:'事件年表',glossary:'梗词典',videos:'视频库'}[p];return '<a href="#/'+p+'" class="'+(p===page?'on':'')+'">'+t+'</a>'}).join('')}

function home(){
 const s=D.site.stats||{};
 const pick=[...D.theories].slice(0,3).concat([...D.people].slice(0,3));
 const latest=[...D.events].sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,4);
 return '<div class="hero"><div class="wrap"><h1>'+esc(D.site.title||'李文亚 Wiki')+'</h1><p>'+esc(D.site.tagline||'')+'　·　单文件离线版：全部内容已打包在本 HTML 内，无需联网、无需服务器，双击即看。</p>'
  +'<div class="stats">'+[['视频',fmt(s.videos||0)],['小时',s.hours||0],['实体',s.entities||0],['事件',s.events||0],['词条',s.glossary||0],['B站',s.bilibili||0]].map(x=>'<div class="stat"><b>'+x[1]+'</b><i>'+x[0]+'</i></div>').join('')+'</div></div></div>'
  +'<section class="wrap"><h2>在线全文检索请用完整版</h2><p class="sub">单文件版内置「标题 / 摘要 / 标签 / 人物 / 理论」的即时搜索（右上角输入框），逐场景台词与画面文字的全文检索在完整版站点中提供。</p></section>'
  +'<section class="wrap"><h2>理论体系</h2><p class="sub">共 '+D.theories.length+' 条，附视频证据锚点</p><div class="grid">'+D.theories.slice(0,6).map(t=>'<a class="card" href="#/theory/'+esc(t.id)+'"><b>'+esc(t.name)+'</b><div class="meta">'+(t.mentionCount||0)+' 个视频提及</div><p style="color:#b9c0cd;font-size:14px">'+esc((t.summary||'').slice(0,90))+'…</p></a>').join('')+'</div></section>'
  +'<section class="wrap"><h2>最新事件</h2><div class="grid">'+latest.map(e=>'<div class="card"><div class="meta">'+esc(e.date||'')+'</div><b>'+esc(e.title)+'</b><p style="color:#b9c0cd;font-size:14px">'+esc((e.summary||'').slice(0,120))+'</p></div>').join('')+'</div></section>';
}

function listPeople(){return '<section class="wrap"><h2>人物志 · '+D.people.length+' 位</h2><p class="sub">李文亚及其相关人物；「视频」列为该人物在归档视频中被提及的条目数</p><div class="grid">'+D.people.map(p=>'<div class="card"><b>'+esc(p.name)+'</b>'+(p.aliases&&p.aliases.length?'<div class="meta">别名：'+esc(p.aliases.join('、'))+'</div>':'')+'<p style="color:#b9c0cd;font-size:14px">'+esc((p.summary||'').slice(0,150))+'</p><div class="meta">'+(p.videoRefs||[]).length+' 个视频提及</div></div>').join('')+'</div></section>'}
function theoryDetail(id){const t=D.theories.find(x=>x.id===id);if(!t)return '<section class="wrap"><div class="empty">未找到该理论</div></section>';
 const tbk=D.textbook&&D.textbook[t.name]?D.textbook[t.name]:null;
 const tb=tbk?('<div style="margin-top:14px"><b>教科书级讲解</b>'+esc(tbk.intro||'')+(tbk.sections||[]).map(s=>'<div style="margin-top:10px"><b>'+esc(s.h||'')+'</b>'+(s.p||[]).map(x=>'<p style="color:#c3c9d6;font-size:14px">'+esc(x)+'</p>').join('')+(s.list||[]).map(x=>'<div style="color:#c3c9d6;font-size:14px">· '+esc(x)+'</div>').join('')+(s.table||[]).map(r=>'<div style="font-size:13px;color:#9aa2b1">'+esc(r.a)+'：'+esc(r.b)+'　→　'+esc(r.c)+'</div>').join('')+'</div>').join('')+(tbk.formulas||[]).map(f=>'<div class="quote">'+esc(f.tex||'')+'</div>').join('')+'</div>'):'';
 const ev=(t.evidence||[]).map(e=>'<div class="quote">'+esc(e.note||'')+'<div class="meta">视频 '+esc(e.videoId)+' @ '+e.t+'s</div></div>').join('');
 return '<section class="wrap"><div class="meta"><a href="#/theories">← 理论体系</a></div><h2>'+esc(t.name)+'</h2>'+(t.aliases&&t.aliases.length?'<p class="sub">别名：'+esc(t.aliases.join('、'))+'</p>':'')
  +'<div class="card"><b>概述</b><p>'+esc(t.summary||'')+'</p>'+(ev?'<b>视频证据锚点</b>'+ev:'')+tb+'</div>'
  +'<p class="sub" style="margin-top:14px">来源：'+(t.sources||[]).map(s=>'<a href="'+esc(s)+'" target="_blank" rel="noreferrer">'+esc(String(s).slice(0,60))+'…</a>').join(' ')+'</p></section>'}
function listTheories(){return '<section class="wrap"><h2>理论体系 · '+D.theories.length+' 条</h2><p class="sub">点开可看概述与该理论在视频中的证据锚点</p><div class="grid">'+D.theories.map(t=>'<a class="card" href="#/theory/'+esc(t.id)+'"><b>'+esc(t.name)+'</b><p style="color:#b9c0cd;font-size:14px">'+esc((t.summary||'').slice(0,110))+'</p><div class="meta">'+(t.mentionCount||0)+' 个视频提及</div></a>').join('')+'</div></section>'}
function listEvents(){const years={};(D.events||[]).forEach(e=>{const y=String(e.date||'').slice(0,4)||'未知';(years[y]=years[y]||[]).push(e)});
 return '<section class="wrap"><h2>事件年表 · '+D.events.length+' 条</h2>'+Object.keys(years).sort().map(y=>'<h3 style="margin-top:26px">'+esc(y)+'</h3><div class="grid">'+years[y].map(e=>'<div class="card"><b>'+esc(e.title)+'</b><p style="color:#b9c0cd;font-size:14px">'+esc((e.summary||'').slice(0,160))+'</p><div class="meta">'+esc(e.date||'')+'</div></div>').join('')+'</div>').join('')+'</section>'}
function listGlossary(){return '<section class="wrap"><h2>梗词典 · '+D.glossary.length+' 条</h2><p class="sub">视频内自称、社区用语与网络迷因的对照表</p><div class="grid">'+D.glossary.map(g=>'<div class="card"><b>'+esc(g.term||g.name)+'</b><p style="color:#b9c0cd;font-size:14px">'+esc(g.definition||g.summary||'')+'</p></div>').join('')+'</div></section>'}

let vlimit=60;
function listVideos(){
 const s=D.videos.slice(0,vlimit);
 return '<section class="wrap"><h2>视频库 · '+D.videos.length+' 个</h2><p class="sub">按系列归档；点开看摘要、要点、标签与该视频理解结果</p>'
  +'<div class="grid">'+s.map(v=>'<a class="card" href="'+vid(v)+'"><b>'+esc(v.title)+'</b><div class="meta">'+esc(v.series||'')+' · '+dur(v.duration)+'</div><p style="color:#b9c0cd;font-size:13px">'+esc((v.summary||'（暂无摘要）').slice(0,100))+'</p></a>').join('')+'</div>'
  +(D.videos.length>vlimit?'<p style="margin-top:18px"><button class="btn" onclick="vlimit+=120;render(&#39;videos&#39;)">加载更多（已显示 '+vlimit+' / '+D.videos.length+'）</button></p>':'')+'</section>'}
function videoDetail(id){const v=D.videos.find(x=>String(x.id)===String(id));if(!v)return '<section class="wrap"><div class="empty">未找到该视频</div></section>';
 const tags=(v.tags||[]).map(t=>'<span class="tag">'+esc(t)+'</span>').join('');
 const kp=(v.key_points||[]).map(k=>'<li>'+esc(k)+'</li>').join('');
 const sc=(v.scenes||[]).slice(0,14).map(s=>'<div class="quote"><div class="meta">'+s.t0+'s – '+s.t1+'s</div>'+esc((s.dialogue||[]).join(' / ').slice(0,180))+(s.visual&&s.visual[0]?'<div class="meta">画面：'+esc((s.visual[0].scene||'').slice(0,90))+'</div>':'')+'</div>').join('');
 return '<section class="wrap"><div class="meta"><a href="#/videos">← 视频库</a></div><h2>'+esc(v.title)+'</h2><p class="sub">'+esc(v.series||'')+' · '+dur(v.duration)+' · 编号 #'+esc(v.id)+'</p>'
  +'<div class="card"><b>摘要</b><p>'+esc(v.summary||'（暂无摘要）')+'</p>'+(kp?'<b>要点</b><ul>'+kp+'</ul>':'')+tags+'</div>'
  +(sc?'<div class="card" style="margin-top:14px"><b>场景理解结果（前 '+Math.min(14,(v.scenes||[]).length)+' 段）</b>'+sc+'</div>':'')+'</section>'}

function search(q){q=(q||'').trim();if(!q)return '';const hit=[];
 D.videos.forEach(v=>{const s=[v.title,v.summary,(v.tags||[]).join(' '),(v.people||[]).join(' '),(v.theories||[]).join(' ')].join(' ');if(s.includes(q))hit.push(['video',v.id,v.title,(v.summary||'').slice(0,80)])});
 D.people.forEach(p=>{if(((p.name||'')+(p.summary||'')+(p.aliases||[]).join('')).includes(q))hit.push(['person',p.id,p.name,(p.summary||'').slice(0,80)])});
 D.theories.forEach(t=>{if(((t.name||'')+(t.summary||'')).includes(q))hit.push(['theory',t.id,t.name,(t.summary||'').slice(0,80)])});
 D.glossary.forEach(g=>{if(((g.term||'')+(g.definition||'')).includes(q))hit.push(['term',g.id,g.term||g.name,(g.definition||'').slice(0,80)])});
 if(!hit.length)return '<section class="wrap"><div class="empty">没有匹配「'+esc(q)+'」的内容</div></section>';
 return '<section class="wrap"><h2>搜索「'+esc(q)+'」· '+hit.length+' 条</h2><div class="grid">'+hit.slice(0,200).map(h=>'<a class="card" href="#/'+(h[0]==='video'?'video':h[0]==='theory'?'theory':'x')+'/'+esc(h[1])+'"><span class="tag">'+TYPE[h[0]]+'</span><b>'+esc(h[2])+'</b><p style="color:#b9c0cd;font-size:13px">'+esc(h[3])+'</p></a>').join('')+'</div></section>'}

function render(page,id){
 const app=$('#app');let html='';
 if(page==='people')html=listPeople();else if(page==='theories')html=listTheories();else if(page==='theory')html=theoryDetail(decodeURIComponent(id||''));
 else if(page==='events')html=listEvents();else if(page==='glossary')html=listGlossary();else if(page==='videos')html=listVideos();
 else if(page==='video')html=videoDetail(id);else html=home();
 app.innerHTML=html;document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#/'+page));
 window.scrollTo({top:0,behavior:'instant'});
}
document.addEventListener('DOMContentLoaded',()=>{
 $('#q').addEventListener('input',e=>{const v=e.target.value.trim();if(v){$('#app').innerHTML=search(v)}else{route()}});
 route();
});
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>李文亚 Wiki · 单文件离线版</title>
<meta name="description" content="李文亚 Wiki 单文件离线版：1206 个视频的多模态理解、理论体系、事件年表与梗词典，双击即看，无需联网。">
<style>@@CSS@@</style>
</head>
<body>
<header><div class="wrap top"><div class="brand">文 <span>李文亚</span> WIKI</div>
<input id="q" type="search" placeholder="搜索视频 / 人物 / 理论 / 词条…（中文子串）" style="max-width:320px;margin-left:auto">
<nav>@@NAV@@</nav></div></header>
<main id="app"></main>
<footer><div class="wrap">单文件离线版 · 数据版本 @@DATE@@ · 共 @@NV@@ 个视频 / @@NH@@ 小时<br>
内容为公开资料的归档与结构化整理，站方口径：社群虚构创作，不对任何主张作真实性背书；已剔除住址、健康等私密信息。</div></footer>
<script>window.WIKI_DATA=@@DATA@@;</script>
<script>@@JS@@</script>
</body></html>
"""

nav_html = '<a href="#/home" class="on">首页</a><a href="#/people">人物志</a><a href="#/theories">理论体系</a><a href="#/events">事件年表</a><a href="#/glossary">梗词典</a><a href="#/videos">视频库</a>'
mapping = {
    "CSS": CSS, "JS": JS, "NAV": nav_html, "DATA": DATA_JSON,
    "DATE": str(site.get("updatedAt", "")), "NV": str(len(videos)),
    "NH": str((site.get("stats") or {}).get("hours", "")),
}
html = re.sub(r"@@([A-Z]+)@@", lambda m: mapping.get(m.group(1), m.group(0)), HTML)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print("[single] 已生成 %s （%.2f MB）" % (OUT, OUT.stat().st_size / 1048576))