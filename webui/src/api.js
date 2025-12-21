// src/api.js
const API_BASE = "http://localhost:5003/api";
const MONITOR_API = "http://localhost:5002/api";
const SAT_BASE = "http://localhost:5001/api";


// ---- shared safe fetch wrapper ----
async function safeFetch(url) {
  try {
    const res = await fetch(url, {
      headers: { "Accept": "application/json" }
    });

    if (!res.ok) {
      console.error(`❌ API error ${res.status}:`, url);
      return null;
    }

    // Some endpoints may return empty or non-JSON bodies → catch gracefully
    try {
      return await res.json();
    } catch {
      console.warn("⚠️ API returned non-JSON:", url);
      return null;
    }

  } catch (err) {
    console.error("❌ Fetch failed:", url, err);
    return null; // Never crash React
  }
}

export default {
  // ---- SAT subsystem ----
  getTelemetry: async () => {
  const res = await safeFetch(`${SAT_BASE}/telemetry`);
  return res?.data?.satellites
    ? { satellites: res.data.satellites }
    : { satellites: [] };
  },

  // ---- Ground subsystem ----
  getGroundState: async () => {
  const res = await safeFetch(`${API_BASE}/ground_state`);
  return res?.data || {};
},

  // ---- SIEM/Monitoring ----
  getLogs: async () => {
    const data = await safeFetch(`${MONITOR_API}/logs`);
    return Array.isArray(data) ? data : data?.logs || [];
  },

  getAlerts: async () => {
    const data = await safeFetch(`${MONITOR_API}/alerts`);
    return Array.isArray(data) ? data : [];
  },
};
