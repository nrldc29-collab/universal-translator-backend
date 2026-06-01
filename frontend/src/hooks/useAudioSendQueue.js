import { useRef } from 'react';
import { MAX_AUDIO_SEND_QUEUE, MAX_BUFFERED_AUDIO_CHUNKS } from '../utils';

export function useAudioSendQueue({ debugLog = () => {} } = {}) {
  const audioSendQueueRef = useRef([]);

  function sendAudioPacket(socket, packet) {
    if (socket.readyState !== WebSocket.OPEN) return false;
    try {
      debugLog('sending audio chunk', packet.meta.bytes, packet.meta.mime_type);
      socket.send(JSON.stringify(packet.meta));
      socket.send(packet.buffer);
      return true;
    } catch (e) {
      console.error('WebSocket send failed:', e);
      return false;
    }
  }

  function queueAudioPacket(packet) {
    const queue = audioSendQueueRef.current;
    if (queue.length >= MAX_BUFFERED_AUDIO_CHUNKS) queue.shift();
    queue.push(packet);
  }

  function flushAudioSendQueue(socket) {
    const queue = audioSendQueueRef.current;
    while (queue.length > 0 && socket.readyState === WebSocket.OPEN) {
      const packet = queue[0];
      if (!sendAudioPacket(socket, packet)) break;
      queue.shift();
    }
  }

  function drainQueue() {
    audioSendQueueRef.current = [];
  }

  return {
    audioSendQueueRef,
    MAX_AUDIO_SEND_QUEUE,
    sendAudioPacket,
    queueAudioPacket,
    flushAudioSendQueue,
    drainQueue,
  };
}
