// src/pages/GNSS.jsx
import React, { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
} from 'recharts';

const files = [
  '/data/pvtSolution0.json',
  '/data/pvtSolution1.json',
  '/data/pvtSolution2.json',
];

const safe = (v) => (typeof v === 'number' && !isNaN(v) ? v : null);
const fmt = (v, d = 5) => (v === null ? '—' : v.toFixed(d));
const haversine = (a, b) => {
  const R = 6371000;
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLon = (b.lon - a.lon) * Math.PI / 180;
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;

  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.sin(dLon / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2);

  return 2 * R * Math.asin(Math.sqrt(x));
};
export default function GNSS() {
  const [gnss, setGnss] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let index = 0;

    const fetchGNSS = async () => {
      try {
        const res = await fetch(files[index]);

        const json = await res.json();

        
        const raw = json.data ?? json;

        const last = (v) =>
        Array.isArray(v) ? v[v.length - 1] : v;

        const parsed = {
        lat: safe(last(raw.lat ?? raw.latitude)),
        lon: safe(last(raw.lon ?? raw.longitude)),
        alt: safe(last(raw.alt ?? raw.height)),
        vel: safe(last(raw.vel_mps ?? raw.speed)),
        fix: raw.fix_quality ?? raw.fix ?? '—',
        sats: raw.sat_count ?? raw.sats ?? '—',
        spoof: Array.isArray(raw.spoof_flags) ? raw.spoof_flags : [],
        };
        const flags = [];

        if (history.length >= 1) {
        const prev = history[history.length - 1];
        const dist = haversine(prev, { lat: parsed.lat, lon: parsed.lon }); // meters

        // velocity = meters per second (1s poll)
        parsed.vel = dist;

        if (dist > 500)
            flags.push(`Teleport detected (${dist.toFixed(1)} m)`);

        if (parsed.vel > 200)
            flags.push(`Impossible velocity (${parsed.vel.toFixed(1)} m/s)`);
        }

        parsed.spoof = flags;



        if (parsed.lat !== null && parsed.lon !== null) {
          setGnss(parsed);

          setHistory((prev) => {
        const next = [
            ...prev.slice(-50),
            {
            time: new Date().toLocaleTimeString(),
            lat: parsed.lat,
            lon: parsed.lon,
            alt_km: parsed.alt !== null ? parsed.alt / 1000 : null,
            },
        ];

        // 🔥 DERIVE VELOCITY (m/s)
        if (next.length >= 2) {
            const a = next[next.length - 2];
            const b = next[next.length - 1];
            const dist = haversine(a, b); // meters
            parsed.vel = dist; // per second (1s polling)
        }

        return next;
        });

        }

        index = (index + 1) % files.length;
      } catch (e) {
        console.error('GNSS fetch failed', e);
      }
    };

    fetchGNSS();
    const id = setInterval(fetchGNSS, 1000);
    return () => clearInterval(id);
  }, []);

  if (!gnss) {
    return <div style={{ padding: 20 }}>Waiting for GNSS data…</div>;
  }

  return (
    <div style={{ padding: 20, color: '#eaeaea', background: '#0f1115' }}>
      <h2>GNSS Telemetry Console</h2>

      {/* TELEMETRY GRID */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}
      >
        <Telemetry label="Latitude" value={fmt(gnss.lat)} />
        <Telemetry label="Longitude" value={fmt(gnss.lon)} />
        <Telemetry label="Altitude (m)" value={fmt(gnss.alt, 1)} />
        <Telemetry label="Velocity (m/s)" value={fmt(gnss.vel, 1)} />
        <Telemetry label="Fix Quality" value={gnss.fix} />
        <Telemetry label="Sat Count" value={gnss.sats} />
      </div>

      {/* SPOOF FLAGS */}
      <div style={{ marginBottom: 20 }}>
        <h4>Spoof Detection</h4>
        {gnss.spoof.length === 0 ? (
          <span style={{ color: 'limegreen' }}>No anomalies detected</span>
        ) : (
          <ul style={{ color: 'red' }}>
            {gnss.spoof.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        )}
      </div>

      {/* POSITION DRIFT */}
      <h4>Position Drift</h4>
      <LineChart width={750} height={260} data={history}>
        <CartesianGrid stroke="#333" strokeDasharray="3 3" />
        <XAxis dataKey="time" stroke="#aaa" />
        <YAxis stroke="#aaa" />
        <Tooltip />
        <Line type="monotone" dataKey="lat" stroke="#00ffcc" dot={false} />
        <Line type="monotone" dataKey="lon" stroke="#ffcc00" dot={false} />
      </LineChart>

      {/* ALTITUDE HISTOGRAM */}
      <h4 style={{ marginTop: 30 }}>Altitude Distribution (km)</h4>
      <BarChart width={750} height={260} data={history.filter(h => h.alt_km !== null)}>
        <CartesianGrid stroke="#333" strokeDasharray="3 3" />
        <XAxis dataKey="time" stroke="#aaa" />
        <YAxis stroke="#aaa" />
        <Tooltip />
        <Bar dataKey="alt_km" fill="#8884d8" />
      </BarChart>
    </div>
  );
}

function Telemetry({ label, value }) {
  return (
    <div
      style={{
        padding: 10,
        background: '#1a1d24',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.7 }}>{label}</div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 'bold',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
          overflow: 'hidden',
        }}
      >
        {value}
      </div>
    </div>
  );
}
