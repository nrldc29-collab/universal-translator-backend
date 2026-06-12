import React from 'react';
import { Check, CircleHelp, Download, Settings2, Share2 } from 'lucide-react';
import { ONBOARDING_OPEN_EVENT } from './OnboardingTour';
import VolumeControl from './VolumeControl';
import AILangStatusBadge from './AILangStatusBadge';
import NeuralVoiceBadge from './NeuralVoiceBadge';

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
  diagnostics = null,
}) {
  const isOnline = connectionStatus === 'online';
  const isChecking = connectionStatus === 'checking';
  const isWarming = connectionStatus === 'warming';

  return (
    <header className="neo-header">
      {/* Left actions */}
      <div className="neo-header-left">
        <VolumeControl initialVolume={volume} onVolumeChange={onVolumeChange} />
      </div>

      {/* Brand */}
      <div className={`neo-brand${isOnline ? ' neo-brand--live' : ''}`}>
        <h1 className="neo-title">
          <span className="neo-mark">Anai</span>
          {isOnline ? <span className="neo-sub neo-sub--live">Bridge</span> : null}
        </h1>
        <div className="neo-status-row">
          <span className={`neo-conn-dot ${connectionStatus}`} />
          <span className="neo-conn-label">
            {isWarming ? 'OPENING' : isChecking ? 'LINKING' : isOnline ? 'LIVE' : 'OFFLINE'}
          </span>
          <span className="neo-build-stamp" title="UI build">v46</span>
          <AILangStatusBadge apiUrl={apiUrl} />
          <NeuralVoiceBadge diagnostics={diagnostics} connectionStatus={connectionStatus} />
        </div>
      </div>

      {/* Right actions */}
      <div className="neo-header-right">
        <button
          className="neo-icon-btn"
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent(ONBOARDING_OPEN_EVENT))}
          aria-label="Help and tips"
          title="Help and tips"
        >
          <CircleHelp size={16} strokeWidth={2.2} />
        </button>
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
          data-tour-target="settings"
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
