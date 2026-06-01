/**
 * UserFriendlyError -- Converts technical errors into actionable, friendly messages
 * 
 * Features:
 * - Maps technical error codes to user-friendly explanations
 * - Provides actionable next steps
 * - Visual severity indicators (info, warning, error)
 * - Dismissible with option to not show again
 */

import React, { useState } from 'react';
import { AlertCircle, RefreshCw, X, Wifi, Mic, Volume2, AlertTriangle } from 'lucide-react';

const ERROR_MAPPINGS = {
  // Microphone errors
  'mic_permission_denied': {
    icon: Mic,
    severity: 'error',
    title: 'Microphone Access Needed',
    message: 'Please allow microphone access in your browser settings to use voice translation.',
    action: 'Open Settings',
    actionHandler: () => {
      // Try to open browser settings (not always possible, but worth attempting)
      if (navigator.permissions) {
        navigator.permissions.query({ name: 'microphone' }).then((result) => {
          if (result.state === 'denied') {
            alert('Please enable microphone access in your browser settings and refresh the page.');
          }
        });
      }
    },
  },
  'mic_not_found': {
    icon: Mic,
    severity: 'error',
    title: 'No Microphone Found',
    message: 'We couldn\'t find a microphone. Please connect one and try again.',
    action: 'Retry',
  },
  'mic_blocked': {
    icon: Mic,
    severity: 'error',
    title: 'Microphone Blocked',
    message: 'Your microphone is blocked by another application. Close other apps using the mic and try again.',
    action: 'Retry',
  },

  // Network errors
  'network_offline': {
    icon: Wifi,
    severity: 'error',
    title: 'No Internet Connection',
    message: 'Please check your internet connection and try again.',
    action: 'Retry',
  },
  'network_timeout': {
    icon: Wifi,
    severity: 'warning',
    title: 'Connection Slow',
    message: 'The connection is taking longer than expected. Please wait or try again.',
    action: 'Retry',
  },
  'websocket_disconnected': {
    icon: Wifi,
    severity: 'warning',
    title: 'Connection Lost',
    message: 'We lost connection to the server. Reconnecting automatically...',
    action: 'Reconnect',
  },

  // Audio errors
  'audio_context_failed': {
    icon: Volume2,
    severity: 'error',
    title: 'Audio Not Available',
    message: 'Your browser doesn\'t support audio playback. Please try a different browser.',
    action: 'Learn More',
    actionHandler: () => {
      window.open('https://caniuse.com/web-audio', '_blank');
    },
  },
  'speaker_blocked': {
    icon: Volume2,
    severity: 'warning',
    title: 'Audio Blocked',
    message: 'Check your device volume and ensure audio is not muted.',
    action: 'Test Audio',
  },

  // Translation errors
  'translation_failed': {
    icon: AlertTriangle,
    severity: 'error',
    title: 'Translation Failed',
    message: 'Something went wrong with the translation. Please try again.',
    action: 'Retry',
  },
  'translation_timeout': {
    icon: AlertTriangle,
    severity: 'warning',
    title: 'Translation Taking Long',
    message: 'The translation is taking longer than usual. Please wait...',
    action: 'Wait',
  },

  // Generic errors
  'unknown_error': {
    icon: AlertCircle,
    severity: 'error',
    title: 'Something Went Wrong',
    message: 'An unexpected error occurred. Please try again.',
    action: 'Retry',
  },
};

export default function UserFriendlyError({ errorCode, onDismiss, onRetry }) {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const errorConfig = ERROR_MAPPINGS[errorCode] || ERROR_MAPPINGS['unknown_error'];
  const ErrorIcon = errorConfig.icon;

  const handleAction = () => {
    if (errorConfig.actionHandler) {
      errorConfig.actionHandler();
    } else if (onRetry) {
      onRetry();
    }
  };

  const handleDismiss = () => {
    if (dontShowAgain) {
      localStorage.setItem(`anai_error_dismissed_${errorCode}`, 'true');
    }
    onDismiss?.();
  };

  const severityColors = {
    info: { bg: '#3b82f6', border: '#1d4ed8', text: '#eff6ff' },
    warning: { bg: '#f59e0b', border: '#d97706', text: '#fffbeb' },
    error: { bg: '#ef4444', border: '#dc2626', text: '#fef2f2' },
  };

  const colors = severityColors[errorConfig.severity];

  return (
    <div className="user-friendly-error" data-severity={errorConfig.severity} role="alert" aria-live="assertive">
      <div className="error-content">
        <div className="error-icon">
          <ErrorIcon size={22} strokeWidth={2} />
        </div>

        <div className="error-message">
          <h3 className="error-title">{errorConfig.title}</h3>
          <p className="error-description">{errorConfig.message}</p>
        </div>

        <button
          className="error-dismiss"
          onClick={handleDismiss}
          aria-label="Dismiss"
        >
          <X size={18} strokeWidth={2} />
        </button>
      </div>

      <div className="error-actions">
        <label className="dont-show-checkbox">
          <input
            type="checkbox"
            checked={dontShowAgain}
            onChange={(e) => setDontShowAgain(e.target.checked)}
          />
          <span>Don't show again</span>
        </label>

        <button
          className="error-action"
          onClick={handleAction}
        >
          {errorConfig.action === 'Retry' || errorConfig.action === 'Reconnect' ? (
            <RefreshCw size={16} strokeWidth={2.5} />
          ) : null}
          {errorConfig.action}
        </button>
      </div>

    </div>
  );
}

// Helper function to get user-friendly error config
export function getErrorConfig(errorCode) {
  return ERROR_MAPPINGS[errorCode] || ERROR_MAPPINGS['unknown_error'];
}

// Helper to map technical errors to user-friendly codes
export function mapTechnicalError(error) {
  const message = error?.message?.toLowerCase() || '';
  const name = error?.name?.toLowerCase() || '';

  if (message.includes('permission') || message.includes('denied') || name.includes('permission')) {
    return 'mic_permission_denied';
  }
  if (message.includes('not found') || message.includes('no device')) {
    return 'mic_not_found';
  }
  if (message.includes('blocked') || message.includes('in use')) {
    return 'mic_blocked';
  }
  if (message.includes('network') || message.includes('offline') || name.includes('network')) {
    return 'network_offline';
  }
  if (message.includes('timeout') || name.includes('timeout')) {
    return 'network_timeout';
  }
  if (message.includes('websocket') || message.includes('connection')) {
    return 'websocket_disconnected';
  }
  if (message.includes('audio context') || message.includes('audiocontext')) {
    return 'audio_context_failed';
  }
  if (message.includes('speaker') || message.includes('volume') || message.includes('mute')) {
    return 'speaker_blocked';
  }
  if (message.includes('translation')) {
    return 'translation_failed';
  }

  return 'unknown_error';
}
