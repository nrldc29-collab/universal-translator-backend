import Constants from 'expo-constants';

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || '';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]; // Exponential backoff
const HEARTBEAT_INTERVAL = 15000; // 15 seconds
const CONNECTION_TIMEOUT = 10000; // 10 seconds
const PING_TIMEOUT = 5000; // 5 seconds for pong response
const MAX_RECONNECT_ATTEMPTS = 10;
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === '1');

const debugLog = (...args) => {
  if (DEBUG_LOGS) console.debug(...args);
};

export const apiToWsUrl = (apiUrl, path, token) => {
  let wsUrl = (apiUrl || API_URL).replace(/^https:/, 'wss:').replace(/^http:/, 'ws:');
  const separator = wsUrl.includes('?') ? '&' : '?';
  const tokenPart = token ? `${separator}access_token=${encodeURIComponent(token)}` : '';
  return `${wsUrl}${path || '/ws/audio'}${tokenPart}`;
};

export const connectWS = (url, onMessage, setStatus, options = {}) => {
  const onOpen = options.onOpen;
  const onClose = options.onClose;
  let ws = null;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let heartbeatTimer = null;
  let connectionTimeout = null;
  let pingTimeout = null;
  let intentionallyClosed = false;
  let currentUrl = url;
  let currentOnMessage = onMessage;
  let currentSetStatus = setStatus;
  let lastPongTime = Date.now();
  let connectionStartTime = Date.now();

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
    if (pingTimeout) {
      clearTimeout(pingTimeout);
      pingTimeout = null;
    }
  };

  const startHeartbeat = () => {
    clearTimers();
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
          
          // Set timeout for pong response
          pingTimeout = setTimeout(() => {
            const timeSincePong = Date.now() - lastPongTime;
            if (timeSincePong > PING_TIMEOUT) {
              debugLog('Ping timeout - no pong received');
              ws.close(4000, 'Ping timeout');
            }
          }, PING_TIMEOUT);
        } catch (e) {
          console.error('Heartbeat send error:', e);
        }
      }
    }, HEARTBEAT_INTERVAL);
  };

  const scheduleReconnect = () => {
    if (intentionallyClosed) return;
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      currentSetStatus?.('Connection failed - max retries reached');
      return;
    }
    
    const delay = RECONNECT_DELAYS[Math.min(reconnectAttempts, RECONNECT_DELAYS.length - 1)];
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
    intentionallyClosed = false;
    connectionStartTime = Date.now();
    
    connectionTimeout = setTimeout(() => {
      if (ws && ws.readyState !== WebSocket.OPEN) {
        debugLog('Connection timeout');
        ws.close(4001, 'Connection timeout');
        setStatus?.('Connection timeout');
        scheduleReconnect();
      }
    }, CONNECTION_TIMEOUT);

    const newWs = new WebSocket(url);
    
    newWs.onopen = () => {
      clearTimers();
      reconnectAttempts = 0; // Reset on successful connection
      const connectionTime = Date.now() - connectionStartTime;
      debugLog(`WebSocket connected in ${connectionTime}ms:`, url);
      currentSetStatus?.("Handshaking...");
      startHeartbeat();
      onOpen?.();
    };
    
    newWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Handle pong responses for heartbeat
        if (data.type === 'pong') {
          lastPongTime = Date.now();
          if (pingTimeout) {
            clearTimeout(pingTimeout);
            pingTimeout = null;
          }
          return; // Don't forward pong to message handler
        }
        currentOnMessage(data);
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
      const connectionDuration = Date.now() - connectionStartTime;
      debugLog(`WebSocket closed after ${connectionDuration}ms:`, event.code, event.reason);

      onClose?.(event);
      if (!intentionallyClosed) {
        // Don't reconnect on normal closure (1000) or if explicitly closed by server
        if (event.code === 1000 || event.code === 1001) {
          currentSetStatus?.('Disconnected');
        } else {
          currentSetStatus?.(`Disconnected (${event.code})`);
          scheduleReconnect();
        }
      } else {
        currentSetStatus?.('Disconnected');
      }
    };
    
    return newWs;
  };

  ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);

  // Return control object
  return {
    get readyState() { return ws?.readyState; },
    get isConnected() { return ws?.readyState === WebSocket.OPEN; },
    get reconnectAttempts() { return reconnectAttempts; },
    get connectionDuration() { return Date.now() - connectionStartTime; },
    send: (data) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          if (data instanceof ArrayBuffer) {
            ws.send(new Uint8Array(data));
          } else if (ArrayBuffer.isView(data)) {
            ws.send(data);
          } else {
            ws.send(data);
          }
          return true;
        } catch (e) {
          console.error('Send error:', e);
          return false;
        }
      }
      return false;
    },
    close: (code = 1000, reason = '') => {
      intentionallyClosed = true;
      clearTimers();
      reconnectAttempts = 0;
      if (ws) {
        ws.close(code, reason);
        ws = null;
      }
    },
    updateHandlers: (newOnMessage, newSetStatus) => {
      currentOnMessage = newOnMessage;
      currentSetStatus = newSetStatus;
    },
    forceReconnect: () => {
      intentionallyClosed = true;
      clearTimers();
      if (ws) {
        try {
          ws.close(1000, 'Manual reconnect');
        } catch {
          // Socket may already be closed.
        }
        ws = null;
      }
      intentionallyClosed = false;
      reconnectAttempts = 0;
      ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);
    }
  };
};
