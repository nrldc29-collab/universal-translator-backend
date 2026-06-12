/**
 * ThinkingIndicator -- Animated "thinking" state while translation is being processed
 * Shows a pulsing animation with progressive dots and optional progress text
 */

import React from 'react';
import { Heart, Languages } from 'lucide-react';

export default function ThinkingIndicator({
  stage = 'thinking',
  progress = null,
  message = '',
  className = '',
}) {
  const stageConfig = {
    thinking: {
      icon: Heart,
      label: 'Understanding',
      animation: 'pulse',
    },
    translating: {
      icon: Heart,
      label: 'Understanding',
      animation: 'shimmer',
    },
    processing: {
      icon: Languages,
      label: 'Bridging',
      animation: 'pulse',
    },
  };

  const config = stageConfig[stage] || stageConfig.thinking;
  const Icon = config.icon;

  return (
    <div
      className={`thinking-indicator ${config.animation} ${className}`}
      data-stage={stage}
      role="status"
      aria-live="polite"
      aria-label={`${config.label}... ${message || ''}`}
    >
      <div className="thinking-orb">
        <Icon size={24} strokeWidth={2} className="thinking-stage-icon" aria-hidden="true" />
        <span className="thinking-pulse" />
        <span className="thinking-pulse delayed" />
      </div>
      
      <div className="thinking-text">
        <span className="thinking-label">{config.label}</span>
        <span className="thinking-dots" aria-hidden="true">
          <span className="dot">.</span>
          <span className="dot">.</span>
          <span className="dot">.</span>
        </span>
      </div>

      {message && (
        <span className="thinking-message">{message}</span>
      )}

      {progress !== null && (
        <div className="thinking-progress">
          <div 
            className="progress-fill"
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}

      <div className="thinking-waves" aria-hidden="true">
        {[...Array(5)].map((_, i) => (
          <span key={i} className="wave-bar" />
        ))}
      </div>
    </div>
  );
}
