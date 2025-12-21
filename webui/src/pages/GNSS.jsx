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

export default function GNSS() {
  const [gnss, setGnss] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    let index = 0;

    const fetchGNSS = async () => {
      try {
        const res = await fetch(files[index]);
        console.log('HTTP status:', res.status);
        console.log('Content-Type:', res.headers.get('content-type'));
        console.log('Raw JSON:', json);

        const json = await res.json();
        const raw = json.data ?? json;
        const sample = Array.isArray(raw)
        ? raw[Math.floor(Math.random() * raw.length)]
        : raw;


        const parsed = {
        lat: safe(sample.lat ?? sample.latitude),
        lon: safe(sample.lon ?? sample.longitude),
        alt: safe(sample.alt ?? sample.height),
        vel: safe(sample.vel_mps ?? sample.speed),
        fix: sample.fix_quality ?? sample.fix ?? '—',
        sats: sample.sat_count ?? sample.sats ?? '—',
        spoof: Array.isArray(sample.spoof_flags) ? sample.spoof_flags : [],
        };


        if (parsed.lat !== null && parsed.lon !== null) {
          setGnss(parsed);

          setHistory((prev) => [
            ...prev.slice(-50),
            {
              time: new Date().toLocaleTimeString(),
              lat: parsed.lat,
              lon: parsed.lon,
              alt_km: parsed.alt !== null ? parsed.alt / 1000 : null,
            },
          ]);
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
