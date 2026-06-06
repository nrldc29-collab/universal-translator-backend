import { View, Text, StyleSheet, ScrollView, Pressable, TextInput } from "react-native";
import { useEffect, useState } from "react";
import { Ionicons } from "@expo/vector-icons";

interface SettingsScreenProps {
  wsUrl: string;
  setWsUrl: (url: string) => void;
  onSaveUrl?: (url: string) => void | Promise<void>;
  onClose?: () => void;
  onTestConnection?: () => void | Promise<void>;
  onLogin?: () => void | Promise<void>;
  onLogout?: () => void | Promise<void>;
  username?: string;
  setUsername?: (value: string) => void;
  password?: string;
  setPassword?: (value: string) => void;
  isLoggedIn?: boolean;
  recentUrls?: string[];
  sourceLanguage: string;
  setSourceLanguage: (lang: string) => void;
  targetLanguage: string;
  setTargetLanguage: (lang: string) => void;
  onClearData: () => void;
  volume?: number;
  setVolume?: (vol: number) => void;
  playbackSpeed?: number;
  setPlaybackSpeed?: (speed: number) => void;
  audioQuality?: string;
  setAudioQuality?: (quality: string) => void;
  AUDIO_QUALITIES?: Record<string, { preset: any; label: string; description: string }>;
  debugMode?: boolean;
  setDebugMode?: (enabled: boolean) => void;
}

const LANGUAGES = [
  { code: "en", name: "English", native: "English", flag: "🇺🇸" },
  { code: "es", name: "Spanish", native: "Español", flag: "🇪🇸" },
  { code: "ht", name: "Haitian Creole", native: "Kreyòl Ayisyen", flag: "🇭🇹" },
  { code: "fr", name: "French", native: "Français", flag: "🇫🇷" },
  { code: "de", name: "German", native: "Deutsch", flag: "🇩🇪" },
  { code: "it", name: "Italian", native: "Italiano", flag: "🇮🇹" },
  { code: "pt", name: "Portuguese", native: "Português", flag: "🇧🇷" },
  { code: "zh", name: "Chinese", native: "中文", flag: "🇨🇳" },
  { code: "ja", name: "Japanese", native: "日本語", flag: "🇯🇵" },
  { code: "ko", name: "Korean", native: "한국어", flag: "🇰🇷" },
  { code: "ar", name: "Arabic", native: "العربية", flag: "🇸🇦" },
  { code: "ru", name: "Russian", native: "Русский", flag: "🇷🇺" },
];

