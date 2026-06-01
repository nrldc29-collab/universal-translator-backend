/**
 * useReliabilityMonitor -- track system health and auto-recover from failures
 * 
 * Features:
 * - Tracks consecutive errors per subsystem
 * - Implements exponential backoff for reconnection
 * - Auto-resets health after successful operations
 * - Graceful degradation when services fail
 */

import { useCallback, useRef, useState, useEffect } from 'react';

const MAX_BACKOFF_MS = 30000; // 30 seconds max backoff
const INITIAL_BACKOFF_MS = 1000; // 1 second initial

export default function useReliabilityMonitor() {
  // Error tracking per subsystem
  const errorCounts = useRef({
    websocket: 0,
    tts: 0,
    translation: 0,
    stt: 0,
    audio: 0,
  });

  // Last success timestamp per subsystem
  const lastSuccess = useRef({
    websocket: Date.now(),
    tts: Date.now(),
    translation: Date.now(),
    stt: Date.now(),
    audio: Date.now(),
  });

  // Circuit breaker states
  const [circuitStates, setCircuitStates] = useState({
    websocket: 'closed', // closed, open, half_open
    tts: 'closed',
    translation: 'closed',
    stt: 'closed',
    audio: 'closed',
  });

  // Current backoff delays
  const backoffDelays = useRef({
    websocket: INITIAL_BACKOFF_MS,
    tts: INITIAL_BACKOFF_MS,
    translation: INITIAL_BACKOFF_MS,
    stt: INITIAL_BACKOFF_MS,
    audio: INITIAL_BACKOFF_MS,
  });

  // Record success and reset error count
  const recordSuccess = useCallback((subsystem) => {
    errorCounts.current[subsystem] = 0;
    lastSuccess.current[subsystem] = Date.now();
    backoffDelays.current[subsystem] = INITIAL_BACKOFF_MS;
    
    // If circuit was open/half_open, close it
    if (circuitStates[subsystem] !== 'closed') {
      setCircuitStates(prev => ({ ...prev, [subsystem]: 'closed' }));
    }
  }, [circuitStates]);

  // Record failure with exponential backoff
  const recordFailure = useCallback((subsystem, error) => {
    const count = ++errorCounts.current[subsystem];
    const consecutiveErrors = count;
    
    // Calculate exponential backoff
    const newDelay = Math.min(
      INITIAL_BACKOFF_MS * Math.pow(2, consecutiveErrors - 1),
      MAX_BACKOFF_MS
    );
    backoffDelays.current[subsystem] = newDelay;

    // Open circuit after 3 consecutive errors
    if (consecutiveErrors >= 3 && circuitStates[subsystem] === 'closed') {
      setCircuitStates(prev => ({ ...prev, [subsystem]: 'open' }));
      
      // Auto-attempt recovery after backoff
      setTimeout(() => {
        setCircuitStates(prev => ({ 
          ...prev, 
          [subsystem]: prev[subsystem] === 'open' ? 'half_open' : prev[subsystem]
        }));
      }, newDelay);
    }

    return {
      consecutiveErrors,
      backoffMs: newDelay,
      circuitOpen: circuitStates[subsystem] === 'open',
    };
  }, [circuitStates]);

  // Check if operation should proceed (circuit breaker)
  const shouldProceed = useCallback((subsystem) => {
    const state = circuitStates[subsystem];
    if (state === 'open') return false;
    if (state === 'half_open') {
      // Allow one test call in half-open state
      setCircuitStates(prev => ({ ...prev, [subsystem]: 'open' }));
      return true;
    }
    return true;
  }, [circuitStates]);

  // Get current health status
  const getHealthStatus = useCallback(() => {
    const now = Date.now();
    const health = {};
    
    Object.keys(errorCounts.current).forEach(subsystem => {
      const errors = errorCounts.current[subsystem];
      const lastSuccess = lastSuccess.current[subsystem];
      const circuit = circuitStates[subsystem];
      const timeSinceSuccess = now - lastSuccess;
      
      health[subsystem] = {
        status: circuit === 'open' ? 'degraded' : errors > 0 ? 'warning' : 'healthy',
        consecutiveErrors: errors,
        timeSinceSuccessMs: timeSinceSuccess,
        circuitState: circuit,
        backoffMs: backoffDelays.current[subsystem],
      };
    });
    
    return health;
  }, [circuitStates]);

  // Force reset (manual recovery)
  const forceReset = useCallback((subsystem) => {
    errorCounts.current[subsystem] = 0;
    backoffDelays.current[subsystem] = INITIAL_BACKOFF_MS;
    setCircuitStates(prev => ({ ...prev, [subsystem]: 'closed' }));
    lastSuccess.current[subsystem] = Date.now();
  }, []);

  // Global health check
  const isHealthy = useCallback(() => {
    return Object.values(circuitStates).every(state => state === 'closed');
  }, [circuitStates]);

  // Auto-recovery check interval
  useEffect(() => {
    const interval = window.setInterval(() => {
      const health = getHealthStatus();
      
      // Log degraded services
      Object.entries(health).forEach(([subsystem, status]) => {
        if (status.status === 'degraded') {
          console.warn(`[ReliabilityMonitor] ${subsystem} is degraded:`, status);
        }
      });
    }, 10000); // Check every 10 seconds

    return () => window.clearInterval(interval);
  }, [getHealthStatus]);

  return {
    recordSuccess,
    recordFailure,
    shouldProceed,
    getHealthStatus,
    forceReset,
    isHealthy,
    circuitStates,
  };
}
