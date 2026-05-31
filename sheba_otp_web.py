#!/usr/bin/env python3
"""
Sheba OTP Sender — Web UI
Deploy on Render as a Python web service.
Environment variables required:
  ADMIN_PASSWORD  — your chosen password to access the tool
"""

import os
import time
import json
import logging
import requests
from flask import Flask, render_template_string, request, jsonify, session
from functools import wraps
from datetime import timedelta

# ── Config ──────────────────────────────────────────────────────────────────────
APP_ID       = "8329815A6D1AE6DD"
GENERATE_URL = f"https://api-accounts.sheba.xyz/api/v1/accountkit/generate/token?app_id={APP_ID}"
SHOOT_URL    = "https://accountkit.sheba.xyz/api/shoot-otp"
VALIDATE_URL = "https://accountkit.sheba.xyz/api/validate-otp"
GATEWAY_URL  = "https://api-gateway.sheba.xyz/v1/continue-with-kit"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DELAY_SECONDS  = float(os.environ.get("DELAY_SECONDS", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.permanent_session_lifetime = timedelta(hours=12)

# ── Helpers ──────────────────────────────────────────────────────────────────────

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Accept": "application/json",
}

def get_fresh_token():
    """Always fetch a fresh api_token before each OTP."""
    try:
        r = requests.get(GENERATE_URL, headers=HEADERS, timeout=10)
        data = r.json()
        if data.get("code") == 200:
            token = data.get("token")
            log.info(f"Fresh token obtained: {token[:20]}...")
            return token
        log.error(f"Token generation failed: {data}")
        return None
    except Exception as e:
        log.error(f"Token fetch error: {e}")
        return None

def shoot_otp(mobile, api_token):
    """Send OTP to a mobile number."""
    try:
        payload = {
            "mobile": mobile if mobile.startswith("+") else f"+88{mobile}",
            "app_id": APP_ID,
            "api_token": api_token,
        }
        r = requests.post(SHOOT_URL, headers=HEADERS, json=payload, timeout=10)
        data = r.json()
        log.info(f"shoot-otp [{mobile}]: {data}")
        if data.get("message") == "Good.":
            return True, data.get("can_retry_after", 150)
        return False, data.get("message", "Unknown error")
    except Exception as e:
        log.error(f"shoot-otp error: {e}")
        return False, str(e)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Routes ────────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sheba OTP Sender</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Syne:wght@400;700;800&display=swap');

  :root {
    --bg: #08090d;
    --surface: #0f1117;
    --border: #1e2130;
    --accent: #00e5a0;
    --accent2: #7c6af7;
    --red: #ff4d6d;
    --text: #e2e8f0;
    --muted: #4a5568;
    --mono: 'JetBrains Mono', monospace;
    --sans: 'Syne', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
      radial-gradient(ellipse 60% 40% at 20% 20%, rgba(0,229,160,0.04) 0%, transparent 60%),
      radial-gradient(ellipse 50% 30% at 80% 80%, rgba(124,106,247,0.05) 0%, transparent 60%);
    pointer-events: none;
  }

  .container {
    width: 100%;
    max-width: 520px;
  }

  /* ── Login ── */
  .login-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 40px;
  }

  .logo {
    font-family: var(--sans);
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 8px;
  }

  .logo span { color: var(--accent); }

  .tagline {
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 32px;
  }

  .field {
    margin-bottom: 16px;
  }

  .field label {
    display: block;
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .field input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
  }

  .field input:focus { border-color: var(--accent); }

  .btn {
    width: 100%;
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    padding: 13px;
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    cursor: pointer;
    transition: opacity 0.2s;
    margin-top: 8px;
  }

  .btn:hover { opacity: 0.85; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn.danger { background: var(--red); }
  .btn.secondary {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    margin-top: 8px;
  }

  .error-msg {
    color: var(--red);
    font-size: 12px;
    margin-top: 10px;
    display: none;
  }

  /* ── Main App ── */
  .app-box { display: none; }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }

  .header-left .logo { margin-bottom: 2px; }

  .logout-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--muted);
    border-radius: 6px;
    padding: 6px 12px;
    font-family: var(--mono);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .logout-btn:hover { border-color: var(--red); color: var(--red); }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 16px;
  }

  .card-title {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }

  textarea {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    resize: vertical;
    min-height: 100px;
    outline: none;
    transition: border-color 0.2s;
  }
  textarea:focus { border-color: var(--accent); }

  .hint {
    font-size: 10px;
    color: var(--muted);
    margin-top: 8px;
    line-height: 1.6;
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }

  .stat {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }

  .stat-val {
    font-family: var(--sans);
    font-size: 24px;
    font-weight: 800;
  }

  .stat-val.green { color: var(--accent); }
  .stat-val.red { color: var(--red); }
  .stat-val.purple { color: var(--accent2); }

  .stat-label {
    font-size: 9px;
    color: var(--muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-top: 4px;
  }

  /* Progress */
  .progress-wrap {
    background: var(--bg);
    border-radius: 3px;
    height: 4px;
    margin: 16px 0;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 3px;
    transition: width 0.4s ease;
    width: 0%;
  }

  /* Log */
  .log-box {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    height: 200px;
    overflow-y: auto;
    font-size: 11px;
    line-height: 1.8;
  }

  .log-box::-webkit-scrollbar { width: 3px; }
  .log-box::-webkit-scrollbar-thumb { background: var(--border); }

  .log-ok   { color: var(--accent); }
  .log-fail { color: var(--red); }
  .log-sys  { color: var(--accent2); }
  .log-info { color: var(--muted); }

  .controls { display: flex; gap: 10px; }
  .controls .btn { margin-top: 0; }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 20px;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--muted);
  }

  .dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--muted);
  }

  .dot.running { background: var(--accent); animation: blink 1s infinite; }
  .dot.paused  { background: #f59e0b; }

  @keyframes blink {
    0%,100% { opacity: 1; }
    50% { opacity: 0.2; }
  }
</style>
</head>
<body>

<!-- LOGIN -->
<div class="container" id="loginContainer">
  <div class="login-box">
    <div class="logo">Sheba <span>OTP</span></div>
    <div class="tagline">Sender Tool — Secure Access</div>
    <div class="field">
      <label>Password</label>
      <input type="password" id="pwInput" placeholder="Enter password" onkeydown="if(event.key==='Enter')doLogin()">
    </div>
    <button class="btn" onclick="doLogin()">Access Tool</button>
    <div class="error-msg" id="loginError">Wrong password. Try again.</div>
  </div>
</div>

<!-- MAIN APP -->
<div class="container" id="appContainer">
  <div class="app-box" id="appBox">

    <div class="header">
      <div class="header-left">
        <div class="logo">Sheba <span>OTP</span></div>
        <div class="tagline">Sender Tool</div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="status-badge">
          <span class="dot" id="statusDot"></span>
          <span id="statusText">Idle</span>
        </span>
        <button class="logout-btn" onclick="doLogout()">Logout</button>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats-row">
      <div class="stat">
        <div class="stat-val green" id="statOk">0</div>
        <div class="stat-label">Sent</div>
      </div>
      <div class="stat">
        <div class="stat-val red" id="statFail">0</div>
        <div class="stat-label">Failed</div>
      </div>
      <div class="stat">
        <div class="stat-val purple" id="statTotal">0</div>
        <div class="stat-label">Total</div>
      </div>
    </div>

    <!-- Numbers input -->
    <div class="card">
      <div class="card-title">Target Numbers</div>
      <textarea id="numbersInput" placeholder="01711000001&#10;01811000002&#10;+8801911000003&#10;&#10;One number per line"></textarea>
      <div class="hint">
        ✦ One number per line &nbsp;·&nbsp; With or without +88 prefix &nbsp;·&nbsp; Delay: <span id="delayVal"></span>s between each
      </div>
    </div>

    <!-- Progress -->
    <div class="progress-wrap">
      <div class="progress-bar" id="progressBar"></div>
    </div>

    <!-- Controls -->
    <div class="controls" style="margin-bottom:16px;">
      <button class="btn" id="startBtn" onclick="startSending()">▶ Start Sending</button>
      <button class="btn secondary" id="pauseBtn" onclick="togglePause()" style="display:none;">⏸ Pause</button>
      <button class="btn danger" id="stopBtn" onclick="stopSending()" style="display:none;">■ Stop</button>
    </div>

    <!-- Log -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div class="card-title" style="margin-bottom:0;">Live Log</div>
        <button onclick="clearLog()" style="background:none;border:none;color:var(--muted);font-family:var(--mono);font-size:11px;cursor:pointer;">Clear</button>
      </div>
      <div class="log-box" id="logBox">
        <span class="log-sys">// Ready. Enter numbers and press Start.</span>
      </div>
    </div>

  </div>
</div>

<script>
  // Config injected safely from Flask
  window.DELAY_MS = {{ delay_ms }};
  document.addEventListener('DOMContentLoaded', function() {
    var el = document.getElementById('delayVal');
    if (el) el.textContent = (window.DELAY_MS / 1000).toFixed(0);
  });
</script>
<script>
let running = false;
let paused  = false;
let stopped = false;
let ok = 0, fail = 0, total = 0;

// ── Login ────────────────────────────────────────────────────────────────────────
async function doLogin() {
  const pw = document.getElementById('pwInput').value;
  const err = document.getElementById('loginError');
  err.style.display = 'none';
  try {
    const r = await fetch('/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({password: pw})
    });
    const d = await r.json();
    if (d.ok) {
      document.getElementById('loginContainer').style.display = 'none';
      document.getElementById('appBox').style.display = 'block';
    } else {
      err.style.display = 'block';
    }
  } catch(e) {
    err.textContent = 'Connection error.';
    err.style.display = 'block';
  }
}

