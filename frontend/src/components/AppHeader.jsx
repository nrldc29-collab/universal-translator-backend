/**
 * AppHeader — branded title row + share/install buttons + live
 * connection indicator. Extracted from `main.jsx` for readability.
 */

import React from 'react';
import { Download, Share2 } from 'lucide-react';

export default function AppHeader({
  connectionStatus,
  shareConversationRoom,
  copiedKey,
  showInstallAction,
  installApp,
}) {
  return (
    <header className="clean-header">
      <div className="header-actions">
        <button
          className="icon-action"
          type="button"
          onClick={shareConversationRoom}
          aria-label="Share speaker room"
          title="Share speaker room"
        >
          <Share2 size={17} strokeWidth={2.4} aria-hidden="true" />
          <span className="sr-only">
            {copiedKey === 'room' ? 'Room link copied' : 'Share speaker room'}
          </span>
        </button>
        {showInstallAction && (
          <button
            className="icon-action install-action"
            type="button"
            onClick={installApp}
            aria-label="Install App"
            title="Install App"
          >
            <Download size={17} strokeWidth={2.4} aria-hidden="true" />
            <span className="sr-only">Install App</span>
          </button>
        )}
      </div>
      <div className="brand-cluster">
        <h1 className="app-title">
          <span className="brand-mark">Anai</span>
          <sub>nrldc</sub>
        </h1>
        <div className="connection-indicator" data-status={connectionStatus}>
          <span className="connection-dot" />
          <span className="connection-label">{connectionStatus}</span>
        </div>
      </div>
    </header>
  );
}
