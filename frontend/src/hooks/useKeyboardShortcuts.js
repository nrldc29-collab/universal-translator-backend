/**
 * useKeyboardShortcuts -- Keyboard shortcuts for common actions
 * 
 * Features:
 * - Space: Toggle microphone
 * - M: Mute/unmute
 * - C: Clear conversation
 * - 1-4: Switch target language
 * - ?: Show keyboard shortcuts help
 * - Escape: Close modals/tooltips
 */

import { useCallback, useEffect } from 'react';

const SHORTCUTS = [
  { key: ' ', action: 'toggleMic', label: 'Toggle microphone' },
  { key: 'm', action: 'toggleMute', label: 'Mute/unmute' },
  { key: 'c', action: 'clearConversation', label: 'Clear conversation' },
  { key: '1', action: 'setLanguage1', label: 'Set target language to Spanish' },
  { key: '2', action: 'setLanguage2', label: 'Set target language to French' },
  { key: '3', action: 'setLanguage3', label: 'Set target language to German' },
  { key: '4', action: 'setLanguage4', label: 'Set target language to Japanese' },
  { key: '?', action: 'showHelp', label: 'Show keyboard shortcuts' },
  { key: 'Escape', action: 'closeModals', label: 'Close modals/tooltips' },
];

export default function useKeyboardShortcuts({
  onToggleMic,
  onToggleMute,
  onClearConversation,
  onSetLanguage,
  onShowHelp,
  onCloseModals,
  disabled = false,
}) {
  const handleKeyDown = useCallback((event) => {
    if (disabled) return;

    // Ignore if typing in an input field
    if (
      event.target.tagName === 'INPUT' ||
      event.target.tagName === 'TEXTAREA' ||
      event.target.isContentEditable
    ) {
      return;
    }

    const key = event.key;

    switch (key) {
      case ' ':
        event.preventDefault();
        onToggleMic?.();
        break;
      case 'm':
      case 'M':
        event.preventDefault();
        onToggleMute?.();
        break;
      case 'c':
      case 'C':
        event.preventDefault();
        onClearConversation?.();
        break;
      case '1':
        event.preventDefault();
        onSetLanguage?.('es');
        break;
      case '2':
        event.preventDefault();
        onSetLanguage?.('fr');
        break;
      case '3':
        event.preventDefault();
        onSetLanguage?.('de');
        break;
      case '4':
        event.preventDefault();
        onSetLanguage?.('ja');
        break;
      case '?':
        event.preventDefault();
        onShowHelp?.();
        break;
      case 'Escape':
        event.preventDefault();
        onCloseModals?.();
        break;
    }
  }, [disabled, onToggleMic, onToggleMute, onClearConversation, onSetLanguage, onShowHelp, onCloseModals]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return { shortcuts: SHORTCUTS };
}
