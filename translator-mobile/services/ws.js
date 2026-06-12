import Constants from 'expo-constants';
import { wsBridgeStatuses } from '../constants/productVoice';

const WS_STATUS = wsBridgeStatuses();

const API_URL = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl || '';

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]; // Exponential backoff
const HEARTBEAT_INTERVAL = 8000; // 8 seconds — faster weak-Wi-Fi detection
const HEARTBEAT_INTERVAL_DEGRADED = 5000;
const DEFAULT_CONNECTION_TIMEOUT = 20000;
const TUNNEL_CONNECTION_TIMEOUT = 35000;
const PING_TIMEOUT = 5000; // 5 seconds for pong response
export const MAX_RECONNECT_ATTEMPTS = 10;
const MAX_SEND_QUEUE = 32;
const DEBUG_LOGS = Boolean(__DEV__ || process.env.EXPO_PUBLIC_DEBUG_LOGS === '1');

const debugLog = (...args) => {
  if (DEBUG_LOGS) console.debug(...args);
};

export function wsSocketHasAuthToken(url) {
  return /[?&](?:access_token|token)=/.test(String(url || ""));
}

export const apiToWsUrl = (apiUrl, path, token) => {
  const raw = String(apiUrl || API_URL || "").trim().replace(/\/+$/, "");
  const wsBase = raw.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
  const [origin, queryString = ""] = wsBase.split("?");
  const wsPath = path || "/ws/audio";
  const normalizedPath = wsPath.startsWith("/") ? wsPath : `/${wsPath}`;
  const params = new URLSearchParams(queryString);
  if (token) {
    params.set("access_token", token);
  }
  const query = params.toString();
  return query ? `${origin}${normalizedPath}?${query}` : `${origin}${normalizedPath}`;
};

