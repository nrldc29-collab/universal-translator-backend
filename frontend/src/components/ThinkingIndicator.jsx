/**
 * ThinkingIndicator -- Animated "thinking" state while translation is being processed
 * Shows a pulsing animation with progressive dots and optional progress text
 */

import React from 'react';
import { Brain, Sparkles, Zap } from 'lucide-react';

export default function ThinkingIndicator({
  stage = 'thinking',
  progress = null,
  message = '',
  className = '',
}) {
  const stageConfig = {
    thinking: {
      icon: Brain,
      color: '#22d3ee',
      label: 'Thinking',
      animation: 'pulse',
    },
    translating: {
      icon: Sparkles,
      color: '#a78bfa',
      label: 'Translating',
      animation: 'shimmer',
    },
    processing: {
      icon: Zap,
      color: '#fbbf24',
      label: 'Processing',
      animation: 'pulse',
    },
  };

  const config = stageConfig[stage] || stageConfig.thinking;
  const Icon = config.icon;

  return (
    <div
      className={`thinking-indicator ${config.animation} ${className}`}
      role="status"
      aria-live="polite"
      aria-label={`${config.label}... ${message || ''}`}
    >
      <div className="thinking-orb" style={{ '--orb-color': config.color }}>
        <Icon size={24} color={config.color} strokeWidth={2} />
        <span className="thinking-pulse" />
        <span className="thinking-pulse delayed" />
      </div>
      
      <div className="thinking-text">
        <span className="thinking-label">{config.label}</span>
        <span className="thinking-dots">
          <span className="dot" style={{ animationDelay: '0ms' }}>.</span>
          <span className="dot" style={{ animationDelay: '200ms' }}>.</span>
          <span className="dot" style={{ animationDelay: '400ms' }}>.</span>
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

      <div className="thinking-waves" aria-hidden="true" style={{ '--wave-color': config.color }}>
        {[...Array(5)].map((_, i) => (
          <span
            key={i}
            className="wave-bar"
            style={{ animationDelay: `${i * 100}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
