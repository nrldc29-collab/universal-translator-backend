/**
 * LoadingSpinner -- Beautiful, accessible loading indicators
 * 
 * Features:
 * - Multiple sizes (small, medium, large)
 * - Color variants (primary, white, accent)
 * - ARIA live regions for screen readers
 * - Smooth animations
 */

import React from 'react';

export default function LoadingSpinner({ 
  size = 'medium', 
  color = 'primary',
  label = 'Loading...',
  fullScreen = false,
}) {
  const sizeStyles = {
    small: { width: 20, height: 20, borderWidth: 2 },
    medium: { width: 32, height: 32, borderWidth: 3 },
    large: { width: 48, height: 48, borderWidth: 4 },
  };

  const colorStyles = {
    primary: '#3b82f6',
    white: '#ffffff',
    accent: '#22d3ee',
  };

  const currentSize = sizeStyles[size] || sizeStyles.medium;
  const currentColor = colorStyles[color] || colorStyles.primary;

  const spinner = (
    <div 
      className="loading-spinner"
      style={{
        width: currentSize.width,
        height: currentSize.height,
        borderWidth: currentSize.borderWidth,
        borderColor: `${currentColor}33`,
        borderTopColor: currentColor,
      }}
      role="status"
      aria-label={label}
    >
      <span className="sr-only">{label}</span>
    </div>
  );

  if (fullScreen) {
    return (
      <div className="loading-spinner-fullscreen" role="dialog" aria-modal="true" aria-label={label}>
        <div className="loading-spinner-content">
          {spinner}
          <p className="loading-spinner-text">{label}</p>
        </div>
      </div>
    );
  }

  return spinner;
}

// Compact inline spinner for buttons
export function InlineSpinner({ size = 'small' }) {
  return (
    <LoadingSpinner size={size} color="white" label="" />
  );
}
