import { useRef } from 'react';
import { STREAM_HEARTBEAT_MS, STREAM_HEARTBEAT_MAX_MISSES } from '../utils';

export function useStreamHeartbeat({ socketRef, setConnectionStatus, setPipelineStage, setStatus }) {
  const streamHeartbeatRef = useRef({ timer: null, missed: 0 });

  function clearStreamHeartbeat() {
    if (streamHeartbeatRef.current?.timer) {
      window.clearInterval(streamHeartbeatRef.current.timer);
    }
    streamHeartbeatRef.current = { timer: null, missed: 0 };
  }

  function markStreamPong() {
    streamHeartbeatRef.current.missed = 0;
    setConnectionStatus('online');
  }

  function startStreamHeartbeat(socket) {
    clearStreamHeartbeat();
    streamHeartbeatRef.current = { timer: null, missed: 0 };
    const timer = window.setInterval(() => {
      if (socketRef.current !== socket) {
        clearStreamHeartbeat();
        return;
      }
      if (socket.readyState !== WebSocket.OPEN) return;
      streamHeartbeatRef.current.missed += 1;
      if (streamHeartbeatRef.current.missed > STREAM_HEARTBEAT_MAX_MISSES) {
        setPipelineStage('Connection heartbeat missed');
        setStatus('Reconnecting stream...');
        socket.close();
        return;
      }
      socket.send(JSON.stringify({ type: 'ping' }));
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
