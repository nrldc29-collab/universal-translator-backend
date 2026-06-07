/**
 * EnhancedMicButton -- Advanced microphone button with pulse animation,
 * waveform visualization, and clear state indicators
 */

import React, { useState, useEffect } from 'react';
import { Mic, MicOff, Volume2, Loader2 } from 'lucide-react';
import WaveformVisualizer from './WaveformVisualizer';

export default function EnhancedMicButton({
  state = 'idle', // 'idle' | 'listening' | 'speaking' | 'processing' | 'error'
  micLevel = 0,
  onClick,
  onPointerDown,
  onPointerUp,
  disabled = false,
  size = 'large',
  className = '',
  showWaveform = true,
  pulseAnimation = true,
  preventDoubleTap = true,
  lastTapRef,
}) {
  const [isPressed, setIsPressed] = useState(false);
  const [rippleActive, setRippleActive] = useState(false);

  // Prevent double-tap issues
  const handleInteraction = (e, handler) => {
    if (preventDoubleTap && lastTapRef) {
      const now = Date.now();
      const lastTap = lastTapRef.current || 0;
      if (now - lastTap < 300) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      lastTapRef.current = now;
    }
    handler?.(e);
  };

  const handleClick = (e) => handleInteraction(e, onClick);
  const handlePointerDown = (e) => {
    setIsPressed(true);
    setRippleActive(true);
    setTimeout(() => setRippleActive(false), 600);
    handleInteraction(e, onPointerDown);
  };
  const handlePointerUp = (e) => {
    setIsPressed(false);
    handleInteraction(e, onPointerUp);
  };

  const stateConfig = {
    idle: {
      icon: Mic,
      color: '#22d3ee',
      bgColor: 'rgba(34, 211, 238, 0.15)',
      borderColor: 'rgba(34, 211, 238, 0.3)',
      label: 'Tap to speak',
      pulse: false,
      rotate: false,
    },
    listening: {
      icon: Mic,
      color: '#ef4444',
      bgColor: 'rgba(239, 68, 68, 0.2)',
      borderColor: 'rgba(239, 68, 68, 0.5)',
      label: 'Listening...',
      pulse: true,
      rotate: false,
    },
    speaking: {
      icon: Volume2,
      color: '#34d399',
      bgColor: 'rgba(52, 211, 153, 0.2)',
      borderColor: 'rgba(52, 211, 153, 0.5)',
      label: 'Speaking...',
      pulse: false,
      rotate: true,
    },
    processing: {
      icon: Loader2,
      color: '#a78bfa',
      bgColor: 'rgba(167, 139, 250, 0.2)',
      borderColor: 'rgba(167, 139, 250, 0.5)',
      label: 'Processing...',
      pulse: false,
      rotate: true,
    },
    error: {
      icon: MicOff,
      color: '#f87171',
      bgColor: 'rgba(248, 113, 113, 0.2)',
      borderColor: 'rgba(248, 113, 113, 0.5)',
      label: 'Error - Tap to retry',
      pulse: false,
      rotate: false,
    },
  };

  const config = stateConfig[state] || stateConfig.idle;
  const Icon = config.icon;

  const sizeClasses = {
    small: { button: 56, icon: 24, waveform: 80 },
    medium: { button: 72, icon: 32, waveform: 100 },
    large: { button: 96, icon: 44, waveform: 120 },
  };

  const sizes = sizeClasses[size] || sizeClasses.large;

  return (
    <div className={`enhanced-mic-container ${className}`}>
      {/* Waveform visualization */}
      {showWaveform && (state === 'listening' || state === 'speaking') && (
        <div 
          className="mic-waveform-ring"
          style={{
            width: sizes.waveform,
            height: sizes.waveform,
          }}
        >
          <WaveformVisualizer
            micLevel={micLevel}
            isListening={state === 'listening'}
            isSpeaking={state === 'speaking'}
            barCount={24}
          />
        </div>
      )}

      {/* Pulse rings */}
      {pulseAnimation && config.pulse && (
        <>
          <span className="pulse-ring ring-1" />
          <span className="pulse-ring ring-2" />
          <span className="pulse-ring ring-3" />
        </>
      )}

      {/* Main button */}
      <button
        className={`enhanced-mic-button ${state} ${isPressed ? 'pressed' : ''} ${rippleActive ? 'ripple' : ''}`}
        data-state={state}
        style={{
          width: sizes.button,
          height: sizes.button,
          '--voice-level': micLevel,
        }}
        onClick={handleClick}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onContextMenu={(e) => e.preventDefault()}
        disabled={disabled}
        aria-label={config.label}
        aria-pressed={isPressed}
      >
        {/* Energy rim that responds to voice */}
        <span
          className="energy-rim"
          style={{ '--voice-level': micLevel }}
        />

        {/* Icon */}
        <Icon
          size={sizes.icon}
          strokeWidth={2.2}
          className={config.rotate ? 'spin-slow' : ''}
        />

        {/* Voice level indicator ring */}
        {state === 'listening' && (
          <svg className="voice-level-ring" viewBox="0 0 100 100">
            <circle
              className="track"
              cx="50"
              cy="50"
              r="46"
              fill="none"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="2"
            />
            <circle
              className="progress"
              cx="50"
              cy="50"
              r="46"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${micLevel * 289} 289`}
              transform="rotate(-90 50 50)"
              style={{
                transition: 'stroke-dasharray 0.1s ease-out',
                filter: `drop-shadow(0 0 4px ${config.color})`,
              }}
            />
          </svg>
        )}
      </button>

      {/* State label */}
      <span
        className={`mic-state-label state-${state}`}
        aria-hidden="true"
      >
        {config.label}
      </span>
    </div>
  );
}
