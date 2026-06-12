import { useRef } from 'react';
import { STREAM_HEARTBEAT_MS, STREAM_HEARTBEAT_MAX_MISSES } from '../utils';

export function useStreamHeartbeat({ socketRef, setPipelineStage, setStatus }) {
  const streamHeartbeatRef = useRef({ timer: null, missed: 0 });

  function clearStreamHeartbeat() {
    if (streamHeartbeatRef.current?.timer) {
      window.clearInterval(streamHeartbeatRef.current.timer);
    }
    streamHeartbeatRef.current = { timer: null, missed: 0 };
  }

  function markStreamPong() {
    streamHeartbeatRef.current.missed = 0;
  }

  function startStreamHeartbeat(socket) {
    clearStreamHeartbeat();
    streamHeartbeatRef.current = { timer: null, missed: 0 };
    const timer = window.setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
      if (socketRef.current !== socket) {
        clearStreamHeartbeat();
        return;
      }
      if (socket.readyState !== WebSocket.OPEN) return;
      streamHeartbeatRef.current.missed += 1;
      if (streamHeartbeatRef.current.missed > STREAM_HEARTBEAT_MAX_MISSES) {
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
        if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
        setPipelineStage('Connection heartbeat missed');
        setStatus('Reconnecting stream...');
        try {
          socket.close();
        } catch {
          // Socket may already be closing.
        }
        return;
      }
      try {
        socket.send(JSON.stringify({ type: 'ping' }));
      } catch {
        clearStreamHeartbeat();
      }
    }, STREAM_HEARTBEAT_MS);
    streamHeartbeatRef.current.timer = timer;
  }

  return {
    streamHeartbeatRef,
    clearStreamHeartbeat,
    markStreamPong,
    startStreamHeartbeat,
  };
}
