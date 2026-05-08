import Constants from 'expo-constants';

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || 'http://127.0.0.1:8000';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]; // Exponential backoff
const HEARTBEAT_INTERVAL = 15000; // 15 seconds
const CONNECTION_TIMEOUT = 10000; // 10 seconds

export const apiToWsUrl = (apiUrl, path, token) => {
  let wsUrl = (apiUrl || API_URL).replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
  const separator = wsUrl.includes('?') ? '&' : '?';
  const tokenPart = token ? `${separator}access_token=${encodeURIComponent(token)}` : '';
  return `${wsUrl}${path || '/ws/audio'}${tokenPart}`;
};

export const connectWS = (url, onMessage, setStatus, options = {}) => {
  let ws = null;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let heartbeatTimer = null;
  let connectionTimeout = null;
  let intentionallyClosed = false;
  let currentUrl = url;
  let currentOnMessage = onMessage;
  let currentSetStatus = setStatus;

  const clearTimers = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    if (connectionTimeout) {
      clearTimeout(connectionTimeout);
      connectionTimeout = null;
    }
  };

  const startHeartbeat = () => {
    clearTimers();
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
        } catch (e) {
          console.error('Heartbeat send error:', e);
        }
      }
    }, HEARTBEAT_INTERVAL);
  };

  const scheduleReconnect = () => {
    if (intentionallyClosed) return;
    if (reconnectAttempts >= RECONNECT_DELAYS.length) {
      currentSetStatus?.('Connection failed - max retries reached');
      return;
    }
    
    const delay = RECONNECT_DELAYS[reconnectAttempts];
    reconnectAttempts++;
    currentSetStatus?.(`Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempts})`);
    
    reconnectTimer = setTimeout(() => {
      if (!intentionallyClosed) {
        currentSetStatus?.('Reconnecting...');
        ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);
      }
    }, delay);
  };

  const createWebSocket = (url, onMessage, setStatus) => {
    clearTimers();
    connectionTimeout = setTimeout(() => {
      if (ws && ws.readyState !== WebSocket.OPEN) {
        console.log('Connection timeout');
        ws.close();
        setStatus?.('Connection timeout');
        scheduleReconnect();
      }
    }, CONNECTION_TIMEOUT);

    const newWs = new WebSocket(url);
    
    newWs.onopen = () => {
      clearTimers();
      reconnectAttempts = 0; // Reset on successful connection
      console.log("WebSocket connected:", url);
      setStatus?.("Connected");
      startHeartbeat();
    };
    
    newWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Handle pong responses for heartbeat
        if (data.type === 'pong') {
          return; // Don't forward pong to message handler
        }
        onMessage(data);
      } catch (error) {
        console.error("Message parse error:", error);
      }
    };
    
    newWs.onerror = (error) => {
      console.error("WebSocket error:", error);
      // Don't set status here - onclose will be called next
    };
    
    newWs.onclose = (event) => {
      clearTimers();
      console.log("WebSocket closed:", event.code, event.reason);
      
      if (!intentionallyClosed) {
        setStatus?.(`Disconnected (${event.code})`);
        scheduleReconnect();
      } else {
        setStatus?.('Disconnected');
      }
    };
    
    return newWs;
  };

  ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);

  // Return control object
  return {
    get readyState() { return ws?.readyState; },
    get isConnected() { return ws?.readyState === WebSocket.OPEN; },
    send: (data) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(data);
        return true;
      }
      return false;
    },
    close: () => {
      intentionallyClosed = true;
      clearTimers();
      reconnectAttempts = 0;
      if (ws) {
        ws.close();
        ws = null;
      }
    },
    updateHandlers: (newOnMessage, newSetStatus) => {
      currentOnMessage = newOnMessage;
      currentSetStatus = newSetStatus;
    }
  };
};