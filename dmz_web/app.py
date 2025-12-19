from flask import Flask, redirect, request, jsonify, render_template, url_for,session
import requests
import datetime
import os

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/app/shared/support"

GROUND_API = "http://ground-station:5003/api"
MONITOR_URL = "http://monitoring:5002/api/logs"
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/support")
def support():
    return render_template("support.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ---- Proxy Endpoints ----
@app.route("/api/status", methods=["GET"])
def proxy_status():
    log_event(f"STATUS requested from {request.remote_addr}", "INFO")

    r = requests.get(
        f"{GROUND_API}/ground_state",
        headers=dict(request.headers),
        timeout=3
    )
    return (r.text, r.status_code, r.headers.items())

@app.route("/api/command", methods=["POST"])
def proxy_command():
    
    log_event(
        f"COMMAND proxy attempt from {request.remote_addr} | Headers={dict(request.headers)}",
        "WARN"
    )
    try:
        requests.post(
            MONITOR_URL,
            json={
                "level": "ALERT",
                "source": "dmz",
                "event": "COMMAND_EXEC",
                "details": {
                    "auth": False,
                    "opcode": request.json.get("opcode"),
                    "src_ip": request.remote_addr
                }
            },
            timeout=2
        )
    except Exception as e:
        print("Monitor logging failed:", e)
    r = requests.post(
        f"{GROUND_API}/command",
        json=request.get_json(),
        headers=dict(request.headers),
        timeout=3
    )
    return (r.text, r.status_code, r.headers.items())

# ---- Intentionally weak support endpoint (future pivot) ----
@app.route("/api/support/event", methods=["POST"])
def support_upload():
    file = request.files.get("file")

    if not file:
        return jsonify({"status": "error", "error": "NO_FILE"}), 400

    filename = file.filename
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    log_event(f"SUPPORT FILE UPLOADED: {filename}", "WARN")

    # Log to monitoring for visibility
    try:
        requests.post(
            MONITOR_URL,
            json={
                "level": "WARN",
                "source": "dmz",
                "event": "SUPPORT_FILE_UPLOAD",
                "details": {
                    "filename": filename,
                    "src_ip": request.remote_addr
                }
            },
            timeout=2
        )
    except:
        pass

    return jsonify({
        "status": "ok",
        "filename": filename
    })
def log_event(event, level="INFO"):
    ts = datetime.datetime.utcnow().isoformat()
    print(f"[DMZ {ts}] [{level}] {event}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)