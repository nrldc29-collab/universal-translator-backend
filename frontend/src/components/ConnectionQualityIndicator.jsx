/**
 * ConnectionQualityIndicator -- Shows network connection quality with visual indicator
 * Displays latency bars, connection status, and auto-reconnect status
 */

import React from 'react';
import { Wifi, WifiOff, AlertTriangle, Activity, CheckCircle2 } from 'lucide-react';

export default function ConnectionQualityIndicator({
  connectionStatus = 'unknown',
  latencyMs = null,
  reconnectAttempt = 0,
  maxReconnectAttempts = 5,
  isReconnecting = false,
  className = '',
}) {
  const getQualityFromLatency = (ms) => {
    if (!ms || ms < 0) return { level: 'unknown', color: '#94a3b8' };
    if (ms < 150) return { level: 'excellent', color: '#22d3ee', bars: 4 };
    if (ms < 300) return { level: 'good', color: '#34d399', bars: 3 };
    if (ms < 600) return { level: 'fair', color: '#fbbf24', bars: 2 };
    return { level: 'poor', color: '#f87171', bars: 1 };
  };

  const quality = getQualityFromLatency(latencyMs);

  const renderStatusIcon = () => {
    switch (connectionStatus) {
      case 'online':
        return <CheckCircle2 size={14} color="#22d3ee" />;
      case 'offline':
        return <WifiOff size={14} color="#f87171" />;
      case 'error':
        return <AlertTriangle size={14} color="#fbbf24" />;
      default:
        return <Activity size={14} color="#94a3b8" />;
    }
  };

  const renderLatencyBars = () => {
    if (connectionStatus !== 'online') {
      return (
        <div className="latency-bars offline">
          {[1, 2, 3, 4].map((i) => (
            <span key={i} className="bar inactive" />
          ))}
        </div>
      );
    }

    return (
      <div className={`latency-bars ${quality.level}`}>
        {[1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className={`bar ${i <= quality.bars ? 'active' : ''}`}
          />
        ))}
      </div>
    );
  };

  const getStatusText = () => {
    if (isReconnecting) {
      return `Reconnecting... (${reconnectAttempt}/${maxReconnectAttempts})`;
    }
    if (connectionStatus === 'offline') return 'Offline';
    if (connectionStatus === 'error') return 'Connection Error';
    if (latencyMs) return `${latencyMs}ms`;
    return 'Connected';
  };

  return (
    <div
      className={`connection-quality-indicator ${connectionStatus} ${className}`}
      role="status"
      aria-live="polite"
      aria-label={`Connection status: ${getStatusText()}`}
    >
      <div className="indicator-main">
        {renderStatusIcon()}
        {renderLatencyBars()}
        <span className="status-text">{getStatusText()}</span>
      </div>
      
      {isReconnecting && (
        <div className="reconnect-progress">
          <div 
            className="progress-bar"
            style={{
              width: `${(reconnectAttempt / maxReconnectAttempts) * 100}%`,
            }}
          />
        </div>
      )}
    </div>
  );
}
