#!/usr/bin/env python3
"""
Sheba OTP Sender — Web UI
Deploy on Render as a Python web service.
Environment variables required:
  ADMIN_PASSWORD  — your chosen password to access the tool
  DELAY_SECONDS   — delay between OTPs (default 3)
  SECRET_KEY      — any random string
"""

import os
import logging
import requests
from flask import Flask, send_from_directory, request, jsonify, session
from functools import wraps
from datetime import timedelta

# ── Config ───────────────────────────────────────────────────────────────────
APP_ID         = "8329815A6D1AE6DD"
GENERATE_URL   = f"https://api-accounts.sheba.xyz/api/v1/accountkit/generate/token?app_id={APP_ID}"
SHOOT_URL      = "https://accountkit.sheba.xyz/api/shoot-otp"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DELAY_SECONDS  = float(os.environ.get("DELAY_SECONDS", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "changeme-set-in-render")
app.permanent_session_lifetime = timedelta(hours=12)

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_fresh_token():
    try:
        r = requests.get(GENERATE_URL, headers=HEADERS, timeout=15)
        log.info(f"Token status: {r.status_code} | body: '{r.text[:200]}'")
        if not r.text.strip():
            log.error("EMPTY RESPONSE — Sheba API likely blocking Render IP")
            return None
        data = r.json()
        # Handle multiple possible response structures
        token = (
            data.get("token") or
            data.get("data", {}).get("token") or
            data.get("result", {}).get("token") or
            data.get("api_token")
        )
        if token:
            log.info(f"Fresh token: {token[:20]}...")
            return token
        log.error(f"Token not found in response: {data}")
        return None
    except Exception as e:
        log.error(f"Token error: {e}")
        return None

def shoot_otp(mobile, api_token):
    try:
        payload = {"mobile": mobile, "app_id": APP_ID, "api_token": api_token}
        r = requests.post(SHOOT_URL, headers=HEADERS, json=payload, timeout=10)
        data = r.json()
        log.info(f"shoot-otp [{mobile}]: {data}")
        if data.get("message") == "Good.":
            return True, data.get("can_retry_after", 150)
        return False, data.get("message", "Unknown error")
    except Exception as e:
        log.error(f"shoot error: {e}")
        return False, str(e)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/config")
def config():
    return jsonify({"delay_ms": int(DELAY_SECONDS * 1000)})

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
    # Normalize to +88XXXXXXXXXX — handles all formats:
    # +8801..., 8801..., 01..., 1...
    if mobile.startswith("+"):
        mobile = mobile[1:]           # strip leading +
    if mobile.startswith("880"):
        mobile = "+" + mobile         # 8801... → +8801...
    elif mobile.startswith("88"):
        mobile = "+" + mobile         # 881... → +881...
    elif mobile.startswith("0"):
        mobile = "+88" + mobile       # 01... → +8801...
    else:
        mobile = "+880" + mobile      # 1... → +8801...
    api_token = get_fresh_token()
    if not api_token:
        return jsonify({"ok": False, "error": "Could not get API token"})
    success, result = shoot_otp(mobile, api_token)
    if success:
        return jsonify({"ok": True, "retry_after": result})
    return jsonify({"ok": False, "error": str(result)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
