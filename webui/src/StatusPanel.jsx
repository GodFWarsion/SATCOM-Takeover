// src/StatusPanel.jsx
import React, { useEffect, useState } from 'react';

function StatusPanel() {
  const [status, setStatus] = useState({});

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/ground_state');
        const data = await res.json();
        setStatus(data);
      } catch (err) {
        console.error('status fetch failed', err);
      }
    };
    fetchStatus();
    const iv = setInterval(fetchStatus, 5000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div style={{
      background: '#111',        // dark background
      color: '#0f0',             // green text
      padding: '10px',
      borderRadius: '4px',
      width: '100%',
      height: '100%'
    }}>
      <h3 style={{marginTop:0}}>Status Panel</h3>
      <p>Satellite: {status.satStatus || 'N/A'}</p>
      <p>Ground Station: {status.groundStatus || 'N/A'}</p>
    </div>
  );
}
export default StatusPanel;
