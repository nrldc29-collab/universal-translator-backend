import React from 'react';
import { Check, Download, Settings2, Share2, Wifi, WifiOff } from 'lucide-react';
import VolumeControl from './VolumeControl';
import AILangStatusBadge from './AILangStatusBadge';

export default function AppHeader({
  connectionStatus,
  shareConversationRoom,
  copiedKey,
  showInstallAction,
  installApp,
  volume,
  onVolumeChange,
  onOpenSettings,
  updateAvailable = false,
  apiUrl,
}) {
  const isOnline = connectionStatus === 'online';
  const isChecking = connectionStatus === 'checking';
  const isWarming = connectionStatus === 'warming';

  return (
    <header className="neo-header">
      {/* Left actions */}
      <div className="neo-header-left">
        <VolumeControl volume={volume} onVolumeChange={onVolumeChange} />
      </div>

      {/* Brand */}
      <div className={`neo-brand${isOnline ? ' neo-brand--live' : ''}`}>
        <h1 className="neo-title">
          <span className="neo-mark">ANAI</span>
          <span className="neo-sub">TRANSLATOR</span>
        </h1>
        <div className="neo-status-row">
          <span className={`neo-conn-dot ${connectionStatus}`} />
          <span className="neo-conn-label">
            {isWarming ? 'WARMING' : isChecking ? 'SYNCING' : isOnline ? 'LIVE' : 'OFFLINE'}
          </span>
          <AILangStatusBadge apiUrl={apiUrl} />
        </div>
      </div>

      {/* Right actions */}
      <div className="neo-header-right">
        <button
          className={`neo-icon-btn${copiedKey === 'room' ? ' success' : ''}`}
          type="button"
          onClick={shareConversationRoom}
          aria-label={copiedKey === 'room' ? 'Copied' : 'Share'}
          title="Share session"
        >
          {copiedKey === 'room' ? <Check size={16} strokeWidth={2.8} /> : <Share2 size={16} strokeWidth={2.2} />}
        </button>
        {showInstallAction && (
          <button className="neo-icon-btn" type="button" onClick={installApp} aria-label="Install" title="Install app">
            <Download size={16} strokeWidth={2.2} />
          </button>
        )}
        <button
          className="sp-gear-btn"
          type="button"
          onClick={onOpenSettings}
          aria-label={updateAvailable ? 'Settings (update available)' : 'Settings'}
          title={updateAvailable ? 'Update available' : 'Settings'}
        >
          <Settings2 size={16} strokeWidth={2.2} />
          {updateAvailable && <span className="sp-gear-badge" aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
