from flask import Flask, jsonify
from flask_cors import CORS
from skyfield.api import load
import time, threading
from protocol import CCSDSProtocol

app = Flask(__name__)
CORS(app)  # Allow WebUI to connect from different port

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

            for sat in stations[:5]:
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
    return jsonify({'satellites': sat_service.satellites, 'timestamp': int(time.time())})

@app.route('/api/satellite/<sat_id>')
def satellite_detail(sat_id):
    sat = next((s for s in sat_service.satellites if s['id'] == sat_id), None)
    if sat: return jsonify(sat)
    return jsonify({'error':'Satellite not found'}), 404

@app.route('/health')
def health(): return jsonify({'status':'healthy','service':'satellite'})

proto = CCSDSProtocol()

@app.route('/api/telemetry_ccsds')
def telemetry_ccsds():
    packet = proto.create_packet({'satellites': sat_service.satellites})
    return jsonify(packet)

if __name__ == "__main__":
    threading.Thread(target=sat_service.update_positions, daemon=True).start()
    print("🛰️ Satellite Service starting...")
    app.run(host='0.0.0.0', port=5001, debug=True)
