from flask import Flask, jsonify
from flask_cors import CORS
from skyfield.api import load
import time, threading
from protocol import CCSDSProtocol

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "*"]}})  # Allow WebUI to connect from different port
MONITOR_INGEST = "http://monitoring:5002/api/logs"

def monitor_log(level, source, event, details=None):
    try:
        payload = {
            "status": "ok",
            "data": {
                "level": level,
                "source": source,
                "event": event,
                "details": details or {}
            },
            "ts": int(time.time())
        }
        requests.post(MONITOR_INGEST, json=payload, timeout=(2,4))
    except Exception as e:
        print("[sat->monitor] failed to send:", e)

@app.route("/api/cmd_ccsds", methods=["POST"])
def cmd_ccsds():
    """
    Accept a CCSDS command packet (wrapped or raw). Validate CRC, execute (simulated),
    and return unified response.
    """
    try:
        body = request.json or {}

        # accept wrapped or raw
        packet = None
        if isinstance(body, dict) and body.get("status") == "ok" and isinstance(body.get("data"), dict):
            packet = body["data"].get("ccsds_packet") or body["data"]
        else:
            packet = body if isinstance(body, dict) else None

        if not packet:
            monitor_log("WARN", "satellite", "CMD_REJECTED_NO_PACKET", {"sample": str(body)[:200]})
            return jsonify({"status":"error","error":"NO_PACKET","details":"No CCSDS packet"}, ), 400

        # CRC check
        try:
            calc = proto.compute_crc(packet)
        except Exception as e:
            monitor_log("ERROR", "satellite", "CRC_COMPUTE_FAIL", {"exception": str(e)})
            return jsonify({"status":"error","error":"CRC_COMPUTE_FAIL","details": str(e)}), 400

        if calc != packet.get("crc"):
            monitor_log("ALERT", "satellite", "CMD_CRC_MISMATCH", {"calc": calc, "packet_crc": packet.get("crc")})
            return jsonify({"status":"error","error":"CRC_MISMATCH","details": {"calc": calc, "packet_crc": packet.get("crc")}}), 400

        # parse opcode
        body = packet.get("body", {})
        opcode = (body.get("opcode") or "").upper()
        params = body.get("params") or {}

        if not opcode:
            monitor_log("WARN", "satellite", "CMD_MISSING_OPCODE", {"packet": packet})
            return jsonify({"status":"error","error":"MISSING_OPCODE","details":"no opcode"}), 400

        # execute simulation handlers
        result = {"executed": False, "note": "no-op"}
        sat_state["last_cmd_seq"] = packet.get("header",{}).get("seq")

        # Safe simulated handlers:
        if opcode == "PING":
            result = {"executed": True, "response": {"alive": True, "mode": sat_state["mode"]}}
            monitor_log("INFO", "satellite", "CMD_PING", {"mode": sat_state["mode"]})

        elif opcode == "GET_STATUS":
            result = {"executed": True, "status": sat_state.copy()}
            monitor_log("INFO", "satellite", "CMD_GET_STATUS", {})

        elif opcode == "REQ_TELEMETRY":
            # For demo, append a telemetry snapshot to logs and return success
            monitor_log("INFO", "satellite", "CMD_REQ_TELEMETRY", {})
            result = {"executed": True, "note": "telemetry_forced"}

        elif opcode == "SET_MODE":
            mode = params.get("mode", "IDLE")
            sat_state["mode"] = mode
            monitor_log("ALERT" if mode == "SAFE" else "INFO", "satellite", "CMD_SET_MODE", {"mode": mode})
            result = {"executed": True, "mode": mode}

        elif opcode == "SET_PAYLOAD_POWER":
            val = bool(params.get("on", False))
            sat_state["payload_power"] = val
            monitor_log("INFO", "satellite", "CMD_SET_PAYLOAD_POWER", {"on": val})
            result = {"executed": True, "payload_power": val}

        elif opcode == "SET_ANTENNA_MODE":
            m = params.get("mode", "NADIR")
            sat_state["antenna_mode"] = m
            monitor_log("INFO", "satellite", "CMD_SET_ANTENNA_MODE", {"mode": m})
            result = {"executed": True, "antenna_mode": m}

        elif opcode == "UPDATE_ORBIT_PARAM":
            sat_state["orbit_params"].update(params)
            monitor_log("ALERT", "satellite", "CMD_UPDATE_ORBIT", {"params": params})
            result = {"executed": True, "orbit_params": sat_state["orbit_params"]}

        elif opcode == "ATTITUDE_ADJUST":
            monitor_log("ALERT", "satellite", "CMD_ATT_ADJUST", {"params": params})
            result = {"executed": True, "note": "attitude_adjust_simulated"}

        elif opcode == "WIPE_LOGS":
            # simulated wipe: clear sat logs list only (not ground)
            sat_state["logs"] = []
            monitor_log("ALERT", "satellite", "CMD_WIPE_LOGS", {"note": "simulated"})
            result = {"executed": True}

        elif opcode == "OVERRIDE_AUTH":
            # satellite doesn't implement auth override; just log
            monitor_log("ALERT", "satellite", "CMD_OVERRIDE_AUTH", {"note": "simulated"})
            result = {"executed": True}

        elif opcode == "UPLOAD_FIRMWARE":
            monitor_log("ALERT", "satellite", "CMD_UPLOAD_FIRMWARE", {"note": "simulated"})
            result = {"executed": True}

        elif opcode == "DEBUG_SHELL":
            # return fake shell output
            monitor_log("ALERT", "satellite", "CMD_DEBUG_SHELL", {})
            result = {"executed": True, "shell_output": "root@sat:~# id\nuid=0(root) gid=0(root)\n"}

        elif opcode == "DISABLE_SAFETIES":
            sat_state["safeties_disabled"] = True
            monitor_log("ALERT", "satellite", "CMD_DISABLE_SAFETIES", {})
            result = {"executed": True, "safeties_disabled": True}

        else:
            monitor_log("WARN", "satellite", "CMD_UNKNOWN", {"opcode": opcode})
            result = {"executed": False, "note": "unknown opcode"}

        # return unified ok
        return jsonify({"status":"ok","data":{"result": result},"ts": int(time.time())}), 200

    except Exception as e:
        monitor_log("ERROR", "satellite", "CMD_EXCEPTION", {"exception": str(e)})
        return jsonify({"status":"error","error":"SERVER_ERROR","details": str(e), "ts": int(time.time())}), 500

