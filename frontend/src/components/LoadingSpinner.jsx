/**
 * LoadingSpinner -- Accessible loading indicators
 */

import React from 'react';

export default function LoadingSpinner({
  size = 'medium',
  color = 'primary',
  label = 'Loading...',
  fullScreen = false,
}) {
  const spinner = (
    <div
      className={`loading-spinner loading-spinner--${size} loading-spinner--${color}`}
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

export function InlineSpinner({ size = 'small' }) {
  return (
    <LoadingSpinner size={size} color="white" label="" />
  );
}
