from flask import Flask, jsonify, request
from flask_cors import CORS
from skyfield.api import load
import time
import threading
import requests

from protocol import CCSDSProtocol

# -----------------------------
# App Setup
# -----------------------------
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "*"]}})

MONITOR_INGEST = "http://monitoring:5002/log"

proto = CCSDSProtocol()

# -----------------------------
# Satellite State (SIMULATED)
# -----------------------------
sat_state = {
    "mode": "IDLE",
    "payload_power": True,
    "antenna_mode": "NOMINAL",
    "orbit_params": {},
    "last_cmd_seq": None,
    "safeties_disabled": False,
    "firmware_version": "1.0.0",
    "cmd_rejects": 0,
    "cmd_exec_count": 0,
    "logs": []
}

# -----------------------------
# Monitoring Helper
# -----------------------------
def monitor_log(level, source, event, details=None):
    try:
        requests.post(
            MONITOR_INGEST,
            json={
                "level": level,
                "source": source,
                "event": event,
                "details": details or {}
            },
            timeout=3
        )
    except Exception as e:
        print("[sat->monitor] failed:", e)

# -----------------------------
# COMMAND API
# -----------------------------
@app.route("/api/cmd_ccsds", methods=["POST"])
def cmd_ccsds():
    try:
        body = request.json or {}

        # unwrap CCSDS packet
        if isinstance(body, dict) and body.get("status") == "ok":
            packet = body.get("data", {}).get("ccsds_packet")
        else:
            packet = body if isinstance(body, dict) else None

        if not packet:
            monitor_log("WARN", "satellite", "NO_PACKET")
            return jsonify({"status": "error", "error": "NO_PACKET"}), 400

        header = packet.get("header", {})
        seq = header.get("seq")

        # replay protection
        if seq is not None and seq == sat_state["last_cmd_seq"]:
            monitor_log("ALERT", "satellite", "REPLAY_DETECTED", {"seq": seq})
            return jsonify({"status": "error", "error": "REPLAY_DETECTED"}), 409

        sat_state["last_cmd_seq"] = seq

        # CRC validation
        calc_crc = proto.compute_crc(packet)
        if calc_crc != packet.get("crc"):
            monitor_log(
                "ALERT",
                "satellite",
                "CRC_MISMATCH",
                {"calc": calc_crc, "packet": packet.get("crc")}
            )
            return jsonify({"status": "error", "error": "CRC_MISMATCH"}), 400

        body = packet.get("body", {})
        opcode = (body.get("opcode") or "").upper()
        params = body.get("params") or {}

        ALLOWED_OPCODES = {
            "PING",
            "GET_STATUS",
            "REQ_TELEMETRY",
            "SET_MODE",
            "SET_PAYLOAD_POWER",
            "SET_ANTENNA_MODE",
            "UPDATE_ORBIT_PARAM",
            "ATTITUDE_ADJUST",
            "WIPE_LOGS",
            "DEBUG_SHELL",
            "UPLOAD_FIRMWARE",
            "DISABLE_SAFETIES",
            "OVERRIDE_AUTH"
        }

        if opcode not in ALLOWED_OPCODES:
            sat_state["cmd_rejects"] += 1
            monitor_log("WARN", "satellite", "UNKNOWN_OPCODE", {"opcode": opcode})
            return jsonify({"status": "error", "error": "UNKNOWN_OPCODE"}), 400

        # -----------------------------
        # EXECUTION (SIMULATED)
        # -----------------------------
        sat_state["cmd_exec_count"] += 1
        result = {"executed": True}

        if opcode == "PING":
            result["alive"] = True

        elif opcode == "GET_STATUS":
            result["state"] = sat_state.copy()

        elif opcode == "REQ_TELEMETRY":
            monitor_log("INFO", "satellite", "TELEMETRY_FORCED")

        elif opcode == "SET_MODE":
            sat_state["mode"] = params.get("mode", "IDLE")
            monitor_log("INFO", "satellite", "MODE_SET", {"mode": sat_state["mode"]})

        elif opcode == "SET_PAYLOAD_POWER":
            sat_state["payload_power"] = bool(params.get("on", False))

        elif opcode == "SET_ANTENNA_MODE":
            sat_state["antenna_mode"] = params.get("mode", "NOMINAL")

        elif opcode == "UPDATE_ORBIT_PARAM":
            sat_state["orbit_params"].update(params)
            monitor_log("ALERT", "satellite", "ORBIT_UPDATE", params)

        elif opcode == "ATTITUDE_ADJUST":
            monitor_log("ALERT", "satellite", "ATTITUDE_ADJUST_SIM", params)

        elif opcode == "WIPE_LOGS":
            sat_state["logs"].clear()
            monitor_log("ALERT", "satellite", "LOG_WIPE_SIM")

        elif opcode == "DISABLE_SAFETIES":
            sat_state["safeties_disabled"] = True
            monitor_log("ALERT", "satellite", "SAFETIES_DISABLED")

        elif opcode == "UPLOAD_FIRMWARE":
            sat_state["firmware_version"] = params.get("version", "X")
            monitor_log("ALERT", "satellite", "FW_UPLOAD_SIM", params)

        elif opcode == "DEBUG_SHELL":
            monitor_log("ALERT", "satellite", "ROOT_SHELL_SIM")
            result["shell"] = "root@sat:~# id\nuid=0(root)\n"

        elif opcode == "OVERRIDE_AUTH":
            monitor_log("ALERT", "satellite", "AUTH_OVERRIDE_SIM")

        return jsonify({
            "status": "ok",
            "data": {
                "opcode": opcode,
                "result": result,
                "state": {
                    "mode": sat_state["mode"],
                    "firmware": sat_state["firmware_version"],
                    "safeties_disabled": sat_state["safeties_disabled"]
                }
            },
            "ts": int(time.time())
        })

    except Exception as e:
        monitor_log("ERROR", "satellite", "CMD_EXCEPTION", {"error": str(e)})
        return jsonify({"status": "error", "error": "SERVER_ERROR"}), 500

