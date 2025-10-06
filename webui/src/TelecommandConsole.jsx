// src/TelecommandConsole.jsx
import React, { useState } from 'react';

function TelecommandConsole() {
  const [command, setCommand] = useState('');

  const sendCommand = () => {
    fetch('/api/send_command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command })
    });
  };

  return (
    <div>
      <h3>Telecommand Console</h3>
      <input
        value={command}
        onChange={e => setCommand(e.target.value)}
        placeholder="Enter command"
        style={{ width: '80%' }}
      />
      <button onClick={sendCommand}>Send</button>
    </div>
  );
}
export default TelecommandConsole;
