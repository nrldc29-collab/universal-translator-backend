import { useState, useRef } from 'react';

export function useMobileConnectionState() {
  const [status, setStatus] = useState('Idle');
  const [statusType, setStatusType] = useState('idle');
  const [isConnected, setIsConnected] = useState(false);
  const [networkState, setNetworkState] = useState(null);

  // Updated synchronously in App.js alongside setIsConnected (not from React state).
  const isConnectedRef = useRef(false);

  return {
    status,
    setStatus,
    statusType,
    setStatusType,
    isConnected,
    setIsConnected,
    isConnectedRef,
    networkState,
    setNetworkState,
  };
}
