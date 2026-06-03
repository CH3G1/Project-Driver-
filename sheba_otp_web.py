#!/usr/bin/env python3
"""
Sheba OTP Sender — Web UI v2.2
Uses Cloudflare Worker as proxy to bypass Cloudflare IP blocking.

Environment variables required:
  ADMIN_PASSWORD    — your chosen password
  DELAY_SECONDS     — delay between OTPs (default 3)
  SECRET_KEY        — any random string
  WORKER_URL        — your Cloudflare Worker URL
                      e.g. https://sheba-proxy.YOUR_NAME.workers.dev
"""

import os
import logging
import requests
from flask import Flask, send_from_directory, request, jsonify, session
from functools import wraps
from datetime import timedelta

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DELAY_SECONDS  = float(os.environ.get("DELAY_SECONDS", "3"))
WORKER_URL     = os.environ.get("WORKER_URL", "").rstrip("/")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "changeme-set-in-render")
app.permanent_session_lifetime = timedelta(hours=12)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ── Helpers via Cloudflare Worker ────────────────────────────
def get_fresh_token():
    try:
        r = requests.get(f"{WORKER_URL}/token", timeout=15)
        log.info(f"Worker /token status: {r.status_code} body: {r.text[:200]}")
        data = r.json()
        token = data.get("token") or data.get("data", {}).get("token")
        if token:
            log.info(f"Token obtained: {token[:20]}...")
            return token
        log.error(f"Token not found: {data}")
        return None
    except Exception as e:
        log.error(f"Token error: {e}")
        return None

def shoot_otp(mobile, api_token):
    try:
        r = requests.post(
            f"{WORKER_URL}/shoot",
            json={"mobile": mobile, "api_token": api_token},
            timeout=15
        )
        log.info(f"Worker /shoot [{mobile}] status: {r.status_code} body: {r.text[:200]}")
        data = r.json()
        if data.get("message") == "Good.":
            return True, data.get("can_retry_after", 150)
        return False, data.get("message", "Unknown error")
    except Exception as e:
        log.error(f"Shoot error: {e}")
        return False, str(e)

# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/config")
def config():
    return jsonify({
        "delay_ms":   int(DELAY_SECONDS * 1000),
        "worker_url": WORKER_URL,
    })

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
    if not WORKER_URL:
        return jsonify({"ok": False, "error": "WORKER_URL not set in environment"})

    data   = request.get_json()
    mobile = data.get("mobile", "").strip()
    if not mobile:
        return jsonify({"ok": False, "error": "No mobile number"})

    # Normalize number
    if mobile.startswith("+"):
        mobile = mobile[1:]
    if mobile.startswith("880"):
        mobile = "+" + mobile
    elif mobile.startswith("88"):
        mobile = "+" + mobile
    elif mobile.startswith("0"):
        mobile = "+88" + mobile
    else:
        mobile = "+880" + mobile

    api_token = get_fresh_token()
    if not api_token:
        return jsonify({"ok": False, "error": "Could not get API token from Worker"})

    success, result = shoot_otp(mobile, api_token)
    if success:
        return jsonify({"ok": True, "retry_after": result})
    return jsonify({"ok": False, "error": str(result)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
