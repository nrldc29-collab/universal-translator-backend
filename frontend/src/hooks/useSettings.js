import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'ut_settings_v1';

const DEFAULTS = {
  // Language
  uiLanguage: 'en',
  // Audio
  volume: 0.8,
  ttsSpeed: 1.0,
  ttsVoice: 'auto',
  micDeviceId: 'default',
  // Translation
  translationMode: 'fast',
  partialTts: true,
  translationProvider: 'hybrid',
  // Display
  theme: 'dark',
  textSize: 'medium',
  showConversationHistory: true,
  // Privacy
  // (no persistent values – only actions)
  // Notifications
  soundEffects: true,
  lowBandwidthMode: false,
  // Advanced
  debugMode: false,
  backendUrl: '',
  googleTtsApiKey: '',
};

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {}
  return { ...DEFAULTS };
}

function save(settings) {
  try {
    // Never persist the API key in plain storage – store only a flag
    const safe = { ...settings };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
  } catch {}
}

export function useSettings() {
  const [settings, setSettingsRaw] = useState(load);

  const setSettings = useCallback((updater) => {
    setSettingsRaw((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater };
      save(next);
      return next;
    });
  }, []);

  const updateSetting = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, [setSettings]);

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', settings.theme);
  }, [settings.theme]);

  // Apply text size to document
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-text-size', settings.textSize);
  }, [settings.textSize]);

  return { settings, setSettings, updateSetting };
}
