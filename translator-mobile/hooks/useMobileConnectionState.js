import { useState, useRef, useEffect } from 'react';

export function useMobileConnectionState() {
  const [status, setStatus] = useState('Idle');
  const [statusType, setStatusType] = useState('idle');
  const [isConnected, setIsConnected] = useState(false);
  const [networkState, setNetworkState] = useState(null);

  const isConnectedRef = useRef(false);
  useEffect(() => {
    isConnectedRef.current = isConnected;
  }, [isConnected]);

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
