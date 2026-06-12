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
    message: 'Please allow microphone access in your browser settings to open the conversation bridge.',
    action: 'Allow mic',
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
    title: 'Bridge Offline',
    message: 'Check your network and bridge server, then try linking again.',
    action: 'Retry',
  },
  'network_timeout': {
    icon: Wifi,
    severity: 'warning',
    title: 'Bridge Link Slow',
    message: 'Linking the bridge is taking longer than expected. Please wait or try again.',
    action: 'Retry',
  },
  'quota_exceeded': {
    icon: AlertTriangle,
    severity: 'warning',
    title: 'Rate Limit Reached',
    message: 'Too many requests in a short time. Wait about a minute, then try again.',
    action: 'Retry',
  },
  'websocket_disconnected': {
    icon: Wifi,
    severity: 'warning',
    title: 'Bridge Dropped',
    message: 'We lost the bridge link. Relinking automatically…',
    action: 'Relink',
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
    title: 'Bridge Failed',
    message: 'Something went wrong bridging meaning. Please try again.',
    action: 'Retry',
  },
  'translation_timeout': {
    icon: AlertTriangle,
    severity: 'warning',
    title: 'Bridge Taking Long',
    message: 'Understanding is taking longer than usual. Please wait…',
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
          type="button"
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
          type="button"
          className="error-action"
          onClick={handleAction}
        >
          {errorConfig.action === 'Retry' || errorConfig.action === 'Relink' ? (
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
  if (message.includes('quota') || message.includes('rate limit')) {
    return 'quota_exceeded';
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
