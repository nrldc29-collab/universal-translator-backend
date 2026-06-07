/**
 * ConversationActions -- Quick actions for conversation management
 * Includes clear history, copy to clipboard, and export features
 */

import React, { useState, useCallback } from 'react';
import { Trash2, Copy, Download, Check, X, Share2, AlertTriangle } from 'lucide-react';

export default function ConversationActions({
  conversationTurns = [],
  onClear,
  onCopy,
  disabled = false,
  className = '',
}) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [copied, setCopied] = useState(false);

  // Format conversation for clipboard
  const formatConversation = useCallback(() => {
    if (!conversationTurns.length) return '';
    
    const lines = conversationTurns.map(turn => {
      const timestamp = new Date(turn.timestamp || Date.now()).toLocaleTimeString();
      return `[${timestamp}] ${turn.speaker_label || 'Speaker'}:\n  ${turn.source_text}\n  → ${turn.translated_text}`;
    });
    
    return lines.join('\n\n');
  }, [conversationTurns]);

  // Handle copy to clipboard
  const handleCopy = async () => {
    const text = formatConversation();
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      onCopy?.(text);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Handle export as text file
  const handleExport = () => {
    const text = formatConversation();
    if (!text) return;

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Handle share (if Web Share API available)
  const handleShare = async () => {
    const text = formatConversation();
    if (!text) return;

    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Conversation Translation',
          text: text,
        });
      } catch (err) {
        // User cancelled or share failed
      }
    } else {
      // Fallback to copy
      handleCopy();
    }
  };

  // Handle clear with confirmation
  const handleClear = () => {
    if (!showConfirm) {
      setShowConfirm(true);
      return;
    }
    onClear?.();
    setShowConfirm(false);
  };

  const hasConversation = conversationTurns.length > 0;
  const canShare = typeof navigator !== 'undefined' && !!navigator.share;

  return (
    <div className={`conversation-actions ${className}`}>
      {showConfirm ? (
        <div className="conv-confirm" role="alertdialog" aria-label="Confirm clear">
          <AlertTriangle size={13} strokeWidth={2.5} className="conv-confirm-icon" aria-hidden="true" />
          <span className="conv-confirm-text">Clear all history?</span>
          <button
            className="conv-confirm-yes"
            onClick={handleClear}
            disabled={disabled}
            aria-label="Confirm clear history"
          >
            <Check size={12} strokeWidth={2.8} /> Yes
          </button>
          <button
            className="conv-confirm-no"
            onClick={() => setShowConfirm(false)}
            aria-label="Cancel"
          >
            <X size={12} strokeWidth={2.5} /> No
          </button>
        </div>
      ) : (
        <div className="conv-action-strip">
          <button
            className={`conv-btn${copied ? ' success' : ''}`}
            onClick={handleCopy}
            disabled={disabled || !hasConversation}
            aria-label={copied ? 'Copied' : 'Copy conversation'}
          >
            {copied ? <Check size={14} strokeWidth={2.8} /> : <Copy size={14} strokeWidth={2.2} />}
            <span className="conv-btn-label">{copied ? 'Copied' : 'Copy'}</span>
          </button>

          <button
            className="conv-btn"
            onClick={handleExport}
            disabled={disabled || !hasConversation}
            aria-label="Export as text file"
          >
            <Download size={14} strokeWidth={2.2} />
            <span className="conv-btn-label">Export</span>
          </button>

          {canShare && (
            <button
              className="conv-btn"
              onClick={handleShare}
              disabled={disabled || !hasConversation}
              aria-label="Share conversation"
            >
              <Share2 size={14} strokeWidth={2.2} />
              <span className="conv-btn-label">Share</span>
            </button>
          )}

          <button
            className="conv-btn danger"
            onClick={handleClear}
            disabled={disabled || !hasConversation}
            aria-label="Clear conversation history"
          >
            <Trash2 size={14} strokeWidth={2.2} />
            <span className="conv-btn-label">Clear</span>
          </button>
        </div>
      )}
    </div>
  );
}
