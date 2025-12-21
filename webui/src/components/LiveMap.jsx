import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import api from '../api';


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

  const tileOptions = [
    { name: 'OpenStreetMap', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' },
    { name: 'Carto Light', url: 'https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png', attribution: '&copy; CARTO' },
    { name: 'Carto Dark', url: 'https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png', attribution: '&copy; CARTO' },
  ];

  const handleLayerChange = (e) => {
    const selected = tileOptions.find((t) => t.name === e.target.value);
    if (selected) {
      setTileUrl(selected.url);
      setAttribution(selected.attribution);
    }
  };

  useEffect(() => {
  let mounted = true;

  // <--- Replace the old fetchTelemetry with this
  const fetchTelemetry = async () => {
    try {
      const data = await api.getTelemetry(); // data = { satellites: [...], timestamp: ... }
      if (mounted) setSats(data.satellites || []); // only the array
    } catch (err) {
      console.error('Telemetry fetch failed:', err);
    }
  };

  fetchTelemetry();
  const interval = setInterval(fetchTelemetry, 5000); // refresh every 5s

  return () => {
    mounted = false;
    clearInterval(interval);
  };
}, []);
  useEffect(() => {
    console.log("🛰️ Satellites in state:", sats);
  }, [sats]);


  const center = sats.length ? [sats[0].lat, sats[0].lon] : [20, 0];

  return (
    <div style={{ height: '100vh', width: '100%' }}>
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

      <MapContainer
  center={center}
  zoom={2}
  style={{ height: '100%', width: '100%' }}
  whenReady={(map) => {
    setTimeout(() => map.target.invalidateSize(), 200);
  }}
>

        <TileLayer url={tileUrl} attribution={attribution} />

        {sats.length === 0 ? null : sats.map((sat, idx) => (
          <CircleMarker
            key={idx}
            center={[sat.lat || 0, sat.lon || 0]}
            radius={16}
            fillColor={sat.status === 'ACTIVE' ? '#00ff00' : '#ff0000'}
            color="#ff0000"
            weight={2}
            fillOpacity={0.8}
          >
            <Popup>
              <div>
                <b>{sat.name || sat.id}</b><br />
                Status: {sat.status || 'N/A'}<br />
                Altitude: {sat.alt || 'N/A'} km<br />
                Velocity: {sat.velocity || 'N/A'} km/s
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
