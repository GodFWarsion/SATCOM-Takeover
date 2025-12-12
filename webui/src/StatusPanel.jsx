import React, { useEffect, useState } from 'react';
import api from './api';

export default function StatusPanel() {
  const [status, setStatus] = useState({});

  useEffect(() => {
    let mounted = true;

    const fetchStatus = async () => {
      try {
        const data = await api.getGroundState();
        if (mounted) setStatus(data || {});
      } catch (err) {
        console.error("Status fetch failed:", err);
        if (mounted) setStatus({});
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  return (
    <div style={{ background: '#222', color: '#0f0', padding: 8, borderRadius: 4 }}>
      <div>Link: {status.link || 'N/A'}</div>
      <div>Last Seq: {status.last_seq ?? 'N/A'}</div>
      <div>CRC Errors: {status.crc_errors ?? 0}</div>
      <div>Last Update: {status.last_update || 'N/A'}</div>
    </div>
  );
}
