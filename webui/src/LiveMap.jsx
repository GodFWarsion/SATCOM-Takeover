// src/LiveMap.jsx
import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import api from './api';

// Fix default Leaflet icon paths
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export default function LiveMap() {
  const [sats, setSats] = useState([]);
  const [tileUrl, setTileUrl] = useState(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
  );
  const [attribution, setAttribution] = useState(
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  );

  // Telemetry fetching
  useEffect(() => {
    let mounted = true;
    const fetchOnce = async () => {
      try {
        const data = await api.getTelemetry();
        const list = Array.isArray(data) ? data : [data];
        if (mounted) setSats(list);
      } catch (e) {
        console.warn('telemetry fetch failed', e);
      }
    };
    fetchOnce();
    const iv = setInterval(fetchOnce, 2000);
    return () => {
      mounted = false;
      clearInterval(iv);
    };
  }, []);

  const center = sats.length
    ? [sats[0].latitude || 0, sats[0].longitude || 0]
    : [20, 0];

  // Map layer options
  const tileOptions = [
    {
      name: 'OpenStreetMap',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
    {
      name: 'Carto Light',
      url: 'https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    },
    {
      name: 'Carto Dark',
      url: 'https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png',
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    },
  ];

  const handleLayerChange = (e) => {
    const selected = tileOptions.find((t) => t.name === e.target.value);
    if (selected) {
      setTileUrl(selected.url);
      setAttribution(selected.attribution);
    }
  };

  return (
    <div style={{ height: '100%', width: '100%' }}>
      {/* Map selector */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          left: 10,
          zIndex: 1000,
          background: 'rgba(30,30,30,0.8)',
          padding: '4px 8px',
          borderRadius: 4,
          color: '#fff',
        }}
      >
        <label>
          Map:
          <select
            value={tileOptions.find((t) => t.url === tileUrl)?.name || ''}
            onChange={handleLayerChange}
            style={{ marginLeft: 6 }}
          >
            {tileOptions.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <MapContainer center={center} zoom={2} style={{ height: '100%', width: '100%' }}>
        <TileLayer url={tileUrl} attribution={attribution} />
        {sats.map((sat, idx) => (
          <Marker key={idx} position={[sat.latitude || 0, sat.longitude || 0]}>
            <Popup>
              <b>{sat.id || 'SAT'}</b>
              <br />
              Status: {sat.status || 'N/A'}
              <br />
              Battery: {sat.battery || 'N/A'}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
