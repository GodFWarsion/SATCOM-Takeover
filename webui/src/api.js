const BASE = process.env.REACT_APP_API_BASE || '';

export async function getTelemetry() {
  const res = await fetch('/telemetry');
  const text = await res.text();
  console.log('telemetry raw response:', text);
  return JSON.parse(text);
}


async function getLogs(){
  const res = await fetch(`${BASE}/api/logs`);
  if(!res.ok) return [];
  return res.json();
}

export default { getTelemetry, getLogs };
