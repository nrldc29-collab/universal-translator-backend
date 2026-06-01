/**
 * KeyboardHelp -- Modal displaying keyboard shortcuts
 * 
 * Features:
 * - Shows all available keyboard shortcuts
 * - Keyboard accessible (Escape to close)
 * - Clean, organized layout
 */

import React from 'react';
import { X, Keyboard } from 'lucide-react';

const SHORTCUTS = [
  { key: 'Space', label: 'Toggle microphone' },
  { key: 'M', label: 'Mute/unmute' },
  { key: 'C', label: 'Clear conversation' },
  { key: '1', label: 'Spanish' },
  { key: '2', label: 'French' },
  { key: '3', label: 'German' },
  { key: '4', label: 'Japanese' },
  { key: '?', label: 'Show this help' },
  { key: 'Escape', label: 'Close modals' },
];

export default function KeyboardHelp({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="keyboard-help-overlay" role="dialog" aria-modal="true" aria-labelledby="keyboard-help-title">
      <div className="keyboard-help-card">
        <div className="keyboard-help-header">
          <div className="keyboard-help-title-row">
            <Keyboard size={20} strokeWidth={2} />
            <h2 id="keyboard-help-title">Keyboard Shortcuts</h2>
          </div>
          <button
            className="keyboard-help-close"
            onClick={onClose}
            aria-label="Close keyboard shortcuts"
            type="button"
          >
            <X size={18} strokeWidth={2} />
          </button>
        </div>

        <div className="keyboard-help-content">
          <div className="keyboard-shortcuts-grid">
            {SHORTCUTS.map((shortcut) => (
              <div key={shortcut.key} className="keyboard-shortcut-item">
                <kbd className="keyboard-key">{shortcut.key}</kbd>
                <span className="keyboard-label">{shortcut.label}</span>
              </div>
            ))}
          </div>

          <p className="keyboard-help-note">
            Press <kbd>?</kbd> anytime to show this help
          </p>
        </div>
      </div>

    </div>
  );
}