async function doLogout() {
  await fetch('/logout', {method:'POST'});
  location.reload();
}

// ── Log helpers ────────────────────────────────────────────────────────────────
function addLog(msg, cls='log-info') {
  const box = document.getElementById('logBox');
  const t = new Date().toLocaleTimeString('en-GB');
  box.innerHTML += `<div class="${cls}">[${t}] ${msg}</div>`;
  box.scrollTop = box.scrollHeight;
}

function clearLog() {
  document.getElementById('logBox').innerHTML = '';
}

// ── Stats ──────────────────────────────────────────────────────────────────────
function updateStats() {
  document.getElementById('statOk').textContent    = ok;
  document.getElementById('statFail').textContent  = fail;
  document.getElementById('statTotal').textContent = total;
  if (total > 0) {
    document.getElementById('progressBar').style.width = ((ok+fail)/total*100) + '%';
  }
}

function setStatus(state) {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  dot.className = 'dot ' + state;
  text.textContent = state === 'running' ? 'Running' : state === 'paused' ? 'Paused' : 'Idle';
}

// ── Sending ────────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function startSending() {
  const raw = document.getElementById('numbersInput').value.trim();
  if (!raw) { addLog('No numbers entered.', 'log-fail'); return; }

  const numbers = raw.split('\n').map(n => n.trim()).filter(n => n.length > 0);
  if (numbers.length === 0) { addLog('No valid numbers found.', 'log-fail'); return; }

  ok = 0; fail = 0; total = numbers.length;
  running = true; paused = false; stopped = false;
  updateStats();
  setStatus('running');

  document.getElementById('startBtn').style.display = 'none';
  document.getElementById('pauseBtn').style.display = 'block';
  document.getElementById('stopBtn').style.display  = 'block';
  document.getElementById('numbersInput').disabled  = true;

  addLog(`Starting — ${total} numbers`, 'log-sys');

  for (let i = 0; i < numbers.length; i++) {
    if (stopped) { addLog('Stopped by user.', 'log-sys'); break; }
    while (paused) { await sleep(500); }

    const num = numbers[i];
    addLog(`[${i+1}/${total}] Fetching token for ${num}...`, 'log-info');

    try {
      const r = await fetch('/send-otp', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({mobile: num})
      });
      const d = await r.json();

      if (d.ok) {
        ok++;
        addLog(`✓ ${num} — OTP sent (retry after ${d.retry_after}s)`, 'log-ok');
      } else {
        fail++;
        addLog(`✗ ${num} — ${d.error}`, 'log-fail');
      }
    } catch(e) {
      fail++;
      addLog(`✗ ${num} — Network error`, 'log-fail');
    }

    updateStats();
    if (i < numbers.length - 1 && !stopped) await sleep(window.DELAY_MS);
  }

  if (!stopped) addLog(`Done — ${ok} sent, ${fail} failed`, 'log-sys');
  setStatus('idle');
  running = false;
  document.getElementById('startBtn').style.display = 'block';
  document.getElementById('pauseBtn').style.display = 'none';
  document.getElementById('stopBtn').style.display  = 'none';
  document.getElementById('numbersInput').disabled  = false;
}

function togglePause() {
  paused = !paused;
  setStatus(paused ? 'paused' : 'running');
  document.getElementById('pauseBtn').textContent = paused ? '▶ Resume' : '⏸ Pause';
  addLog(paused ? 'Paused.' : 'Resumed.', 'log-sys');
}

function stopSending() {
  stopped = true;
  paused  = false;
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, delay_ms=int(DELAY_SECONDS * 1000))

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if data.get("password") == ADMIN_PASSWORD:
        session.permanent = True
        session["logged_in"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/send-otp", methods=["POST"])
@login_required
def send_otp():
    data   = request.get_json()
    mobile = data.get("mobile", "").strip()

    if not mobile:
        return jsonify({"ok": False, "error": "No mobile number"})

    # Normalize number
    if not mobile.startswith("+"):
        mobile = f"+88{mobile}" if not mobile.startswith("88") else f"+{mobile}"

    # Step 1: Always get a fresh token
    api_token = get_fresh_token()
    if not api_token:
        return jsonify({"ok": False, "error": "Could not get API token"})

    # Step 2: Shoot OTP
    success, result = shoot_otp(mobile, api_token)

    if success:
        return jsonify({"ok": True, "retry_after": result})
    else:
        return jsonify({"ok": False, "error": str(result)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