# -----------------------------
# Satellite Position Service
# -----------------------------
class SatelliteService:
    def __init__(self):
        self.satellites = []
        self.ts = load.timescale()
        self.load_satellites()

    def load_satellites(self):
        try:
            stations = load.tle_file(
                "https://celestrak.com/NORAD/elements/stations.txt"
            )
            t = self.ts.now()
            data = []

            for sat in stations[:8]:
                geo = sat.at(t).subpoint()
                data.append({
                    "id": f"SAT-{len(data)+1}",
                    "name": sat.name.strip(),
                    "lat": round(geo.latitude.degrees, 4),
                    "lon": round(geo.longitude.degrees, 4),
                    "alt": round(geo.elevation.km, 2),
                    "status": "ACTIVE",
                    "timestamp": int(time.time()),
                    "velocity": 7.8
                })

            self.satellites = data
            print(f"[satellite] loaded {len(data)} satellites")

        except Exception as e:
            print("[satellite] fallback data:", e)
            self.satellites = [
                {
                    "id": "SAT-1",
                    "name": "ISS",
                    "lat": 28.6,
                    "lon": 77.2,
                    "alt": 408,
                    "status": "ACTIVE",
                    "timestamp": int(time.time()),
                    "velocity": 7.66
                }
            ]

    def update_positions(self):
        while True:
            time.sleep(30)
            self.load_satellites()

sat_service = SatelliteService()

# -----------------------------
# Telemetry APIs
# -----------------------------
@app.route("/api/telemetry")
def telemetry():
    return jsonify({
        "status": "ok",
        "data": {"satellites": sat_service.satellites},
        "ts": int(time.time())
    })

@app.route("/api/satellite/<sat_id>")
def satellite_detail(sat_id):
    sat = next((s for s in sat_service.satellites if s["id"] == sat_id), None)
    if not sat:
        return jsonify({"status": "error", "error": "NOT_FOUND"}), 404
    return jsonify({"status": "ok", "data": sat, "ts": int(time.time())})

@app.route("/api/telemetry_ccsds")
def telemetry_ccsds():
    packet = proto.create_packet({"satellites": sat_service.satellites})
    return jsonify({
        "status": "ok",
        "data": {"ccsds_packet": packet},
        "ts": int(time.time())
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "data": {"service": "satellite", "healthy": True},
        "ts": int(time.time())
    })

# -----------------------------
# Start Service
# -----------------------------
if __name__ == "__main__":
    threading.Thread(
        target=sat_service.update_positions,
        daemon=True
    ).start()

    print("🛰️ Satellite Service starting on :5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
