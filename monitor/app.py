from flask import Flask, request, jsonify
from datetime import datetime, timezone
from collections import defaultdict, deque
import threading
import time
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "*"]}, r"/log": {"origins": ["http://localhost:3000", "*"]}})

# thread-safe containers
_logs_lock = threading.Lock()
_alerts_lock = threading.Lock()

LOG_CAP = 500
ALERT_CAP = 200

logs = deque(maxlen=LOG_CAP)
alerts = deque(maxlen=ALERT_CAP)
conn_counts = defaultdict(list)

# ------------------------------
# Utility Functions
# ------------------------------

def nos_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def now_ts():
    return int(time.time())

def api_ok(data):
    return jsonify({
        "status": "ok",
        "data": data,
        "ts": now_ts()
    })

def api_err(code, details):
    return jsonify({
        "status": "error",
        "error": code,
        "details": str(details),
        "ts": now_ts()
    }), 500

# ------------------------------
# Logging Core (thread-safe)
# ------------------------------

def add_log(level, source, event, details=None):
    entry = {
        "timestamp": nos_iso(),
        "level": level,
        "source": source,
        "event": event,
        "details": details or {}
    }
    with _logs_lock:
        logs.append(entry)
    print("[LOG]", entry)

    # Auto-alert logic
    if level == "ALERT" or "scan" in event.lower():
        with _alerts_lock:
            alerts.append(entry)

def note_conn(src_ip):
    t = time.time()
    conn_counts[src_ip].append(t)
    conn_counts[src_ip] = [ts for ts in conn_counts[src_ip] if t - ts < 10]
    if len(conn_counts[src_ip]) > 30:
        add_log("ALERT", "monitor", "HighConnectionRate", {"src_ip": src_ip, "rate": len(conn_counts[src_ip])})

# ------------------------------
# Ingest endpoints (accept both /log and /api/logs for POST)
# ------------------------------
def _handle_ingest(body):
    level = body.get("level", "INFO")
    source = body.get("source", "unknown")
    event = body.get("event", "")
    details = body.get("details", {})
    add_log(level, source, event, details)
    if event.lower().startswith("conn:"):
        src_ip = details.get("src_ip") or source
        note_conn(src_ip)
    return {"ingested": True}

@app.route('/log', methods=['POST'])
@app.route('/api/logs', methods=['POST'])
def ingest_log():
    try:
        body = request.json or {}
        result = _handle_ingest(body)
        return api_ok(result)
    except Exception as e:
        return api_err("LOG_INGEST_FAIL", e)

# ------------------------------
# Read APIs (C2 shape)
# ------------------------------
@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        with _logs_lock:
            snapshot = list(logs)[-LOG_CAP:]
        return api_ok({"logs": snapshot})
    except Exception as e:
        return api_err("LOG_FETCH_FAIL", e)

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    try:
        with _alerts_lock:
            snapshot = list(alerts)[-ALERT_CAP:]
        return api_ok({"alerts": snapshot})
    except Exception as e:
        return api_err("ALERT_FETCH_FAIL", e)

@app.route('/api/overview')
def overview():
    try:
        with _logs_lock:
            last_log = logs[-1] if logs else None
        with _alerts_lock:
            last_alert = alerts[-1] if alerts else None
        return api_ok({
            "log_count": len(logs),
            "alert_count": len(alerts),
            "last_log": last_log,
            "last_alert": last_alert
        })
    except Exception as e:
        return api_err("OVERVIEW_FAIL", e)

@app.route('/api/health')
@app.route('/health')
def health():
    return api_ok({"service": "monitoring", "healthy": True})

# ------------------------------
# Background Summary
# ------------------------------
def periodic_summary():
    while True:
        time.sleep(30)
        print(f"[monitor] logs={len(logs)} alerts={len(alerts)}")

if __name__ == '__main__':
    threading.Thread(target=periodic_summary, daemon=True).start()
    print("Starting monitor app on port 5002")
    app.run(host="0.0.0.0", port=5002, debug=True)
