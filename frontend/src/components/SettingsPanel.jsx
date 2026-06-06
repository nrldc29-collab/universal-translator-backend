import React, { useState, useEffect, useRef } from 'react';
import {
  X, Languages, Volume2, Mic, Zap, Monitor, Lock, Bell, Settings2, Info,
  ChevronRight, ChevronDown, Sun, Moon, Contrast, Type, Eye, EyeOff,
  Trash2, Shield, Music, Bug, Server, Key, Check, AlertTriangle, Brain,
} from 'lucide-react';
import { TARGET_LANGUAGE_OPTIONS } from '../utils';

const FRONTEND_VERSION = '2.0.0';

const UI_LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
  { code: 'pt', label: 'Português' },
  { code: 'ht', label: 'Kreyòl Ayisyen' },
];

const SECTIONS = [
  { id: 'language',     label: 'Language',     Icon: Languages  },
  { id: 'audio',        label: 'Audio',         Icon: Volume2    },
  { id: 'translation',  label: 'Translation',   Icon: Zap        },
  { id: 'ailang',       label: 'AILang',         Icon: Brain      },
  { id: 'display',      label: 'Display',       Icon: Monitor    },
  { id: 'privacy',      label: 'Privacy',       Icon: Shield     },
  { id: 'notifications',label: 'Notifications', Icon: Bell       },
  { id: 'advanced',     label: 'Advanced',      Icon: Settings2  },
  { id: 'about',        label: 'About',         Icon: Info       },
];

