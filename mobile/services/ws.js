export const apiToWsUrl = (apiUrl, path = '/ws/audio', token = '') => {
  const base = apiUrl.replace(/^http/, 'ws').replace(/\/$/, '');
  const separator = path.includes('?') ? '&' : '?';
  return token ? `${base}${path}${separator}access_token=${encodeURIComponent(token)}` : `${base}${path}`;
};

export const connectWS = (url, onMessage, onStatus, onOpen) => {
  const ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('CONNECTED');
    ws.send(JSON.stringify({ type: 'ping' }));
    onOpen?.(ws);
    onStatus?.('WebSocket connected');
  };

  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };

  ws.onerror = () => {
    onStatus?.('WebSocket error');
  };

  ws.onclose = () => {
    onStatus?.('WebSocket closed');
  };

  return ws;
};