export default function SettingsScreen({
  wsUrl,
  setWsUrl,
  sourceLanguage,
  setSourceLanguage,
  targetLanguage,
  setTargetLanguage,
  onClearData,
  volume = 0.8,
  setVolume,
  playbackSpeed = 1.0,
  setPlaybackSpeed,
  audioQuality = "HIGH",
  setAudioQuality,
  AUDIO_QUALITIES,
  debugMode = false,
  setDebugMode,
  onSaveUrl,
  onClose,
  onTestConnection,
  onLogin,
  onLogout,
  username = "",
  setUsername,
  password = "",
  setPassword,
  isLoggedIn = false,
  recentUrls = [],
}: SettingsScreenProps) {
  const [localVolume, setLocalVolume] = useState(volume);
  const [localSpeed, setLocalSpeed] = useState(playbackSpeed);
  const [localUrl, setLocalUrl] = useState(wsUrl);

  useEffect(() => {
    setLocalUrl(wsUrl);
  }, [wsUrl]);

  const handleVolumeChange = (value: number) => {
    setLocalVolume(value);
    setVolume?.(value);
  };

  const handleSpeedChange = (value: number) => {
    setLocalSpeed(value);
    setPlaybackSpeed?.(value);
  };

  const adjustVolume = (delta: number) => {
    const newValue = Math.max(0, Math.min(1, localVolume + delta));
    handleVolumeChange(newValue);
  };

  const adjustSpeed = (delta: number) => {
    const newValue = Math.max(0.5, Math.min(2.0, localSpeed + delta));
    handleSpeedChange(newValue);
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>Settings</Text>
          <Text style={styles.subtitle}>Languages, audio, and server connection.</Text>
        </View>
        {onClose ? (
          <Pressable onPress={onClose} style={styles.closeBtn} accessibilityRole="button" accessibilityLabel="Close settings">
            <Ionicons name="close" size={22} color="#e2e8f0" />
          </Pressable>
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Server</Text>
        <Text style={styles.settingDescription}>Railway HTTPS URL or local IP (port 8000).</Text>
        <TextInput
          value={localUrl}
          onChangeText={(value) => {
            setLocalUrl(value);
            setWsUrl(value);
          }}
          placeholder="https://your-app.up.railway.app"
          placeholderTextColor="#64748b"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          style={styles.urlInput}
          accessibilityLabel="Backend server URL"
        />
        {recentUrls.length > 0 ? (
          <View style={styles.chipRow}>
            {recentUrls.map((url) => (
              <Pressable
                key={url}
                style={[styles.chip, localUrl === url && styles.chipActive]}
                onPress={() => {
                  setLocalUrl(url);
                  setWsUrl(url);
                }}
              >
                <Text numberOfLines={1} style={[styles.chipText, localUrl === url && styles.chipTextActive]}>
                  {url.replace(/^https?:\/\//, "").slice(0, 28)}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}
        <View style={styles.buttonRow}>
          <Pressable style={styles.actionChip} onPress={() => onTestConnection?.()}>
            <Text style={styles.actionChipText}>Test connection</Text>
          </Pressable>
          <Pressable
            style={[styles.actionChip, styles.actionChipPrimary]}
            onPress={() => onSaveUrl?.(localUrl)}
          >
            <Text style={[styles.actionChipText, styles.actionChipTextPrimary]}>Save & reconnect</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        {isLoggedIn ? (
          <>
            <Text style={styles.settingDescription}>Signed in. Tap below to sign out.</Text>
            <Pressable style={styles.actionChip} onPress={() => onLogout?.()}>
              <Text style={styles.actionChipText}>Sign out</Text>
            </Pressable>
          </>
        ) : (
          <>
            <TextInput
              value={username}
              onChangeText={setUsername}
              placeholder="Username"
              placeholderTextColor="#64748b"
              autoCapitalize="none"
              style={styles.urlInput}
              accessibilityLabel="Username"
            />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor="#64748b"
              secureTextEntry
              style={styles.urlInput}
              accessibilityLabel="Password"
            />
            <Pressable style={[styles.actionChip, styles.actionChipPrimary]} onPress={() => onLogin?.()}>
              <Text style={[styles.actionChipText, styles.actionChipTextPrimary]}>Sign in</Text>
            </Pressable>
          </>
        )}
      </View>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Audio Settings</Text>
        
        <View style={styles.settingRow}>
          <Text style={styles.label}>Volume</Text>
          <Text style={styles.value}>{Math.round(localVolume * 100)}%</Text>
        </View>
        <View style={styles.buttonRow}>
          <Pressable style={styles.adjustButton} onPress={() => adjustVolume(-0.1)}>
            <Text style={styles.adjustButtonText}>-</Text>
          </Pressable>
          <Pressable style={styles.adjustButton} onPress={() => adjustVolume(0.1)}>
            <Text style={styles.adjustButtonText}>+</Text>
          </Pressable>
        </View>

        <View style={styles.settingRow}>
          <Text style={styles.label}>TTS Speed</Text>
          <Text style={styles.value}>{localSpeed.toFixed(1)}x</Text>
        </View>
        <View style={styles.buttonRow}>
          <Pressable style={styles.adjustButton} onPress={() => adjustSpeed(-0.1)}>
            <Text style={styles.adjustButtonText}>-</Text>
          </Pressable>
          <Pressable style={styles.adjustButton} onPress={() => adjustSpeed(0.1)}>
            <Text style={styles.adjustButtonText}>+</Text>
          </Pressable>
        </View>

        {AUDIO_QUALITIES && (
          <>
            <View style={styles.settingRow}>
              <Text style={styles.label}>Audio Quality</Text>
              <Text style={styles.value}>{AUDIO_QUALITIES[audioQuality]?.label || audioQuality}</Text>
            </View>
            <View style={styles.chipRow}>
              {Object.entries(AUDIO_QUALITIES).map(([key, quality]) => (
                <Pressable
                  key={key}
                  style={[styles.chip, audioQuality === key && styles.chipActive]}
                  onPress={() => setAudioQuality?.(key)}
                >
                  <Text style={[styles.chipText, audioQuality === key && styles.chipTextActive]}>
                    {quality.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Text style={styles.settingDescription}>{AUDIO_QUALITIES[audioQuality]?.description}</Text>
          </>
        )}
      </View>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Language Preferences</Text>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Source Language</Text>
          <Text style={styles.value}>{LANGUAGES.find(l => l.code === sourceLanguage)?.name || sourceLanguage}</Text>
        </View>
        <View style={styles.chipRow}>
          {LANGUAGES.map((language) => (
            <Pressable
              key={`source-${language.code}`}
              style={[styles.chip, sourceLanguage === language.code && styles.chipActive]}
              onPress={() => setSourceLanguage(language.code)}
            >
              <Text style={[styles.chipText, sourceLanguage === language.code && styles.chipTextActive]}>
                {language.flag} {language.native || language.name}
              </Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Target Language</Text>
          <Text style={styles.value}>{LANGUAGES.find(l => l.code === targetLanguage)?.name || targetLanguage}</Text>
        </View>
        <View style={styles.chipRow}>
          {LANGUAGES.map((language) => (
            <Pressable
              key={`target-${language.code}`}
              style={[styles.chip, targetLanguage === language.code && styles.chipActive]}
              onPress={() => setTargetLanguage(language.code)}
            >
              <Text style={[styles.chipText, targetLanguage === language.code && styles.chipTextActive]}>
                {language.flag} {language.native || language.name}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {setDebugMode && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Developer Options</Text>
          <View style={styles.settingRow}>
            <Text style={styles.label}>Debug Mode</Text>
            <Pressable
              style={[styles.toggle, debugMode && styles.toggleActive]}
              onPress={() => setDebugMode(!debugMode)}
            >
              <Text style={[styles.toggleText, debugMode && styles.toggleTextActive]}>
                {debugMode ? "ON" : "OFF"}
              </Text>
            </Pressable>
          </View>
          <Text style={styles.settingDescription}>
            Enable detailed logging and debug information
          </Text>
        </View>
      )}
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Version</Text>
          <Text style={styles.value}>1.0.0</Text>
        </View>
        <View style={styles.settingRow}>
          <Text style={styles.label}>App</Text>
          <Text style={styles.value}>Anai Translator Mobile</Text>
        </View>
      </View>
      
      <View style={styles.dangerZone}>
        <Text style={styles.dangerTitle}>Danger Zone</Text>
        <Pressable style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]} onPress={onClearData}>
          <Text style={styles.buttonText}>Clear All Stored Data</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: "#050711" },
  headerRow: { flexDirection: "row", alignItems: "flex-start", gap: 12, marginBottom: 8 },
  closeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.2)",
  },
  title: { fontSize: 28, fontWeight: "900", color: '#f8fafc', marginBottom: 4 },
  subtitle: { color: '#94a3b8', fontSize: 13, marginBottom: 10 },
  urlInput: {
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.28)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: "#f8fafc",
    fontSize: 14,
    marginTop: 8,
  },
  actionChip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 999,
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.78)",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.2)",
  },
  actionChipPrimary: {
    backgroundColor: "#22d3ee",
    borderColor: "rgba(34, 211, 238, 0.5)",
  },
  actionChipText: { color: "#cbd5e1", fontSize: 13, fontWeight: "900" },
  actionChipTextPrimary: { color: "#07131f" },
  section: { backgroundColor: '#07111f', padding: 15, borderRadius: 22, marginBottom: 15, borderWidth: 1, borderColor: 'rgba(103, 232, 249, 0.16)' },
  sectionTitle: { color: '#67e8f9', fontSize: 13, fontWeight: '900', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.7 },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: 'rgba(148, 163, 184, 0.12)' },
  label: { color: '#93a4bd', fontSize: 14 },
  value: { color: '#e5ecff', fontSize: 14, fontWeight: '900', flexShrink: 1, textAlign: 'right' },
  settingDescription: { color: '#64748b', fontSize: 12, marginTop: 8, marginBottom: 4 },
  buttonRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  adjustButton: { width: 44, height: 44, borderRadius: 999, backgroundColor: 'rgba(20, 184, 166, 0.26)', borderWidth: 1, borderColor: 'rgba(45, 212, 191, 0.46)', alignItems: 'center', justifyContent: 'center' },
  adjustButtonText: { color: '#ccfbf1', fontSize: 20, fontWeight: '900' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10, marginBottom: 6 },
  chip: { paddingVertical: 8, paddingHorizontal: 10, borderRadius: 999, backgroundColor: 'rgba(15, 23, 42, 0.78)', borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.16)' },
  chipActive: { backgroundColor: 'rgba(20, 184, 166, 0.26)', borderColor: 'rgba(45, 212, 191, 0.46)' },
  chipText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  chipTextActive: { color: '#ccfbf1' },
  toggle: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(15, 23, 42, 0.78)', borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.16)' },
  toggleActive: { backgroundColor: 'rgba(20, 184, 166, 0.26)', borderColor: 'rgba(45, 212, 191, 0.46)' },
  toggleText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  toggleTextActive: { color: '#ccfbf1' },
  dangerZone: { backgroundColor: '#160b13', padding: 15, borderRadius: 22, marginBottom: 15, borderWidth: 1, borderColor: 'rgba(248, 113, 113, 0.45)' },
  dangerTitle: { color: '#f87171', fontSize: 13, fontWeight: '900', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.7 },
  button: { backgroundColor: '#dc2626', padding: 13, borderRadius: 999, alignItems: 'center', marginTop: 10 },
  buttonPressed: { transform: [{ scale: 0.98 }] },
  buttonText: { color: '#fff', fontWeight: '900', fontSize: 14 },
});