export const connectWS = (url, onMessage, setStatus, options = {}) => {
  const onOpen = options.onOpen;
  const onClose = options.onClose;
  const onReconnectProgress = options.onReconnectProgress;
  const onReconnectFailed = options.onReconnectFailed;
  const shouldReconnect = options.shouldReconnect;
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
  let forceReconnectPending = false;
  const sendQueue = [];
  let flushingQueue = false;

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

  const heartbeatIntervalMs = () => {
    if (sendQueue.length > 0) return 4000;
    return reconnectAttempts > 0 ? HEARTBEAT_INTERVAL_DEGRADED : HEARTBEAT_INTERVAL;
  };

  const isAudioPayload = (data) => data instanceof ArrayBuffer || ArrayBuffer.isView(data);

  const enqueueSend = (data) => {
    if (sendQueue.length >= MAX_SEND_QUEUE) {
      if (isAudioPayload(data)) {
        const audioIndex = sendQueue.findIndex((item) => isAudioPayload(item));
        if (audioIndex >= 0) {
          sendQueue.splice(audioIndex, 1);
        } else {
          sendQueue.shift();
        }
      }
    }
    sendQueue.push(data);
  };

  const clearStaleAudioFromQueue = () => {
    for (let index = sendQueue.length - 1; index >= 0; index -= 1) {
      if (isAudioPayload(sendQueue[index])) {
        sendQueue.splice(index, 1);
      }
    }
  };

  const flushSendQueue = () => {
    if (flushingQueue || intentionallyClosed || !canAutoReconnect()) return;
    const active = ws;
    if (!active || active.readyState !== WebSocket.OPEN) return;
    flushingQueue = true;
    while (sendQueue.length > 0 && active.readyState === WebSocket.OPEN) {
      const item = sendQueue[0];
      try {
        if (item instanceof ArrayBuffer) {
          active.send(new Uint8Array(item));
        } else if (ArrayBuffer.isView(item)) {
          active.send(item);
        } else {
          active.send(item);
        }
        sendQueue.shift();
      } catch (error) {
        console.error('Queued send error:', error);
        break;
      }
    }
    flushingQueue = false;
  };

  const startHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    if (pingTimeout) {
      clearTimeout(pingTimeout);
      pingTimeout = null;
    }
    heartbeatTimer = setInterval(() => {
      if (intentionallyClosed || !canAutoReconnect()) {
        if (pingTimeout) {
          clearTimeout(pingTimeout);
          pingTimeout = null;
        }
        return;
      }
      const active = ws;
      if (active && active.readyState === WebSocket.OPEN) {
        try {
          active.send(JSON.stringify({ type: 'ping' }));

          if (pingTimeout) {
            clearTimeout(pingTimeout);
            pingTimeout = null;
          }
          // Set timeout for pong response
          pingTimeout = setTimeout(() => {
            if (!canAutoReconnect()) return;
            if (
              !intentionallyClosed
              && ws === active
              && ws?.readyState === WebSocket.OPEN
              && Date.now() - lastPongTime > PING_TIMEOUT
            ) {
              debugLog('Ping timeout - no pong received');
              try {
                ws.close(4000, 'Ping timeout');
              } catch {
                // Socket may already be closed.
              }
            }
          }, PING_TIMEOUT);
        } catch (e) {
          console.error('Heartbeat send error:', e);
        }
      }
    }, heartbeatIntervalMs());
  };

  const canAutoReconnect = () => {
    if (intentionallyClosed) return false;
    if (typeof shouldReconnect === "function" && !shouldReconnect()) return false;
    return true;
  };

  const scheduleReconnect = () => {
    if (!canAutoReconnect()) return;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      currentSetStatus?.(WS_STATUS.maxRetriesFailed);
      onReconnectProgress?.(null);
      onReconnectFailed?.({ reason: "max_retries", attempts: reconnectAttempts });
      return;
    }
    
    const delay = RECONNECT_DELAYS[Math.min(reconnectAttempts, RECONNECT_DELAYS.length - 1)];
    reconnectAttempts++;
    onReconnectProgress?.({
      attempt: reconnectAttempts,
      maxAttempts: MAX_RECONNECT_ATTEMPTS,
      delayMs: delay,
    });
    currentSetStatus?.(WS_STATUS.reconnectIn(delay / 1000, reconnectAttempts));
    
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (!canAutoReconnect()) return;
      const live = ws;
      if (live && (live.readyState === WebSocket.OPEN || live.readyState === WebSocket.CONNECTING)) return;
      currentSetStatus?.(WS_STATUS.reconnectingEllipsis);
      ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);
    }, delay);
  };

  const connectionTimeoutMs = (targetUrl) => (
    /^wss:/i.test(String(targetUrl || "")) ? TUNNEL_CONNECTION_TIMEOUT : DEFAULT_CONNECTION_TIMEOUT
  );

  const createWebSocket = (url, onMessage, setStatus) => {
    clearTimers();
    intentionallyClosed = false;
    connectionStartTime = Date.now();

    const newWs = new WebSocket(url);
    ws = newWs;

    connectionTimeout = setTimeout(() => {
      if (ws !== newWs || intentionallyClosed || !canAutoReconnect()) return;
      if (newWs.readyState === WebSocket.OPEN) return;
      if (newWs.readyState !== WebSocket.CONNECTING) return;
      debugLog('Connection timeout');
      setStatus?.(WS_STATUS.timeout);
      try {
        newWs.close(4001, 'Connection timeout');
      } catch {
        // Socket may already be closed.
      }
    }, connectionTimeoutMs(url));

    newWs.onopen = () => {
      if (ws !== newWs || intentionallyClosed) {
        if (ws === newWs) {
          try { newWs.close(1000, 'Superseded'); } catch { /* already closed */ }
        }
        return;
      }
      clearTimers();
      reconnectAttempts = 0; // Reset on successful connection
      onReconnectProgress?.(null);
      lastPongTime = Date.now();
      const connectionTime = Date.now() - connectionStartTime;
      debugLog(`WebSocket connected in ${connectionTime}ms:`, url);
      currentSetStatus?.(WS_STATUS.handshaking);
      if (canAutoReconnect()) {
        startHeartbeat();
      }
      clearStaleAudioFromQueue();
      flushSendQueue();
      onOpen?.();
    };
    
    newWs.onmessage = (event) => {
      if (ws !== newWs) return;
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
      if (ws !== newWs) return;
      console.error("WebSocket error:", error);
      // Don't set status here - onclose will be called next
    };
    
    newWs.onclose = (event) => {
      const isActiveSocket = ws === newWs;
      const completingForceReplace = forceReconnectPending && !isActiveSocket;
      if (!isActiveSocket && !completingForceReplace) {
        debugLog("Ignoring stale WebSocket close");
        return;
      }
      const wasIntentional = intentionallyClosed;
      const shouldReplace = forceReconnectPending;
      if (isActiveSocket) {
        ws = null;
      }
      forceReconnectPending = false;
      clearTimers();
      const connectionDuration = Date.now() - connectionStartTime;
      debugLog(`WebSocket closed after ${connectionDuration}ms:`, event.code, event.reason);

      if (shouldReplace) {
        if (!canAutoReconnect()) return;
        intentionallyClosed = false;
        reconnectAttempts = 0;
        ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);
        return;
      }

      const willReconnect = canAutoReconnect()
        && event.code !== 1000
        && event.code !== 1001
        && event.code !== 1013
        && reconnectAttempts < MAX_RECONNECT_ATTEMPTS;
      if (!wasIntentional) {
        onClose?.({ code: event.code, reason: event.reason || '', willReconnect });
      }

      if (!intentionallyClosed) {
        if (event.code === 1000 || event.code === 1001) {
          currentSetStatus?.(WS_STATUS.disconnected);
        } else if (willReconnect) {
          scheduleReconnect();
        } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          currentSetStatus?.(WS_STATUS.maxRetriesFailed);
          onReconnectProgress?.(null);
          onReconnectFailed?.({ reason: "max_retries", attempts: reconnectAttempts });
        } else {
          currentSetStatus?.(WS_STATUS.disconnected);
        }
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
    isReconnecting() {
      return Boolean(reconnectTimer);
    },
    get connectionDuration() { return Date.now() - connectionStartTime; },
    getUrl: () => currentUrl,
    send: (data) => {
      if (intentionallyClosed || !canAutoReconnect()) return false;
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
          enqueueSend(data);
          return false;
        }
      }
      if (canAutoReconnect()) {
        enqueueSend(data);
      }
      return false;
    },
    flushQueue: flushSendQueue,
    queuedSends: () => sendQueue.length,
    dispose: () => {
      intentionallyClosed = true;
      forceReconnectPending = false;
      clearTimers();
      reconnectAttempts = 0;
      currentOnMessage = () => {};
      currentSetStatus = () => {};
      const closing = ws;
      ws = null;
      if (closing && closing.readyState !== WebSocket.CLOSED && closing.readyState !== WebSocket.CLOSING) {
        try {
          closing.close(1000, 'Disposed');
        } catch {
          // Socket may already be closed.
        }
      }
    },
    close: (code = 1000, reason = '') => {
      intentionallyClosed = true;
      forceReconnectPending = false;
      const hadReconnectTimer = Boolean(reconnectTimer);
      clearTimers();
      reconnectAttempts = 0;
      currentOnMessage = () => {};
      currentSetStatus = () => {};
      if (hadReconnectTimer) {
        currentSetStatus?.(WS_STATUS.disconnected);
      }
      const closing = ws;
      ws = null;
      if (closing) {
        try {
          closing.close(code, reason);
        } catch {
          // Socket may already be closed.
        }
        onClose?.({ code, reason, willReconnect: false });
      } else if (hadReconnectTimer) {
        onClose?.({ code, reason, willReconnect: false });
      }
    },
    updateHandlers: (newOnMessage, newSetStatus) => {
      currentOnMessage = newOnMessage;
      currentSetStatus = newSetStatus;
    },
    updateUrl: (nextUrl) => {
      if (!nextUrl) return;
      currentUrl = nextUrl;
      reconnectAttempts = 0;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    },
    resetReconnectState: () => {
      reconnectAttempts = 0;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    },
    forceReconnect: (nextUrl) => {
      if (nextUrl) currentUrl = nextUrl;
      intentionallyClosed = true;
      forceReconnectPending = true;
      clearTimers();
      reconnectAttempts = 0;
      const closing = ws;
      if (closing) {
        ws = null;
        try {
          closing.close(1000, 'Manual reconnect');
        } catch {
          // Socket may already be closed.
        }
      } else if (canAutoReconnect()) {
        forceReconnectPending = false;
        intentionallyClosed = false;
        ws = createWebSocket(currentUrl, currentOnMessage, currentSetStatus);
      } else {
        forceReconnectPending = false;
        intentionallyClosed = false;
      }
    },
  };
};
