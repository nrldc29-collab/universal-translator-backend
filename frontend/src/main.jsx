import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Mic, Radio, Square, Languages } from 'lucide-react';
import './styles.css';
import { registerServiceWorker } from './pwa';

function isLocalHost(hostname) {
  const sourceName = languages[sourceLanguage] || sourceLanguage.toUpperCase();
  const targetName = languages[targetLanguage] || targetLanguage.toUpperCase();
  const sourceText = partialTranscript || result?.source_text || text || 'Tap the mic and speak';
  const translatedText = liveTranslation || result?.translated_text || 'Your translation will appear here';
  const micState = streaming ? 'listening' : processing ? 'translating' : playing ? 'speaking' : 'idle';
  const connectionLabel = connectionStatus === 'online' ? 'Online' : connectionStatus === 'offline' ? 'Offline' : 'Connecting';

  return (
    <main className="app-shell">
      <section className="phone-frame">
        <header className="topbar">
          <div>
            <p className="brand-kicker">Universal Translator</p>
            <h1>Speak freely.</h1>
          </div>
          <div className={`status-pill ${connectionStatus}`}><span />{connectionLabel}</div>
        </header>

        {!authToken && (
          <section className="glass-card signin-card">
            <p className="label">Private session</p>
            <div className="signin-grid">
              <input aria-label="Username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Username" />
              <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" />
              <button onClick={login}>Log in</button>
            </div>
          </section>
        )}

        <section className="hero-panel">
          <div className="language-row">
            <select aria-label="Source language" value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}>
              {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
            <button className="swap-button" onClick={() => { setSourceLanguage(targetLanguage); setTargetLanguage(sourceLanguage); }} aria-label="Swap languages">?</button>
            <select aria-label="Target language" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>
              {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </div>

          <button className={`mic-orb ${micState}`} onClick={toggleStreaming} disabled={processing && !streaming} aria-label={streaming ? 'Stop listening' : 'Start speaking'}>
            <span className="orb-ring" />
            {streaming ? <Square size={42} /> : <Mic size={52} />}
          </button>
          <p className="tap-label">{streaming ? 'Listening...' : processing ? 'Translating...' : playing ? 'Speaking...' : 'Tap to Speak'}</p>
          <p className="quiet-status">{status}</p>
        </section>

        <section className="translation-stack">
          <article className="glass-card transcript-card">
            <p className="label">You said</p>
            <p>{sourceText}</p>
          </article>
          <article className="glass-card translation-card">
            <p className="label">Translation</p>
            <p>{translatedText}</p>
          </article>
        </section>

        <section className="conversation-panel">
          <div className="conversation-header">
            <p className="label">Conversation</p>
            <button onClick={runSelfTest} disabled={selfTest.status === 'running'}>Self test</button>
          </div>
          <div className="speaker-grid">
            <button className={duplex.A.active ? 'speaker active' : 'speaker'} onClick={() => toggleDuplexSpeaker('A')}>
              <span>Speaker A</span>
              <strong>{sourceName}</strong>
            </button>
            <button className={duplex.B.active ? 'speaker active alt' : 'speaker alt'} onClick={() => toggleDuplexSpeaker('B')}>
              <span>Speaker B</span>
              <strong>{targetName}</strong>
            </button>
          </div>
          <div className="timeline">
            {(sharedSession?.history || []).slice(-4).map((turn, index) => (
              <div className="turn" key={`${turn.created_at}-${index}`}>
                <span>{turn.speaker || 'A'}</span>
                <p>{turn.source_text}</p>
                <strong>{turn.translated_text}</strong>
              </div>
            ))}
            {!(sharedSession?.history || []).length && <p className="empty-timeline">Live conversation appears here.</p>}
          </div>
        </section>

        <section className="settings-sheet">
          <details>
            <summary>Settings</summary>
            <div className="settings-grid">
              <label>Voice speed<select value={speechSpeed} onChange={(event) => setSpeechSpeed(event.target.value)}><option value="slow">Slow</option><option value="normal">Normal</option><option value="fast">Fast</option></select></label>
              <label>Audio quality<select value={lowBandwidthMode ? 'low' : 'normal'} onChange={(event) => setLowBandwidthMode(event.target.value === 'low')}><option value="normal">Normal</option><option value="low">Low bandwidth</option></select></label>
              <label>Accessibility<select value={accessibilityMode} onChange={(event) => setAccessibilityMode(event.target.value)}><option value="balanced">Balanced</option><option value="noise">Noisy room</option><option value="accent">Strong accent</option><option value="slow">Slower conversation</option></select></label>
              <button onClick={requestMicPermission}>Allow Microphone</button>
              <button onClick={unlockMobileAudio}>{mobileAudioUnlocked ? 'Audio Ready' : 'Unlock Audio'}</button>
              <button disabled={!installPrompt || pwaInstalled} onClick={installApp}>{pwaInstalled ? 'Installed' : 'Install App'}</button>
              {authToken && <button onClick={logout}>Log out</button>}
            </div>
          </details>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);

