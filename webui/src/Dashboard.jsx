// src/Dashboard.jsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

import LiveMap from './components/LiveMap';
import StatusPanel from './components/StatusPanel';
import TelecommandConsole from './components/TelecommandConsole';
import LogPanel from './components/LogPanel';
import './Dashboard.css';

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="dashboard">

      {/* 🔹 Top Navigation Bar */}
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          zIndex: 1000,
        }}
      >
        <button
          onClick={() => navigate('/gnss')}
          style={{
            padding: '8px 14px',
            fontWeight: 'bold',
            cursor: 'pointer',
          }}
        >
          GNSS Telemetry
        </button>
      </div>

      {/* Windowed Map */}
      <div className="map-window glass">
        <LiveMap />
      </div>

      {/* Status Panel */}
      <div className="status-panel glass">
        <StatusPanel />
      </div>

      {/* Telecommand Console */}
      <div className="telecommand-console glass">
        <TelecommandConsole />
      </div>

      {/* Logs Panel */}
      <div
        className="logs-panel glass"
        style={{
          position: 'absolute',
          bottom: 20,
          left: 20,
          width: 400,
          height: 200,
        }}
      >
        <LogPanel />
      </div>

    </div>
  );
}
