// src/Dashboard.jsx
import React from 'react';
import LiveMap from './LiveMap';
import StatusPanel from './StatusPanel';
import TelecommandConsole from './TelecommandConsole';
import LogPanel from './LogPanel';
import './Dashboard.css';

export default function Dashboard() {
  return (
    <div className="dashboard">
      {/* Windowed Map */}
      <div className="map-window glass">
        <LiveMap />
      </div>

      {/* Status Panel - top-right */}
      <div className="status-panel glass">
        <StatusPanel />
      </div>

      {/* Telecommand Console - bottom-right */}
      <div className="telecommand-console glass">
        <TelecommandConsole />
      </div>

      {/* Logs Panel - bottom-left */}
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
