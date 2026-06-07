import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'ut_settings_v1';
const SETTINGS_VERSION = 6;

const DEFAULTS = {
  // Language
  uiLanguage: 'en',
  // Audio
  volume: 0.84,
  ttsSpeed: 1.0,
  ttsVoice: 'backend',
  micDeviceId: 'default',
  // Translation
  translationMode: 'fast',
  partialTts: false,
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
  settingsVersion: SETTINGS_VERSION,
};

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const loaded = { ...DEFAULTS, ...JSON.parse(raw) };
      if ((loaded.settingsVersion || 0) < SETTINGS_VERSION) {
        if ((loaded.settingsVersion || 0) < 2) {
          loaded.partialTts = true;
        }
        if ((loaded.settingsVersion || 0) < 3) {
          if (!loaded.ttsSpeed || loaded.ttsSpeed === 1) loaded.ttsSpeed = 0.94;
          loaded.partialTts = false;
        }
        if ((loaded.settingsVersion || 0) < 4) {
          if (!loaded.ttsVoice || loaded.ttsVoice === 'auto') loaded.ttsVoice = 'backend';
        }
        if ((loaded.settingsVersion || 0) < 5) {
          loaded.ttsVoice = 'backend';
          loaded.partialTts = false;
          if (!loaded.ttsSpeed || loaded.ttsSpeed >= 1) loaded.ttsSpeed = 0.94;
        }
        if ((loaded.settingsVersion || 0) < 6) {
          loaded.ttsVoice = 'backend';
          loaded.partialTts = false;
          loaded.ttsSpeed = 1.0;
        }
        loaded.lowBandwidthMode = false;
        loaded.settingsVersion = SETTINGS_VERSION;
        save(loaded);
      }
      return loaded;
    }
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
