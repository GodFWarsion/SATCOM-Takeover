// src/api.js

const API_BASE =
  process.env.REACT_APP_API_BASE || "http://ground:5003/api";

const MONITOR_API =
  process.env.REACT_APP_MONITOR_API_URL || "http://monitoring:5002/api";

const SAT_BASE =
  process.env.REACT_APP_SAT_API || "http://satellite:5001/api";

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
    const data = await safeFetch(`${SAT_BASE}/telemetry`);
    return data?.satellites ? data : { satellites: [] };
  },

  // ---- Ground subsystem ----
  getGroundState: async () => {
    const data = await safeFetch(`${API_BASE}/ground_state`);
    return data || { antennas: [], status: "unknown" };
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
