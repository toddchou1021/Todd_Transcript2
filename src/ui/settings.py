from __future__ import annotations

import base64

import webview

from .. import APP_NAME, APP_VERSION
from ..paths import ICON_PATH, LOGO_PATH


def _logo_data_uri() -> str:
    data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def settings_html() -> str:
    logo = _logo_data_uri()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{APP_NAME}</title>
<style>
:root {{
  --bg:#121314; --top:#0d0e0f; --panel:#1b1d1f; --panel2:#202326; --line:#344044;
  --text:#e7ecef; --muted:#9facb2; --dim:#66767d; --accent:#55d7ff; --danger:#ffb4ab;
}}
* {{ box-sizing:border-box; }}
html, body {{ height:100%; margin:0; overflow:hidden; }}
body {{ background:var(--bg); color:var(--text); font-family:Inter, "Segoe UI", Arial, sans-serif; }}
button, input, select {{ font:inherit; }}
button {{ cursor:pointer; }}
.app {{ height:100%; display:grid; grid-template-columns:152px 1fr; grid-template-rows:68px 1fr; }}
header {{ grid-column:1 / 3; display:flex; align-items:center; justify-content:space-between; padding:0 34px; background:var(--top); border-bottom:1px solid var(--line); }}
.brand {{ display:flex; align-items:center; gap:14px; min-width:0; }}
.brand img {{ width:46px; height:46px; object-fit:contain; }}
.title {{ font-size:21px; font-weight:700; text-transform:uppercase; white-space:nowrap; }}
.version {{ color:var(--dim); font:12px/1.4 Consolas, monospace; margin-top:3px; }}
.status {{ display:flex; align-items:center; gap:10px; color:var(--muted); font:600 12px/1 Consolas, monospace; text-transform:uppercase; }}
.dot {{ width:8px; height:8px; background:var(--dim); }}
.dot.live {{ background:var(--accent); box-shadow:0 0 14px rgba(85,215,255,.7); }}
main {{ grid-column:2; grid-row:2; overflow:auto; padding:30px 34px; }}
.inner {{ max-width:1060px; margin:0 auto; }}
.page {{ display:none; }}
.page.active {{ display:block; }}
.headline {{ font-size:28px; line-height:1.2; font-weight:650; border-left:4px solid var(--accent); padding-left:14px; margin:0 0 24px; }}
.grid {{ display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:20px; }}
.panel {{ background:var(--panel); border:1px solid var(--line); padding:22px; }}
.span-7 {{ grid-column:span 7; }}
.span-5 {{ grid-column:span 5; }}
.span-12 {{ grid-column:span 12; }}
h2 {{ margin:0 0 18px; color:#9ce9ff; font-size:21px; font-weight:550; }}
.row {{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:15px 0; border-bottom:1px solid var(--line); }}
.row:last-child {{ border-bottom:0; }}
.row-title {{ font-size:16px; }}
.row-desc {{ color:var(--dim); font-size:13px; line-height:1.45; margin-top:4px; }}
.controls {{ display:flex; flex-wrap:wrap; gap:10px; justify-content:flex-end; }}
.btn, select, input {{ min-height:36px; border:1px solid var(--line); background:var(--panel2); color:var(--text); padding:0 12px; }}
.btn {{ background:transparent; color:var(--muted); text-transform:uppercase; font:600 12px/1 Consolas, monospace; }}
.btn:hover {{ background:var(--accent); border-color:var(--accent); color:#001f25; }}
.btn.danger:hover {{ background:var(--danger); border-color:var(--danger); color:#2a0000; }}
.hotkey {{ min-width:110px; text-align:center; font:500 13px/1 Consolas, monospace; }}
.metric-row {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.metric {{ border:1px solid var(--line); background:var(--panel2); padding:16px; }}
.metric-num {{ font-size:32px; font-weight:700; }}
.metric-label {{ color:var(--dim); font:600 12px/1.4 Consolas, monospace; text-transform:uppercase; }}
.model-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
.model {{ border:1px solid var(--line); background:var(--panel2); padding:16px; min-height:112px; }}
.model-name {{ font-size:17px; line-height:1.3; margin-bottom:8px; }}
.model-meta {{ color:var(--dim); font-size:13px; line-height:1.45; }}
.model-state {{ margin-top:12px; color:var(--accent); font:600 12px/1 Consolas, monospace; text-transform:uppercase; }}
.list {{ display:grid; gap:10px; }}
.item {{ border:1px solid var(--line); background:var(--panel2); padding:14px; position:relative; }}
.item-actions {{ position:absolute; top:10px; right:10px; display:flex; gap:6px; }}
.item-meta {{ color:var(--dim); font:12px/1.4 Consolas, monospace; margin-bottom:8px; padding-right:150px; }}
.item-text {{ line-height:1.55; padding-right:130px; white-space:pre-wrap; }}
.empty {{ color:var(--dim); border:1px dashed var(--line); padding:22px; text-align:center; }}
.add-row {{ display:grid; grid-template-columns:1fr auto; gap:10px; margin-bottom:16px; }}
nav {{ grid-column:1; grid-row:2; display:flex; flex-direction:column; background:var(--top); border-right:1px solid var(--line); }}
.nav-item {{ width:100%; min-height:66px; border:0; border-left:3px solid transparent; background:transparent; color:var(--dim); text-transform:uppercase; font:600 12px/1.2 Consolas, monospace; }}
.nav-item.active {{ color:#9ce9ff; border-left-color:var(--accent); }}
@media (max-width:860px) {{ .app {{ grid-template-columns:122px 1fr; }} header, main {{ padding-left:20px; padding-right:20px; }} .grid {{ grid-template-columns:1fr; }} .span-7,.span-5,.span-12 {{ grid-column:span 1; }} .metric-row,.model-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="app">
<header>
  <div class="brand">
    <img src="{logo}" alt="">
    <div><div class="title">{APP_NAME}</div><div class="version" id="version">{APP_VERSION}</div></div>
  </div>
  <div class="status"><span id="dot" class="dot"></span><span id="state">Idle</span></div>
</header>
<main>
<div class="inner">
  <section id="page-control" class="page active">
    <div class="headline">Speech Control</div>
    <div class="grid">
      <div class="panel span-7">
        <h2>Recording</h2>
        <div class="row">
          <div><div class="row-title">Transcribe</div><div class="row-desc">Starts recording, then inserts recognized text into the active app.</div></div>
          <div class="controls"><button class="btn hotkey" id="key-transcribe" onclick="recordHotkey('transcribe')"></button><button class="btn" onclick="startMode('transcribe')">Start</button></div>
        </div>
        <div class="row">
          <div><div class="row-title">Translate</div><div class="row-desc">Records speech and asks the backend to translate to the selected target language.</div></div>
          <div class="controls"><button class="btn hotkey" id="key-translate" onclick="recordHotkey('translate')"></button><button class="btn" onclick="startMode('translate')">Start</button></div>
        </div>
        <div class="row">
          <div><div class="row-title">Stop Recording</div><div class="row-desc">Esc also stops the active recording.</div></div>
          <button class="btn danger" onclick="stopRecording()">Stop</button>
        </div>
        <div class="row">
          <div><div class="row-title">Realtime</div><div class="row-desc">Open live transcription or live translation windows.</div></div>
          <div class="controls"><button class="btn" onclick="openRealtimeASR()">ASR</button><button class="btn" onclick="openRealtimeTranslate()">Translate</button></div>
        </div>
      </div>
      <div class="panel span-5">
        <h2>Configuration</h2>
        <div class="row">
          <div><div class="row-title">Input Source</div><div class="row-desc">Microphone, system audio, or mixed capture.</div></div>
          <select id="input-source" onchange="setConfig('recorder.input_mode', this.value)"><option value="microphone">Microphone</option><option value="system_audio">System Audio</option><option value="both">Microphone + System</option></select>
        </div>
        <div class="row">
          <div><div class="row-title">Target Language</div><div class="row-desc">Used for translation mode.</div></div>
          <select id="target-language" onchange="setConfig('target_language', this.value)"><option value="zh">Chinese</option><option value="en">English</option><option value="ja">Japanese</option><option value="fr">French</option><option value="de">German</option><option value="ko">Korean</option><option value="es">Spanish</option></select>
        </div>
        <div class="row">
          <div><div class="row-title">Text Polishing</div><div class="row-desc">Let the backend polish ASR output when supported.</div></div>
          <select id="postprocess" onchange="setConfig('postprocess', this.value === 'true')"><option value="true">On</option><option value="false">Off</option></select>
        </div>
      </div>
      <div class="panel span-12">
        <h2>Local Model Stack</h2>
        <div class="model-grid">
          <div class="model">
            <div class="model-name">Whisper Large v3 Turbo</div>
            <div class="model-meta">Transcription · local Transformers pipeline</div>
            <div class="model-state">ASR</div>
          </div>
          <div class="model">
            <div class="model-name">Qwen 3.5 4B</div>
            <div class="model-meta">Transcript cleanup and translation · Ollama</div>
            <div class="model-state">Thinking Off</div>
          </div>
          <div class="model">
            <div class="model-name">OpenAI Realtime</div>
            <div class="model-meta">Optional realtime windows when configured</div>
            <div class="model-state">Optional</div>
          </div>
        </div>
      </div>
      <div class="panel span-12">
        <div class="metric-row">
          <div class="metric"><div class="metric-label">Today</div><span class="metric-num" id="today-words">0</span> words <div class="metric-label"><span id="today-count">0</span> sessions</div></div>
          <div class="metric"><div class="metric-label">Total</div><span class="metric-num" id="total-words">0</span> words <div class="metric-label"><span id="total-count">0</span> sessions</div></div>
        </div>
      </div>
    </div>
  </section>
  <section id="page-history" class="page">
    <div class="headline">Recognition History</div>
    <div class="panel"><div class="row" style="padding-top:0"><h2 style="margin:0">Recent Output</h2><button class="btn danger" onclick="clearHistory()">Clear</button></div><div id="history-list" class="list"></div></div>
  </section>
  <section id="page-hotwords" class="page">
    <div class="headline">Hotwords</div>
    <div class="panel"><h2>Custom Vocabulary</h2><div class="add-row"><input id="hotword-input" placeholder="Add product names, people, acronyms..." onkeydown="if(event.key==='Enter')addHotword()"><button class="btn" onclick="addHotword()">Add</button></div><div id="hotword-list" class="list"></div></div>
  </section>
  <section id="page-settings" class="page">
    <div class="headline">Runtime Settings</div>
    <div class="grid">
      <div class="panel span-7"><h2>Backend</h2><div class="row"><div><div class="row-title">Pipeline URL</div><div class="row-desc">Local WebSocket endpoint used by developer mode.</div></div></div><div class="add-row"><input id="pipeline-url"><button class="btn" onclick="savePipelineUrl()">Save</button></div></div>
      <div class="panel span-5"><h2>OpenAI Realtime</h2><div class="row"><div><div class="row-title">API Key</div><div class="row-desc" id="openai-key-status">Stored locally in config.yaml.</div></div></div><div class="add-row"><input id="openai-api-key" type="password" placeholder="sk-..."><button class="btn" onclick="saveOpenAIKey()">Save</button></div></div>
    </div>
  </section>
</div>
</main>
<nav>
  <button class="nav-item active" data-page="control">Control</button>
  <button class="nav-item" data-page="history">History</button>
  <button class="nav-item" data-page="hotwords">Hotwords</button>
  <button class="nav-item" data-page="settings">Settings</button>
</nav>
</div>
<script>
let recordingHotkey = null;
let pressed = new Set();
document.querySelectorAll('.nav-item').forEach(btn => btn.addEventListener('click', () => {{
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('page-' + btn.dataset.page).classList.add('active');
  if (btn.dataset.page === 'history') loadHistory();
  if (btn.dataset.page === 'hotwords') loadHotwords();
  if (btn.dataset.page === 'control') loadStats();
}}));
function esc(s) {{ return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
function fmtKey(combo) {{ return combo ? combo.split('+').map(x => x.charAt(0).toUpperCase() + x.slice(1)).join('+') : 'Set key'; }}
function keyName(e) {{
  if (e.key === 'Control') return 'ctrl'; if (e.key === 'Alt') return 'alt'; if (e.key === 'Shift') return 'shift'; if (e.key === 'Meta') return 'win';
  if (/^F\\d+$/.test(e.key)) return e.key.toLowerCase(); if (e.code.startsWith('Key')) return e.code.slice(3).toLowerCase(); if (e.code.startsWith('Digit')) return e.code.slice(5);
  return {{' ':'space','Enter':'enter','Tab':'tab','Backspace':'backspace','Delete':'delete','`':'`'}}[e.key] || e.key.toLowerCase();
}}
function recordHotkey(mode) {{
  recordingHotkey = mode; pressed.clear();
  document.getElementById('key-' + mode).textContent = 'Press keys...';
  document.addEventListener('keydown', onKeyDown, true); document.addEventListener('keyup', onKeyUp, true);
}}
function onKeyDown(e) {{ if (!recordingHotkey) return; e.preventDefault(); pressed.add(keyName(e)); }}
async function onKeyUp(e) {{
  if (!recordingHotkey || pressed.size === 0) return;
  e.preventDefault();
  const order = ['ctrl','win','alt','shift'];
  const combo = order.filter(k => pressed.has(k)).concat([...pressed].filter(k => !order.includes(k)).sort()).join('+');
  const mode = recordingHotkey; recordingHotkey = null; pressed.clear();
  document.removeEventListener('keydown', onKeyDown, true); document.removeEventListener('keyup', onKeyUp, true);
  document.getElementById('key-' + mode).textContent = fmtKey(combo);
  await pywebview.api.save_hotkey(mode, combo);
}}
async function startMode(mode) {{ const r = await pywebview.api.start_recording(mode); if (!r.ok) alert(r.error || 'Start failed'); }}
async function stopRecording() {{ const r = await pywebview.api.stop_recording(); if (!r.ok && r.error) alert(r.error); }}
async function openRealtimeASR() {{ const r = await pywebview.api.open_realtime_asr(); if (r && r.ok === false) alert(r.error || 'Failed to open realtime ASR'); }}
async function openRealtimeTranslate() {{ const r = await pywebview.api.open_realtime_translate(); if (r && r.ok === false) alert(r.error || 'Failed to open realtime translation'); }}
async function setConfig(key, value) {{ await pywebview.api.set_config(key, value); }}
async function savePipelineUrl() {{ await setConfig('pipeline_api.url', document.getElementById('pipeline-url').value.trim()); }}
async function saveOpenAIKey() {{ const el = document.getElementById('openai-api-key'); if (el.value.trim()) await setConfig('openai.api_key', el.value.trim()); el.value=''; init(); }}
async function loadStats() {{
  const s = await pywebview.api.get_stats();
  document.getElementById('today-words').textContent = (s.today_words || 0).toLocaleString();
  document.getElementById('today-count').textContent = (s.today_count || 0).toLocaleString();
  document.getElementById('total-words').textContent = (s.total_words || 0).toLocaleString();
  document.getElementById('total-count').textContent = (s.total_count || 0).toLocaleString();
}}
async function loadHistory() {{
  const h = await pywebview.api.get_history_page(0);
  const el = document.getElementById('history-list');
  if (!h.records.length) {{ el.innerHTML = '<div class="empty">No history yet.</div>'; return; }}
  el.innerHTML = h.records.map(r => '<div class="item"><div class="item-actions"><button class="btn" onclick="copyText(`'+esc(r.final_text)+'`)">Copy</button><button class="btn danger" onclick="deleteHistory(`'+esc(r.timestamp)+'`)">Delete</button></div><div class="item-meta">'+esc(r.timestamp)+' · '+esc(r.mode || '')+'</div><div class="item-text">'+esc(r.final_text)+'</div></div>').join('');
}}
async function copyText(text) {{ await pywebview.api.copy_text(text); }}
async function deleteHistory(ts) {{ await pywebview.api.delete_history_by_ts(ts); loadHistory(); loadStats(); }}
async function clearHistory() {{ if (confirm('Delete all saved recognition history?')) {{ await pywebview.api.clear_history(); loadHistory(); loadStats(); }} }}
async function loadHotwords() {{
  const words = await pywebview.api.get_hotwords();
  const el = document.getElementById('hotword-list');
  if (!words.length) {{ el.innerHTML = '<div class="empty">No hotwords yet.</div>'; return; }}
  el.innerHTML = words.map(w => '<div class="item"><div class="item-actions"><button class="btn danger" onclick="removeHotword(`'+esc(w)+'`)">Remove</button></div><div class="item-text">'+esc(w)+'</div></div>').join('');
}}
async function addHotword() {{ const input = document.getElementById('hotword-input'); if (input.value.trim()) await pywebview.api.add_hotword(input.value.trim()); input.value=''; loadHotwords(); }}
async function removeHotword(w) {{ await pywebview.api.remove_hotword(w); loadHotwords(); }}
async function pollStatus() {{
  const s = await pywebview.api.get_status();
  document.getElementById('state').textContent = s.status || 'Idle';
  document.getElementById('dot').className = s.recording ? 'dot live' : 'dot';
  setTimeout(pollStatus, 400);
}}
async function init() {{
  const cfg = await pywebview.api.get_config();
  document.getElementById('key-transcribe').textContent = fmtKey(cfg.hotkey?.transcribe);
  document.getElementById('key-translate').textContent = fmtKey(cfg.hotkey?.translate);
  document.getElementById('input-source').value = cfg.recorder?.input_mode || 'microphone';
  document.getElementById('target-language').value = cfg.target_language || 'zh';
  document.getElementById('postprocess').value = String(cfg.postprocess !== false);
  document.getElementById('pipeline-url').value = cfg.pipeline_api?.url || '';
  document.getElementById('openai-key-status').textContent = cfg.openai?.has_api_key ? 'API key saved locally in config.yaml.' : 'No API key saved.';
  loadStats(); pollStatus();
}}
window.addEventListener('pywebviewready', init);
</script>
</body>
</html>"""


class SettingsWindow:
    def __init__(self, api):
        self.api = api
        self.window = None

    def start(self) -> None:
        self.window = webview.create_window(
            APP_NAME,
            html=settings_html(),
            js_api=self.api,
            width=1120,
            height=760,
            min_size=(860, 620),
            background_color="#121314",
            text_select=True,
        )
        webview.start(icon=str(ICON_PATH), debug=False)
