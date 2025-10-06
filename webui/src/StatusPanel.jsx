// src/StatusPanel.jsx
import React, { useEffect, useState } from 'react';

function StatusPanel() {
  const [status, setStatus] = useState({});
  useEffect(() => {
    fetch('/api/ground_state')
      .then(res => res.json())
      .then(data => setStatus(data));
  }, []);
  return (
    <div>
      <h3>Status</h3>
      <p>Satellite: {status.satStatus}</p>
      <p>Ground Station: {status.groundStatus}</p>
     {/* Future considerations for status fields */}
    </div>
  );
}
export default StatusPanel;
