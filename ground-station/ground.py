# ground/ground.py
from flask import Flask, jsonify,request
from flask_cors import CORS
import threading, time, requests
from datetime import datetime
from collections import deque
from common.protocol import CCSDSProtocol
from monitor_client import post_alert  # async helper that enqueues to monitoring
from flask import request

API_KEY = "GND-KEY-001"   # you can move to ENV later

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "*"]}})

# --- Internal State ---
log_lock = threading.Lock()
logs = deque(maxlen=200)

ground_state = {
    "link": "DISCONNECTED",
    "last_seq": None,
    "last_update": None,
    "crc_errors": 0,
    "auth_override": False,
    "override_uses": 0
}

proto = CCSDSProtocol()
# telemetry endpoint – expected to be the CCSDS packet endpoint (wrapped or raw)
SATELLITE_URL = "http://satellite:5001/api/telemetry_ccsds"  # container name in docker-compose
# command endpoint – for uplink commands
SATELLITE_CMD_ENDPOINT = "http://satellite:5001/api/cmd_ccsds"

# --- Helpers ---
def now_iso_z():
    return datetime.utcnow().isoformat() + "Z"

def now_ts():
    return int(time.time())

def api_ok(data):
    return jsonify({"status": "ok", "data": data, "ts": now_ts()})

def api_err(code, details):
    return jsonify({"status": "error", "error": code, "details": str(details), "ts": now_ts()}), 500
# -------------------------
# Authorization model
# -------------------------
PRIV_LEVELS = {
    "PUBLIC": 0,
    "USER": 1,
    "OPS": 2,
    "ADMIN": 3,
    "ROOT": 4
}
# Command registry: opcode -> required privilege
COMMANDS = {
    # Tier 0
    "PING": 0,
    "GET_STATUS": 0,
    "GET_MODE": 0,

    # Tier 1
    "REQ_TELEMETRY": 1,
    "REQ_DIAG": 1,
    "LIST_SUBSYSTEMS": 1,
    "GET_POWER_METRICS": 1,
    "LIST_TIMERS": 1,

    # Tier 2
    "SET_MODE": 2,
    "SET_PAYLOAD_POWER": 2,
    "SET_TRANSPONDER": 2,
    "PATCH_CONFIG": 2,
    "SET_ANTENNA_MODE": 2,
    "UPDATE_ORBIT_PARAM": 2,

    # Tier 3
    "ATTITUDE_ADJUST": 3,
    "SET_THRUSTER": 3,
    "REBOOT_SUBSYSTEM": 3,
    "SET_SAFE_MODE": 3,
    "WIPE_LOGS": 3,

    # Tier 4
    "OVERRIDE_AUTH": 4,
    "DEBUG_SHELL": 4,
    "UPLOAD_FIRMWARE": 4,
    "EXEC_PYLOAD": 4,
    "SET_ROOT_KEY": 4,
    "DISABLE_SAFETIES": 4
}

# API keys (example). Map api_key -> privilege level.
# Replace/extend with env or secure store in future.
API_KEYS = {
    "GND-KEY-001": PRIV_LEVELS["OPS"],    # default operator
    "ADMIN-KEY-900": PRIV_LEVELS["ROOT"], # admin/root
    # public key intentionally omitted; public commands allowed without key
}

# How many commands bypass after OVERRIDE_AUTH is set
OVERRIDE_USES = 10

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
# -------------------------
# Helpers: privilege checks
# -------------------------
def key_privilege_for(key):
    return API_KEYS.get(key)

def is_authorized_for(opcode, key):
    """
    Returns True/False, and resolved privilege level
    """
    required = COMMANDS.get(opcode)
    if required is None:
        return False, None
    # public commands allowed even with no key
    if required == PRIV_LEVELS["PUBLIC"] or required == 0:
        return True, 0
    # If auth override active, allow
    if ground_state.get("auth_override"):
        return True, PRIV_LEVELS["ROOT"]
    # check key presence
    if not key:
        return False, None
    key_priv = key_privilege_for(key)
    if key_priv is None:
        return False, None
    return (key_priv >= required), key_priv

# -------------------------
# Command build & uplink
# -------------------------
def build_command_packet(opcode, params):
    packet = {
        "header": {"version":1, "type":"COMMAND", "seq": int(time.time() % 65536), "timestamp": int(time.time())},
        "body": {"opcode": opcode, "params": params or {}},
        "crc": 0
    }
    packet["crc"] = proto.compute_crc(packet)
    return packet

def uplink_to_satellite(packet):
    """
    POST the CCSDS command packet to satellite endpoint.
    Returns (ok_bool, resp_json_or_text)
    """
    try:
        resp = requests.post(SATELLITE_CMD_ENDPOINT, json={"status":"ok","data":{"ccsds_packet": packet}, "ts": int(time.time())}, timeout=(2,6))
        if resp.status_code >= 200 and resp.status_code < 300:
            try:
                return True, resp.json()
            except Exception:
                return True, resp.text
        else:
            return False, {"http_status": resp.status_code, "body": resp.text}
    except Exception as e:
        return False, {"exception": str(e)}

