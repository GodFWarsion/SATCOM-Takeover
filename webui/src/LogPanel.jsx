// src/LogPanel.jsx
import React, { useEffect, useState } from 'react';
import api from './api';

export default function LogPanel() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    let mounted = true;
    const fetchLogs = async () => {
      const data = await api.getLogs();
      if (mounted) setLogs(Array.isArray(data) ? data : (data.logs || []));
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  return (
    // src/LogPanel.jsx
<div style={{
  height:'100%',
  overflow:'auto',
  background:'#111', 
  color:'#0f0', 
  padding:'8px', 
  borderRadius:4,
  fontFamily: 'monospace'
}}>
  {logs.length === 0 ? 
    <div>No logs</div> : 
    logs.slice().reverse().map((l,i)=><div key={i}>{l}</div>)
  }
</div>

  );
}
