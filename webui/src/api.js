// src/api.js
const BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:5001/api';

export async function getTelemetry() {
  try {
    const res = await fetch(`${BASE_URL}/telemetry`);
    if (!res.ok) throw new Error('Failed to fetch telemetry');
    const data = await res.json();
    console.log('Telemetry response:', data);
    return data.satellites || [];
  } catch (err) {
    console.error('getTelemetry error:', err);
    return [];
  }
}


export async function getLogs() {
  try {
    const res = await fetch(`${BASE_URL}/logs`);
    if (!res.ok) return [];
    return res.json();
  } catch (err) {
    console.error('getLogs error:', err);
    return [];
  }
}

export async function getGroundState() {
  try {
    const res = await fetch(`${BASE_URL}/ground_state`);
    if (!res.ok) return {};
    return res.json();
  } catch (err) {
    console.error('getGroundState error:', err);
    return {};
  }
}

export default { getTelemetry, getLogs, getGroundState };