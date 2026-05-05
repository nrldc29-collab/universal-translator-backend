export const connectWS = (url, onMessage) => {
  const ws = new WebSocket(url);

  ws.onopen = () => console.log("connected");

  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data));
  };

  return ws;
};