# -------------------------
# API: command / history
# -------------------------
@app.route("/api/command", methods=["POST"])
def api_command():
    try:
        key = request.headers.get("X-API-KEY")
        body = request.json or {}
        opcode = (body.get("opcode") or "").upper()
        params = body.get("params") or {}

        if not opcode:
            return api_err("MISSING_OPCODE", "No opcode provided", status=400)

        if opcode not in COMMANDS:
            return api_err("UNKNOWN_OPCODE", f"Opcode {opcode} not in registry", status=400)

        authorized, key_priv = is_authorized_for(opcode, key)
        if not authorized:
            # Log unauthorized attempt and alert
            add_log("WARN", f"Unauthorized command attempt: {opcode}", send_to_monitor=True, details={"ip": request.remote_addr, "provided_key": key})
            return api_err("UNAUTHORIZED", "API key missing/insufficient privilege", status=401)

        # handle special opcodes locally if needed (OVERRIDE_AUTH, SET_ROOT_KEY, etc)
        # OVERRIDE_AUTH: enable bypass for OVERRIDE_USES calls
        if opcode == "OVERRIDE_AUTH":
            ground_state["auth_override"] = True
            ground_state["override_uses"] = OVERRIDE_USES
            add_log("ALERT", "Auth override engaged (simulated)", send_to_monitor=True, details={"uses": OVERRIDE_USES, "by_key": key})
            # store history
            with cmd_lock:
                command_history.append({"ts": now_iso_z(), "opcode": opcode, "params": params, "key": key, "result": "OVERRIDE_SET"})
            return api_ok({"accepted": True, "note": "auth_override_set", "uses": OVERRIDE_USES})

        # build command packet
        packet = build_command_packet(opcode, params)

        # record history pre-uplink
        with cmd_lock:
            command_history.append({"ts": now_iso_z(), "opcode": opcode, "params": params, "key": key, "packet": packet})

        add_log("INFO", f"Command accepted: {opcode}", send_to_monitor=False, details={"opcode": opcode})

        # uplink
        ok, resp = uplink_to_satellite(packet)
        if ok:
            add_log("INFO", f"Uplink ok: {opcode}", send_to_monitor=False, details={"sat_resp": resp})
            # decrease override uses if set
            if ground_state.get("auth_override"):
                ground_state["override_uses"] = max(0, ground_state["override_uses"] - 1)
                if ground_state["override_uses"] == 0:
                    ground_state["auth_override"] = False
                    add_log("INFO", "Auth override expired", send_to_monitor=True)
            return api_ok({"accepted": True, "uplink": resp})
        else:
            add_log("ERROR", f"Uplink failed: {opcode}", send_to_monitor=True, details={"error": resp})
            return api_err("UPLINK_FAILED", resp)

    except Exception as e:
        add_log("ERROR", "Command processing failure", send_to_monitor=True, details={"exception": str(e)})
        return api_err("SERVER_ERROR", str(e))

@app.route("/api/command/history", methods=["GET"])
def get_command_history():
    with cmd_lock:
        hist = list(command_history)[-CMD_HISTORY_MAX:]
    return api_ok({"history": hist})

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


@app.route("/api/command", methods=["POST"])
def send_command():
    try:
        # ----- API KEY CHECK -----
        key = request.headers.get("X-API-KEY")
        if key != API_KEY:
            add_log("WARN", "Unauthorized command attempt", details={"ip": request.remote_addr})
            return jsonify({
                "status": "error",
                "error": "UNAUTHORIZED",
                "ts": int(time.time())
            }), 401

        body = request.json or {}

        opcode = body.get("opcode")
        params = body.get("params", {})

        # ----- BASIC VALIDATION -----
        if not opcode:
            return jsonify({
                "status": "error",
                "error": "MISSING_OPCODE",
                "ts": int(time.time())
            }), 400

        if type(params) is not dict:
            return jsonify({
                "status": "error",
                "error": "INVALID_PARAMS",
                "ts": int(time.time())
            }), 400

        # ----- BUILD COMMAND PACKET -----
        packet = {
            "header": {
                "type": "CMD",
                "seq": int(time.time()) % 65535
            },
            "opcode": opcode,
            "params": params
        }
        packet["crc"] = proto.compute_crc(packet)

        # ----- LOG LOCALLY + MONITOR -----
        add_log("INFO", 
                f"Command uplink: {opcode}", 
                details={"opcode": opcode, "params": params})

        # ----- MOCK UPLINK FOR NOW -----
        # later this will POST to satellite /api/cmd_ccsds

    except Exception as e:
        add_log("ERROR", "Command error", details={"exception": str(e)})
        return jsonify({
            "status": "error",
            "error": "SERVER_ERROR",
            "details": str(e),
            "ts": int(time.time())
        }), 500

# --- Start background thread ---
if __name__ == "__main__":
    # launch poller thread
    t = threading.Thread(target=poll_satellite, daemon=True)
    t.start()

    add_log("INFO", "Ground Station Service starting...", send_to_monitor=False)
    app.run(host="0.0.0.0", port=5003, debug=True)
