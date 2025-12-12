# ground/ground.py
from flask import Flask, jsonify
from flask_cors import CORS
import threading, time, requests
from datetime import datetime
from collections import deque
from common.protocol import CCSDSProtocol
from monitor_client import post_alert  # async helper that enqueues to monitoring

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "*"]}})

# --- Internal State ---
log_lock = threading.Lock()
logs = deque(maxlen=200)

ground_state = {
    "link": "DISCONNECTED",
    "last_seq": None,
    "last_update": None,
    "crc_errors": 0
}

proto = CCSDSProtocol()
# telemetry endpoint – expected to be the CCSDS packet endpoint (wrapped or raw)
SATELLITE_URL = "http://satellite:5001/api/telemetry_ccsds"  # container name in docker-compose

# --- Helpers ---
def now_iso_z():
    return datetime.utcnow().isoformat() + "Z"

def now_ts():
    return int(time.time())

def api_ok(data):
    return jsonify({"status": "ok", "data": data, "ts": now_ts()})

def api_err(code, details):
    return jsonify({"status": "error", "error": code, "details": str(details), "ts": now_ts()}), 500

# --- Logging Helper ---
def add_log(level, msg, send_to_monitor=None, details=None):
    """
    level: "INFO","WARN","ERROR","ALERT", etc.
    send_to_monitor: True = always, False = never, None = auto (only WARN/ERROR/ALERT)
    """
    ts = now_iso_z()
    entry = f"{ts} [{level}] {msg}"
    # thread-safe append
    with log_lock:
        logs.append(entry)
    print(entry)

    # decide whether to forward structured entry to monitoring
    if send_to_monitor is True:
        send_structured = True
    elif send_to_monitor is False:
        send_structured = False
    else:
        # auto: only forward important logs
        send_structured = level in ("WARN", "ERROR", "ALERT")

    if send_structured:
        try:
            payload_level = level if level in ("INFO", "ALERT", "WARN", "ERROR") else "INFO"
            # Use monitor_client.post_alert (async, queued) to avoid blocking
            post_alert(payload_level, "ground-station", msg, details or {})
        except Exception as e:
            print(f"[monitor_client] failed to post alert: {e}")

# --- Background Telemetry Polling ---
def _extract_ccsds_packet(resp_json):
    """
    Accept either:
      - raw packet dict (header/body/crc)
      - wrapped C2 response: {"status":"ok","data":{"ccsds_packet": { ... }}}
      - wrapped older form: {"status":"ok","data": packet}
    Return packet dict or None.
    """
    if not isinstance(resp_json, dict):
        return None

    # If it's the wrapped C2 response
    if resp_json.get("status") == "ok" and isinstance(resp_json.get("data"), dict):
        data = resp_json.get("data")
        # prefer explicit name
        if "ccsds_packet" in data:
            return data.get("ccsds_packet")
        # if data itself is the packet
        # e.g., {"status":"ok","data": {"header":..., "body":..., "crc":...}}
        if "header" in data or "body" in data:
            return data
    # If it's already a packet
    if "header" in resp_json or "body" in resp_json:
        return resp_json

    return None

def poll_satellite():
    """
    Periodically poll the satellite CCSDS telemetry endpoint.
    This function is resilient to either raw packet or C2-wrapped response.
    """
    while True:
        try:
            # use (connect, read) timeout tuple to avoid long hangs
            res = requests.get(SATELLITE_URL, timeout=(2, 4))
            if res.status_code == 200:
                try:
                    resp_json = res.json()
                except ValueError:
                    add_log("ERROR", "Telemetry returned non-JSON", send_to_monitor=True, details={"status_code": res.status_code})
                    ground_state["link"] = "DISCONNECTED"
                    time.sleep(10)
                    continue

                packet = _extract_ccsds_packet(resp_json)
                if packet is None:
                    add_log("WARN", "Telemetry payload had unexpected structure", send_to_monitor=True, details={"sample": str(resp_json)[:200]})
                    ground_state["link"] = "DISCONNECTED"
                    time.sleep(10)
                    continue

                # compute CRC: proto.compute_crc expects same shape used by create_packet
                try:
                    crc_calc = proto.compute_crc(packet)
                except Exception as e:
                    add_log("ERROR", f"CRC compute failed: {e}", send_to_monitor=True, details={"exception": str(e)})
                    ground_state["link"] = "DISCONNECTED"
                    time.sleep(10)
                    continue

                seq = packet.get("header", {}).get("seq")
                packet_crc = packet.get("crc")

                if crc_calc == packet_crc:
                    ground_state["link"] = "CONNECTED"
                    ground_state["last_seq"] = seq
                    ground_state["last_update"] = now_iso_z()
                    add_log("INFO", f"Received telemetry seq={seq} CRC=OK", send_to_monitor=False, details={"seq": seq})
                else:
                    ground_state["crc_errors"] += 1
                    msg = f"CRC mismatch for seq={seq}"
                    add_log("WARN", msg, send_to_monitor=True, details={"seq": seq, "calc_crc": crc_calc, "packet_crc": packet_crc})
            else:
                add_log("ERROR", f"Telemetry fetch failed ({res.status_code})", send_to_monitor=True, details={"status_code": res.status_code})
                ground_state["link"] = "DISCONNECTED"

        except requests.exceptions.RequestException as e:
            add_log("ERROR", f"Satellite unreachable: {e}", send_to_monitor=True, details={"exception": str(e)})
            ground_state["link"] = "DISCONNECTED"
        except Exception as e:
            # catch-all
            add_log("ERROR", f"Unexpected poll error: {e}", send_to_monitor=True, details={"exception": str(e)})
            ground_state["link"] = "DISCONNECTED"

        time.sleep(10)  # poll interval (seconds)

# --- API Endpoints ---
@app.route("/api/ground_state")
def get_ground_state():
    return api_ok(ground_state)

@app.route("/api/logs")
def get_logs():
    # return last 50 human-readable log lines (not the structured monitoring logs)
    with log_lock:
        last = list(logs)[-50:]
    return api_ok({"logs": last})

@app.route('/api/health')
def health():
    return api_ok({"service": "ground", "healthy": True})

# --- Start background thread ---
if __name__ == "__main__":
    # launch poller thread
    t = threading.Thread(target=poll_satellite, daemon=True)
    t.start()

    add_log("INFO", "Ground Station Service starting...", send_to_monitor=False)
    app.run(host="0.0.0.0", port=5003, debug=True)
