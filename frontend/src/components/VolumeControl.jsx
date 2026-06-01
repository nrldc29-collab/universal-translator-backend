/**
 * VolumeControl -- Audio volume control with visual feedback
 * 
 * Features:
 * - Volume slider with visual feedback
 * - Mute/unmute toggle
 * - Volume level indicator
 * - Keyboard accessible
 */

import React, { useState, useEffect, useRef } from 'react';
import { Volume2, VolumeX, Volume1 } from 'lucide-react';

export default function VolumeControl({ 
  initialVolume = 0.8, 
  onVolumeChange,
  className = '',
}) {
  const [volume, setVolume] = useState(initialVolume);
  const [isMuted, setIsMuted] = useState(false);
  const [showVolume, setShowVolume] = useState(false);
  const sliderRef = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    setVolume(initialVolume);
  }, [initialVolume]);

  const handleVolumeChange = (newVolume) => {
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
    onVolumeChange?.(newVolume);
    
    // Show volume indicator
    setShowVolume(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setShowVolume(false);
    }, 1500);
  };

  const toggleMute = () => {
    if (isMuted) {
      handleVolumeChange(0.8);
    } else {
      handleVolumeChange(0);
    }
  };

  const getVolumeIcon = () => {
    if (isMuted || volume === 0) return VolumeX;
    if (volume < 0.5) return Volume1;
    return Volume2;
  };

  const VolumeIcon = getVolumeIcon();

  const pct = isMuted ? 0 : volume;

  return (
    <div className={`volume-control ${className}`}>
      <button
        className={`volume-toggle${isMuted ? ' muted' : ''}`}
        onClick={toggleMute}
        aria-label={isMuted ? 'Unmute' : 'Mute'}
        aria-pressed={isMuted}
        type="button"
      >
        <VolumeIcon size={16} strokeWidth={2} />
      </button>

      <div className="volume-track" style={{ '--pct': pct }}>
        <input
          ref={sliderRef}
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={pct}
          onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
          className="volume-slider"
          aria-label="Volume"
        />
      </div>

      {showVolume && (
        <div className="volume-indicator" role="status" aria-live="polite">
          {Math.round(pct * 100)}%
        </div>
      )}
    </div>
  );
}