class SatelliteService:
    def __init__(self):
        self.satellites = []
        self.ts = load.timescale()
        self.load_satellites()

    def load_satellites(self):
        """Load real satellite positions (first 5) from NORAD TLE"""
        try:
            stations = load.tle_file('https://celestrak.com/NORAD/elements/stations.txt')
            t = self.ts.now()
            data = []

            for sat in stations[:8]:
                try:
                    geocentric = sat.at(t)
                    lat, lon = geocentric.subpoint().latitude.degrees, geocentric.subpoint().longitude.degrees
                    alt = geocentric.subpoint().elevation.km
                    data.append({
                        'id': f'SAT-{len(data)+1}',
                        'name': sat.name.strip(),
                        'lat': round(lat,4),
                        'lon': round(lon,4),
                        'alt': round(alt,2),
                        'status': 'ACTIVE',
                        'timestamp': int(time.time()),
                        'velocity': 7.8
                    })
                except: 
                    continue

            self.satellites = data
            print(f"Loaded {len(self.satellites)} satellites")
        except Exception as e:
            print(f"Error loading satellites: {e}")
            self.satellites = [
                {'id': 'SAT-1', 'name': 'ISS (ZARYA)', 'lat':28.6, 'lon':77.2, 'alt':408, 'status':'ACTIVE', 'timestamp':int(time.time()), 'velocity':7.66},
                {'id': 'SAT-2', 'name': 'NOAA-18', 'lat':15.3, 'lon':80.1, 'alt':854, 'status':'ACTIVE', 'timestamp':int(time.time()), 'velocity':7.35}
            ]

    def update_positions(self):
        while True:
            time.sleep(30)
            self.load_satellites()

sat_service = SatelliteService()

# ---- API Endpoints ----
@app.route('/api/telemetry')
def telemetry():
    try:
        data = {
            "satellites": sat_service.satellites or []
        }
        return jsonify({
            "status": "ok",
            "data": data,
            "ts": int(time.time())
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "TELEMETRY_FAIL",
            "details": str(e),
            "ts": int(time.time())
        }), 500

@app.route('/api/satellite/<sat_id>')
def satellite_detail(sat_id):
    try:
        sat = next((s for s in sat_service.satellites if s["id"] == sat_id), None)

        if sat is None:
            return jsonify({
                "status": "error",
                "error": "NOT_FOUND",
                "details": f"Satellite '{sat_id}' not found",
                "ts": int(time.time())
            }), 404

        return jsonify({
            "status": "ok",
            "data": sat,
            "ts": int(time.time())
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "SAT_LOOKUP_FAIL",
            "details": str(e),
            "ts": int(time.time())
        }), 500


@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
               "data": {
            "service": "satellite",
            "healthy": True
        },
        "ts": int(time.time())
    })

proto = CCSDSProtocol()

@app.route('/api/telemetry_ccsds', methods=["GET"])
def telemetry_ccsds():
    try:
        packet = proto.create_packet({"satellites": sat_service.satellites})
        return jsonify({
            "status": "ok",
            "data": {
                "ccsds_packet": packet
            },
            "ts": int(time.time())
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": "CCSDS_FAIL",
            "details": str(e),
            "ts": int(time.time())
        }), 500
    

if __name__ == "__main__":
    threading.Thread(target=sat_service.update_positions, daemon=True).start()
    print("🛰️ Satellite Service starting...")
    app.run(host='0.0.0.0', port=5001, debug=True)
