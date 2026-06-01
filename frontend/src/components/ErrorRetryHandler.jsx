/**
 * ErrorRetryHandler -- Displays network/connection errors with automatic retry logic
 * Shows retry countdown, attempts count, and manual retry option
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AlertTriangle, RefreshCw, WifiOff, ServerCrash } from 'lucide-react';

export default function ErrorRetryHandler({
  error,
  errorCode,
  onRetry,
  onDismiss,
  maxRetries = 3,
  baseDelay = 2000,
  className = '',
  showDismiss = true,
}) {
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [lastError, setLastError] = useState(null);
  const retryTimeoutRef = useRef(null);
  const countdownIntervalRef = useRef(null);

  // Calculate exponential backoff delay
  const getRetryDelay = useCallback((attempt) => {
    return Math.min(baseDelay * Math.pow(2, attempt), 30000); // Max 30 seconds
  }, [baseDelay]);

  // Stop all retry operations
  const stopRetry = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    setIsRetrying(false);
    setCountdown(0);
  }, []);

  // Execute retry
  const executeRetry = useCallback(async () => {
    stopRetry();
    setIsRetrying(true);
    setRetryCount(prev => prev + 1);

    try {
      await onRetry?.();
      // Success - reset state
      setRetryCount(0);
      setLastError(null);
    } catch (err) {
      setLastError(err);
      
      // Schedule next retry if under max
      if (retryCount < maxRetries - 1) {
        const delay = getRetryDelay(retryCount + 1);
        setCountdown(Math.ceil(delay / 1000));
        
        countdownIntervalRef.current = setInterval(() => {
          setCountdown(prev => {
            if (prev <= 1) {
              clearInterval(countdownIntervalRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        retryTimeoutRef.current = setTimeout(() => {
          executeRetry();
        }, delay);
      } else {
        setIsRetrying(false);
      }
    }
  }, [onRetry, retryCount, maxRetries, getRetryDelay, stopRetry]);

  // Start auto-retry when error appears
  useEffect(() => {
    if (error || errorCode) {
      setLastError(error || { code: errorCode });
      if (retryCount === 0 && !isRetrying) {
        executeRetry();
      }
    }
    
    return () => stopRetry();
  }, [error, errorCode, executeRetry, retryCount, isRetrying, stopRetry]);

  // Manual retry handler
  const handleManualRetry = () => {
    setRetryCount(0);
    executeRetry();
  };

  const getErrorIcon = () => {
    if (errorCode?.includes('network') || errorCode?.includes('connection')) {
      return <WifiOff size={24} color="#f87171" />;
    }
    if (errorCode?.includes('server') || errorCode?.includes('500')) {
      return <ServerCrash size={24} color="#f87171" />;
    }
    return <AlertTriangle size={24} color="#fbbf24" />;
  };

  const getErrorMessage = () => {
    if (errorCode === 'network_error') return 'Network connection lost. Retrying...';
    if (errorCode === 'server_error') return 'Server temporarily unavailable. Retrying...';
    if (errorCode === 'timeout') return 'Request timed out. Retrying...';
    if (errorCode === 'tts_failed') return 'Voice playback failed. Retrying...';
    return error?.message || 'Something went wrong. Retrying...';
  };

  // If no error, don't render
  if (!error && !errorCode && !lastError) return null;

  const canRetry = retryCount < maxRetries;
  const isExhausted = retryCount >= maxRetries && !isRetrying;

  return (
    <div 
      className={`error-retry-handler ${isExhausted ? 'exhausted' : ''} ${className}`}
      role="alert"
      aria-live="polite"
    >
      <div className="error-content">
        <div className="error-icon">
          {getErrorIcon()}
        </div>
        
        <div className="error-text">
          <p className="error-message">{getErrorMessage()}</p>
          
          {isRetrying && countdown > 0 && (
            <p className="retry-countdown">
              Retrying in {countdown}s...
            </p>
          )}
          
          {isRetrying && countdown === 0 && (
            <p className="retry-status">
              <RefreshCw size={14} className="spin" />
              Attempt {retryCount} of {maxRetries}...
            </p>
          )}
          
          {isExhausted && (
            <p className="retry-exhausted">
              Unable to reconnect after {maxRetries} attempts.
            </p>
          )}
        </div>
      </div>

      <div className="error-actions">
        {(isExhausted || !isRetrying) && (
          <button
            className="retry-button"
            onClick={handleManualRetry}
            disabled={isRetrying}
          >
            <RefreshCw size={16} />
            {isExhausted ? 'Try Again' : 'Retry Now'}
          </button>
        )}
        
        {showDismiss && (
          <button
            className="dismiss-button"
            onClick={() => {
              stopRetry();
              onDismiss?.();
            }}
          >
            Dismiss
          </button>
        )}
      </div>

      {/* Progress bar for countdown */}
      {isRetrying && countdown > 0 && (
        <div className="retry-progress">
          <div 
            className="progress-fill"
            style={{
              animation: `shrink ${countdown}s linear forwards`,
            }}
          />
        </div>
      )}
    </div>
  );
}
