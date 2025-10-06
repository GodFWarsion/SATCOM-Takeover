import React, { useEffect, useState } from 'react';
import api from './api';

export default function LogPanel(){
  const [logs, setLogs] = useState([]);
  useEffect(()=>{
    let mounted = true;
    const fetchLogs = async ()=>{
      try {
        const data = await api.getLogs();
        if(mounted) setLogs(Array.isArray(data) ? data : (data.logs || []));
      } catch(e){
        console.warn('logs fetch failed', e);
      }
    };
    fetchLogs();
    const iv = setInterval(fetchLogs, 2000);
    return ()=>{ mounted=false; clearInterval(iv); };
  }, []);

  return (
    <div style={{padding:'8px'}}>
      <div style={{height:'100%', overflow:'auto', background:'#000', color:'#0f0', padding:'8px', borderRadius:4}}>
        {logs.length === 0 ? <div>No logs</div> : logs.slice().reverse().map((l, i)=><div key={i}><code>{l}</code></div>)}
      </div>
    </div>
  );
}
