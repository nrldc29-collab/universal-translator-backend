/**
 * KeyboardHelp -- Modal displaying keyboard shortcuts
 */

import React from 'react';
import { X, Keyboard } from 'lucide-react';

const SHORTCUT_GROUPS = [
  {
    title: 'Voice',
    items: [
      { key: 'Space', label: 'Toggle microphone' },
      { key: 'M', label: 'Mute / unmute' },
    ],
  },
  {
    title: 'Conversation',
    items: [
      { key: 'C', label: 'Clear conversation' },
    ],
  },
  {
    title: 'Languages',
    items: [
      { key: '1', label: 'Spanish' },
      { key: '2', label: 'French' },
      { key: '3', label: 'German' },
      { key: '4', label: 'Japanese' },
    ],
  },
  {
    title: 'General',
    items: [
      { key: '?', label: 'Show this help' },
      { key: 'Escape', label: 'Close modals' },
    ],
  },
];

export default function KeyboardHelp({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div
      className="keyboard-help-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="keyboard-help-title"
      onClick={onClose}
    >
      <div className="keyboard-help-card" onClick={(e) => e.stopPropagation()}>
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
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title} className="keyboard-help-section">
              <div className="keyboard-help-section-label">{group.title}</div>
              <div className="keyboard-shortcuts-grid">
                {group.items.map((shortcut) => (
                  <div key={shortcut.key} className="keyboard-shortcut-item">
                    <kbd className="keyboard-key">{shortcut.key}</kbd>
                    <span className="keyboard-label">{shortcut.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <p className="keyboard-help-note">
            Press <kbd>?</kbd> anytime to show this help
          </p>
        </div>
      </div>
    </div>
  );
}
