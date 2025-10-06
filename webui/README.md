Satellite WebUI scaffold
========================

Files included:
- package.json
- Dockerfile
- public/index.html
- src/index.js
- src/App.jsx
- src/LiveMap.jsx
- src/LogPanel.jsx
- src/api.js

How to run (development):
1. cd satellite-webui
2. npm install
3. npm start
- By default the app will call the API at the path defined by REACT_APP_API_BASE env var (e.g. http://localhost:5000).
  If not set, it will fetch '/api/telemetry' (use proxy or reverse proxy).

How to run in Docker:
1. docker build -t satellite-webui .
2. docker run -p 3000:3000 -e REACT_APP_API_BASE=http://<ground_host>:5000 satellite-webui

Notes:
- This scaffold is minimal and intended to be connected to your backend (ground station) APIs.
- The LiveMap component uses react-leaflet and OpenStreetMap tiles.
