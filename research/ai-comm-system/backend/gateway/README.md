# Gateway Service (Web + WebSocket)

- Serves static frontend
- WebSocket hub for real-time events
- Exposes /metrics for Prometheus scraping
- In production, place behind Nginx/Ingress with sticky sessions for Socket.io