export default function SettingsPanel({
  open,
  onClose,
  settings,
  updateSetting,
  onClearHistory,
  onClearSession,
  diagnostics,
  apiUrl,
}) {
  const [activeSection, setActiveSection] = useState('language');
  const [micDevices, setMicDevices] = useState([]);
  const [apiKeyVisible, setApiKeyVisible] = useState(false);
  const [backendTestResult, setBackendTestResult] = useState(null);
  const [testingBackend, setTestingBackend] = useState(false);
  const [clearConfirm, setClearConfirm] = useState(null);
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    navigator.mediaDevices?.enumerateDevices?.()
      .then((devices) => {
        const mics = devices.filter((d) => d.kind === 'audioinput');
        setMicDevices(mics);
      })
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  async function testBackendUrl() {
    const url = (settings.backendUrl || apiUrl || '').replace(/\/+$/, '');
    if (!url) { setBackendTestResult({ ok: false, msg: 'No URL configured' }); return; }
    setTestingBackend(true);
    setBackendTestResult(null);
    try {
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(5000) });
      const json = await res.json().catch(() => ({}));
      setBackendTestResult({ ok: res.ok, msg: res.ok ? `Connected — ${json.status || 'ok'}` : `HTTP ${res.status}` });
    } catch (err) {
      setBackendTestResult({ ok: false, msg: err?.message || 'Unreachable' });
    } finally {
      setTestingBackend(false);
    }
  }

  function handleClearConfirm(action) {
    if (clearConfirm === action) {
      if (action === 'history') onClearHistory?.();
      if (action === 'session') onClearSession?.();
      setClearConfirm(null);
    } else {
      setClearConfirm(action);
      setTimeout(() => setClearConfirm(null), 4000);
    }
  }

  if (!open) return null;

  return (
    <div className="sp-overlay" role="dialog" aria-modal="true" aria-label="Settings" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sp-panel" ref={panelRef}>
        {/* Header */}
        <div className="sp-header">
          <div className="sp-header-left">
            <Settings2 size={18} strokeWidth={2.2} className="sp-header-icon" />
            <span className="sp-header-title">Settings</span>
          </div>
          <button className="sp-close" onClick={onClose} aria-label="Close settings" type="button">
            <X size={18} strokeWidth={2.5} />
          </button>
        </div>

        <div className="sp-body">
          {/* Sidebar nav */}
          <nav className="sp-nav" aria-label="Settings sections">
            {SECTIONS.map(({ id, label, Icon }) => (
              <button
                key={id}
                type="button"
                className={`sp-nav-item${activeSection === id ? ' active' : ''}`}
                onClick={() => setActiveSection(id)}
              >
                <Icon size={15} strokeWidth={2.1} />
                <span>{label}</span>
                <ChevronRight size={13} strokeWidth={2} className="sp-nav-chevron" />
              </button>
            ))}
          </nav>

          {/* Content pane */}
          <div className="sp-content">
            {activeSection === 'language' && (
              <SectionLanguage settings={settings} updateSetting={updateSetting} />
            )}
            {activeSection === 'audio' && (
              <SectionAudio settings={settings} updateSetting={updateSetting} micDevices={micDevices} />
            )}
            {activeSection === 'translation' && (
              <SectionTranslation settings={settings} updateSetting={updateSetting} />
            )}
            {activeSection === 'ailang' && (
              <SectionAILang apiUrl={apiUrl} />
            )}
            {activeSection === 'display' && (
              <SectionDisplay settings={settings} updateSetting={updateSetting} />
            )}
            {activeSection === 'privacy' && (
              <SectionPrivacy
                clearConfirm={clearConfirm}
                onClearConfirm={handleClearConfirm}
              />
            )}
            {activeSection === 'notifications' && (
              <SectionNotifications settings={settings} updateSetting={updateSetting} />
            )}
            {activeSection === 'advanced' && (
              <SectionAdvanced
                settings={settings}
                updateSetting={updateSetting}
                apiKeyVisible={apiKeyVisible}
                setApiKeyVisible={setApiKeyVisible}
                testingBackend={testingBackend}
                backendTestResult={backendTestResult}
                onTestBackend={testBackendUrl}
                apiUrl={apiUrl}
              />
            )}
            {activeSection === 'about' && (
              <SectionAbout diagnostics={diagnostics} apiUrl={apiUrl} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Section: Language ───────────────────────────────────────────── */
function SectionLanguage({ settings, updateSetting }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Language Settings</h2>

      <SettingRow
        label="UI Language"
        hint="Language used for the interface"
        icon={<Languages size={15} />}
      >
        <select
          className="sp-select"
          value={settings.uiLanguage}
          onChange={(e) => updateSetting('uiLanguage', e.target.value)}
        >
          {UI_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>{l.label}</option>
          ))}
        </select>
      </SettingRow>

      <div className="sp-info-box">
        <Info size={13} />
        <span>Source and target languages are set directly on the main screen using the language selector dock.</span>
      </div>

      <div className="sp-divider-label">Available Translation Languages</div>
      <div className="sp-lang-grid">
        {TARGET_LANGUAGE_OPTIONS.map((opt) => (
          <div key={opt.code} className="sp-lang-badge">
            <span className="sp-lang-flag">{opt.flag}</span>
            <span className="sp-lang-name">{opt.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Section: Audio ──────────────────────────────────────────────── */
function SectionAudio({ settings, updateSetting, micDevices }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Audio Settings</h2>

      <SettingRow label="Volume" hint="Master playback volume" icon={<Volume2 size={15} />}>
        <div className="sp-slider-row">
          <input
            type="range" min={0} max={1} step={0.05}
            value={settings.volume}
            onChange={(e) => updateSetting('volume', parseFloat(e.target.value))}
            className="sp-slider"
            aria-label="Volume"
          />
          <span className="sp-slider-val">{Math.round(settings.volume * 100)}%</span>
        </div>
      </SettingRow>

      <SettingRow label="TTS Speed" hint="Speech playback rate" icon={<Music size={15} />}>
        <div className="sp-slider-row">
          <input
            type="range" min={0.5} max={2.0} step={0.1}
            value={settings.ttsSpeed}
            onChange={(e) => updateSetting('ttsSpeed', parseFloat(e.target.value))}
            className="sp-slider"
            aria-label="TTS Speed"
          />
          <span className="sp-slider-val">{settings.ttsSpeed.toFixed(1)}×</span>
        </div>
      </SettingRow>

      <SettingRow label="TTS Voice" hint="Preferred voice engine" icon={<Volume2 size={15} />}>
        <select
          className="sp-select"
          value={settings.ttsVoice}
          onChange={(e) => updateSetting('ttsVoice', e.target.value)}
        >
          <option value="auto">Auto (recommended)</option>
          <option value="backend">Backend Neural</option>
          <option value="browser">Browser TTS</option>
          <option value="google">Google Cloud TTS</option>
        </select>
      </SettingRow>

      <SettingRow label="Microphone" hint="Input device" icon={<Mic size={15} />}>
        <select
          className="sp-select"
          value={settings.micDeviceId}
          onChange={(e) => updateSetting('micDeviceId', e.target.value)}
        >
          <option value="default">Default Microphone</option>
          {micDevices.map((d) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `Microphone ${d.deviceId.slice(0, 6)}`}
            </option>
          ))}
        </select>
      </SettingRow>

      {micDevices.length === 0 && (
        <div className="sp-info-box warning">
          <AlertTriangle size={13} />
          <span>Grant microphone permission to list available devices.</span>
        </div>
      )}
    </div>
  );
}

/* ─── Section: Translation ────────────────────────────────────────── */
function SectionTranslation({ settings, updateSetting }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Translation Settings</h2>

      <SettingRow label="Translation Mode" hint="Speed vs. accuracy tradeoff" icon={<Zap size={15} />}>
        <div className="sp-button-group">
          {[
            { value: 'fast',     label: 'Fast',     hint: '~200ms' },
            { value: 'balanced', label: 'Balanced', hint: '~400ms' },
            { value: 'accurate', label: 'Accurate', hint: '~800ms' },
          ].map(({ value, label, hint }) => (
            <button
              key={value}
              type="button"
              className={`sp-btn-option${settings.translationMode === value ? ' active' : ''}`}
              onClick={() => updateSetting('translationMode', value)}
            >
              <span>{label}</span>
              <span className="sp-btn-hint">{hint}</span>
            </button>
          ))}
        </div>
      </SettingRow>

      <SettingRow label="Partial TTS" hint="Speak partial translations as they arrive" icon={<Volume2 size={15} />}>
        <Toggle
          value={settings.partialTts}
          onChange={(v) => updateSetting('partialTts', v)}
        />
      </SettingRow>

      <SettingRow label="Translation Provider" hint="Backend translation engine" icon={<Zap size={15} />}>
        <select
          className="sp-select"
          value={settings.translationProvider}
          onChange={(e) => updateSetting('translationProvider', e.target.value)}
        >
          <option value="hybrid">Hybrid (Auto)</option>
          <option value="lightweight">Lightweight (Offline)</option>
          <option value="remote">Remote (Online)</option>
          <option value="marian">Marian NMT</option>
        </select>
      </SettingRow>

      <div className="sp-info-box">
        <Info size={13} />
        <span><strong>Hybrid</strong> uses lightweight translation first, then falls back to remote APIs for complex phrases. Best for most use cases.</span>
      </div>
    </div>
  );
}

/* ─── Section: AILang ─────────────────────────────────────────────── */
function SectionAILang({ apiUrl }) {
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const [switching, setSwitching] = useState(false);
  const [switchResult, setSwitchResult] = useState(null);

  useEffect(() => {
    loadStatus();
  }, [apiUrl]);

  const loadStatus = async () => {
    if (!apiUrl) return;
    try {
      const res = await fetch(`${apiUrl}/health/ollama`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) return;
      const data = await res.json();
      setOllamaStatus(data);
    } catch {
      // Silently fail
    }
  };

  const switchModel = async (modelName) => {
    if (!apiUrl || modelName === ollamaStatus?.model) return;
    setSwitching(true);
    setSwitchResult(null);
    try {
      const res = await fetch(`${apiUrl}/health/ollama/model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName }),
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      if (res.ok) {
        setSwitchResult({ ok: true, msg: data.message });
        await loadStatus();
      } else {
        setSwitchResult({ ok: false, msg: data.detail?.error || data.detail || 'Switch failed' });
      }
    } catch (err) {
      setSwitchResult({ ok: false, msg: err?.message || 'Network error' });
    } finally {
      setSwitching(false);
    }
  };

  const isActive = ollamaStatus?.warmup?.status === 'active' || ollamaStatus?.warmup?.status === 'switched';
  const isDegraded = ollamaStatus?.enabled && !ollamaStatus?.reachable;
  const models = ollamaStatus?.models || [];

  return (
    <div className="sp-section">
      <h2 className="sp-section-title">AILang Intelligence</h2>

      <SettingRow
        label="Status"
        hint={ollamaStatus?.warmup?.message || (ollamaStatus ? 'Checking...' : 'Loading...')}
        icon={<Brain size={15} />}
      >
        <span className={`ailang-status-badge ${isActive ? 'active' : isDegraded ? 'degraded' : 'offline'}`} style={{ fontSize: '0.72rem' }}>
          {isActive ? 'Active' : isDegraded ? 'Degraded' : ollamaStatus?.enabled ? 'Checking' : 'Offline'}
        </span>
      </SettingRow>

      <div className="sp-divider-label">Ollama Model</div>

      {ollamaStatus?.enabled && ollamaStatus?.reachable ? (
        <SettingRow
          label="Active Model"
          hint={models.length > 0 ? `${models.length} model${models.length !== 1 ? 's' : ''} available` : 'No models found'}
          icon={<Zap size={15} />}
        >
          <select
            className="sp-select"
            value={ollamaStatus?.model || 'mistral'}
            onChange={(e) => switchModel(e.target.value)}
            disabled={switching}
          >
            {models.map((m) => (
              <option key={m} value={m.split(':')[0]}>{m}</option>
            ))}
            {models.length === 0 && (
              <option value="">No models available</option>
            )}
          </select>
        </SettingRow>
      ) : ollamaStatus?.enabled && !ollamaStatus?.reachable ? (
        <div className="sp-info-box warning">
          <AlertTriangle size={13} />
          <span>Ollama is enabled but not reachable at {ollamaStatus?.url}. Start Ollama or check OLLAMA_URL.</span>
        </div>
      ) : (
        <div className="sp-info-box">
          <Info size={13} />
          <span>Ollama is not enabled. Set OLLAMA_ENABLED=true and restart the backend to activate local LLM intelligence.</span>
        </div>
      )}

      {switchResult && (
        <div className={`sp-info-box ${switchResult.ok ? '' : 'warning'}`}>
          {switchResult.ok ? <Check size={13} /> : <AlertTriangle size={13} />}
          <span>{switchResult.msg}</span>
        </div>
      )}

      {switching && (
        <div className="sp-info-box">
          <Brain size={13} className="sp-spin-icon" />
          <span>Switching model...</span>
        </div>
      )}

      <div className="sp-divider-label">How It Works</div>

      <div className="sp-info-box">
        <Brain size={13} />
        <span>
          <strong>AILang</strong> enhances translations with context memory, domain detection,
          ambiguity resolution, glossary enforcement, and emotion-aware TTS.
          It tries providers in order: <strong>Ollama</strong> (local, free) →{' '}
          <strong>OpenAI</strong> (cloud) → <strong>offline rules</strong> (stub).
        </span>
      </div>

      <div className="sp-info-box">
        <Info size={13} />
        <span>
          Switch models instantly without restart. Use <strong>phi3</strong> or <strong>tinyllama</strong> for
          speed, <strong>mistral</strong> or <strong>llama3</strong> for accuracy. Run{' '}
          <code style={{ fontFamily: 'monospace', fontSize: '0.85em' }}>ollama pull &lt;model&gt;</code> to add models.
        </span>
      </div>
    </div>
  );
}

/* ─── Section: Display ────────────────────────────────────────────── */
function SectionDisplay({ settings, updateSetting }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Display Settings</h2>

      <SettingRow label="Theme" hint="App color scheme" icon={<Monitor size={15} />}>
        <div className="sp-theme-grid">
          {[
            { value: 'dark',   label: 'Dark',   Icon: Moon     },
            { value: 'darker', label: 'Darker', Icon: Contrast },
            { value: 'auto',   label: 'Auto',   Icon: Sun      },
          ].map(({ value, label, Icon }) => (
            <button
              key={value}
              type="button"
              className={`sp-theme-btn${settings.theme === value ? ' active' : ''}`}
              onClick={() => updateSetting('theme', value)}
            >
              <Icon size={16} strokeWidth={2} />
              <span>{label}</span>
              {settings.theme === value && <Check size={11} className="sp-theme-check" />}
            </button>
          ))}
        </div>
      </SettingRow>

      <SettingRow label="Text Size" hint="Interface font size" icon={<Type size={15} />}>
        <div className="sp-button-group">
          {[
            { value: 'small',  label: 'S' },
            { value: 'medium', label: 'M' },
            { value: 'large',  label: 'L' },
            { value: 'xlarge', label: 'XL' },
          ].map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={`sp-btn-option compact${settings.textSize === value ? ' active' : ''}`}
              onClick={() => updateSetting('textSize', value)}
            >
              {label}
            </button>
          ))}
        </div>
      </SettingRow>

      <SettingRow label="Conversation History" hint="Show recent translations on screen" icon={settings.showConversationHistory ? <Eye size={15} /> : <EyeOff size={15} />}>
        <Toggle
          value={settings.showConversationHistory}
          onChange={(v) => updateSetting('showConversationHistory', v)}
        />
      </SettingRow>
    </div>
  );
}

/* ─── Section: Privacy ────────────────────────────────────────────── */
function SectionPrivacy({ clearConfirm, onClearConfirm }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Privacy Settings</h2>

      <div className="sp-info-box">
        <Shield size={13} />
        <span>All translations are processed on your configured backend. No data is stored on third-party servers by default.</span>
      </div>

      <div className="sp-divider-label">Data Management</div>

      <div className="sp-privacy-action">
        <div className="sp-privacy-desc">
          <Trash2 size={15} className="sp-privacy-icon" />
          <div>
            <div className="sp-privacy-title">Clear Conversation History</div>
            <div className="sp-privacy-hint">Removes all local conversation turns from this session</div>
          </div>
        </div>
        <button
          type="button"
          className={`sp-danger-btn${clearConfirm === 'history' ? ' confirm' : ''}`}
          onClick={() => onClearConfirm('history')}
        >
          {clearConfirm === 'history' ? 'Tap again to confirm' : 'Clear History'}
        </button>
      </div>

      <div className="sp-privacy-action">
        <div className="sp-privacy-desc">
          <Lock size={15} className="sp-privacy-icon" />
          <div>
            <div className="sp-privacy-title">Clear Session Data</div>
            <div className="sp-privacy-hint">Resets session ID, speaker profiles, and cached audio</div>
          </div>
        </div>
        <button
          type="button"
          className={`sp-danger-btn${clearConfirm === 'session' ? ' confirm' : ''}`}
          onClick={() => onClearConfirm('session')}
        >
          {clearConfirm === 'session' ? 'Tap again to confirm' : 'Clear Session'}
        </button>
      </div>

      <div className="sp-divider-label">Local Storage</div>
      <div className="sp-privacy-action">
        <div className="sp-privacy-desc">
          <Shield size={15} className="sp-privacy-icon" />
          <div>
            <div className="sp-privacy-title">Data Stored Locally</div>
            <div className="sp-privacy-hint">Device ID, language preferences, UI settings, speaker labels</div>
          </div>
        </div>
        <span className="sp-badge-info">Device only</span>
      </div>
    </div>
  );
}

/* ─── Section: Notifications ──────────────────────────────────────── */
function SectionNotifications({ settings, updateSetting }) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Notification Settings</h2>

      <SettingRow label="Sound Effects" hint="UI feedback sounds (taps, alerts)" icon={<Bell size={15} />}>
        <Toggle
          value={settings.soundEffects}
          onChange={(v) => updateSetting('soundEffects', v)}
        />
      </SettingRow>

      <SettingRow label="Low Bandwidth Mode" hint="Skip voice audio to save data — text only" icon={<Zap size={15} />}>
        <Toggle
          value={settings.lowBandwidthMode}
          onChange={(v) => updateSetting('lowBandwidthMode', v)}
        />
      </SettingRow>

      <div className="sp-info-box">
        <Info size={13} />
        <span>Translation audio playback volume is controlled separately in the Audio section.</span>
      </div>
    </div>
  );
}

/* ─── Section: Advanced ───────────────────────────────────────────── */
function SectionAdvanced({
  settings, updateSetting,
  apiKeyVisible, setApiKeyVisible,
  testingBackend, backendTestResult, onTestBackend,
  apiUrl,
}) {
  return (
    <div className="sp-section">
      <h2 className="sp-section-title">Advanced Settings</h2>

      <SettingRow label="Debug Mode" hint="Show diagnostics panel and verbose logs" icon={<Bug size={15} />}>
        <Toggle
          value={settings.debugMode}
          onChange={(v) => updateSetting('debugMode', v)}
        />
      </SettingRow>

      <div className="sp-divider-label">Backend Connection</div>

      <SettingRow label="Backend URL" hint="Override the default API endpoint" icon={<Server size={15} />}>
        <div className="sp-input-row">
          <input
            type="url"
            className="sp-input"
            placeholder={apiUrl || 'https://your-backend.railway.app'}
            value={settings.backendUrl}
            onChange={(e) => updateSetting('backendUrl', e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <button
            type="button"
            className={`sp-test-btn${testingBackend ? ' testing' : ''}${backendTestResult?.ok === true ? ' ok' : backendTestResult?.ok === false ? ' fail' : ''}`}
            onClick={onTestBackend}
            disabled={testingBackend}
          >
            {testingBackend ? '…' : 'Test'}
          </button>
        </div>
      </SettingRow>

      {backendTestResult && (
        <div className={`sp-info-box ${backendTestResult.ok ? '' : 'warning'}`}>
          {backendTestResult.ok ? <Check size={13} /> : <AlertTriangle size={13} />}
          <span>{backendTestResult.msg}</span>
        </div>
      )}

      <div className="sp-divider-label">API Keys</div>

      <SettingRow label="Google TTS API Key" hint="For Google Cloud Text-to-Speech voices" icon={<Key size={15} />}>
        <div className="sp-input-row">
          <input
            type={apiKeyVisible ? 'text' : 'password'}
            className="sp-input"
            placeholder="AIza..."
            value={settings.googleTtsApiKey}
            onChange={(e) => updateSetting('googleTtsApiKey', e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            className="sp-icon-btn"
            onClick={() => setApiKeyVisible((v) => !v)}
            aria-label={apiKeyVisible ? 'Hide key' : 'Show key'}
          >
            {apiKeyVisible ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </SettingRow>

      <div className="sp-info-box warning">
        <AlertTriangle size={13} />
        <span>API keys are stored in browser localStorage. Use a restricted key and avoid storing production credentials in shared devices.</span>
      </div>
    </div>
  );
}

/* ─── Section: About ──────────────────────────────────────────────── */
function SectionAbout({ diagnostics, apiUrl }) {
  const backendVersion = diagnostics?.version || diagnostics?.release || '—';
  const translationRuntime = diagnostics?.translation_runtime || '—';
  const sttProvider = diagnostics?.stt_provider || '—';
  const cipMode = diagnostics?.cip?.mode || '—';

  return (
    <div className="sp-section">
      <h2 className="sp-section-title">About ANAI Translator</h2>

      <div className="sp-about-brand">
        <div className="sp-about-logo">
          <span className="sp-about-mark">ANAI</span>
          <span className="sp-about-sub">TRANSLATOR</span>
        </div>
        <div className="sp-about-tagline">Real-time AI translation for everyone</div>
      </div>

      <div className="sp-divider-label">Version Info</div>
      <div className="sp-info-grid">
        <InfoRow label="Frontend" value={`v${FRONTEND_VERSION}`} />
        <InfoRow label="Backend" value={backendVersion} />
        <InfoRow label="Translation" value={translationRuntime} />
        <InfoRow label="STT Provider" value={sttProvider} />
        <InfoRow label="CIP Mode" value={cipMode} />
        <InfoRow label="API URL" value={apiUrl || '—'} mono />
      </div>

      <div className="sp-divider-label">System</div>
      <div className="sp-info-grid">
        <InfoRow label="Platform" value={navigator.platform || '—'} />
        <InfoRow label="Browser" value={getBrowserName()} />
        <InfoRow label="Online" value={navigator.onLine ? 'Yes' : 'No'} />
      </div>

      <div className="sp-divider-label">Legal</div>
      <div className="sp-info-box">
        <Info size={13} />
        <span>ANAI Translator uses open-source speech and translation engines. No audio or text is stored on external servers without your explicit consent.</span>
      </div>
    </div>
  );
}

/* ─── Shared sub-components ───────────────────────────────────────── */
function SettingRow({ label, hint, icon, children }) {
  return (
    <div className="sp-row">
      <div className="sp-row-left">
        <span className="sp-row-icon">{icon}</span>
        <div>
          <div className="sp-row-label">{label}</div>
          {hint && <div className="sp-row-hint">{hint}</div>}
        </div>
      </div>
      <div className="sp-row-right">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      className={`sp-toggle${value ? ' on' : ''}`}
      onClick={() => onChange(!value)}
    >
      <span className="sp-toggle-thumb" />
    </button>
  );
}

function InfoRow({ label, value, mono }) {
  return (
    <div className="sp-info-row">
      <span className="sp-info-label">{label}</span>
      <span className={`sp-info-value${mono ? ' mono' : ''}`}>{value}</span>
    </div>
  );
}

function getBrowserName() {
  const ua = navigator.userAgent;
  if (ua.includes('Firefox')) return 'Firefox';
  if (ua.includes('Edg/')) return 'Edge';
  if (ua.includes('Chrome')) return 'Chrome';
  if (ua.includes('Safari')) return 'Safari';
  return 'Unknown';
}
