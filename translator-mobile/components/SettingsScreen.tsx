import { View, Text, StyleSheet, ScrollView, Pressable, TextInput } from "react-native";
import React, { useEffect, useState, ReactNode } from "react";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import NeoBrandMark from "./NeoBrandMark";
import VolumeControl from "./VolumeControl";
import SpeedControl from "./SpeedControl";
import { MOBILE_BUILD_ID } from "../constants/mobileBuild";
import { bridgeServerStatusMessages } from "../constants/productVoice";
import { AUDIO_QUALITIES } from "../constants/audioQuality";
import PerformanceDashboard from "./PerformanceDashboard";

function SectionIcon({ name, danger = false }: { name: React.ComponentProps<typeof Ionicons>["name"]; danger?: boolean }) {
  return (
    <View style={[styles.sectionIconRing, danger && styles.sectionIconRingDanger]}>
      <Ionicons name={name} size={14} color={danger ? "#fca5a5" : "#67e8f9"} />
    </View>
  );
}

function SettingsSection({
  title,
  icon,
  danger = false,
  children,
}: {
  title: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <View style={[styles.section, danger && styles.dangerZone]}>
      <LinearGradient
        colors={danger ? ["rgba(248, 113, 113, 0.28)", "transparent"] : ["rgba(103, 232, 249, 0.28)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.sectionShine}
        pointerEvents="none"
      />
      <View style={styles.sectionHead}>
        <SectionIcon name={icon} danger={danger} />
        <Text style={danger ? styles.dangerTitle : styles.sectionTitle}>{title}</Text>
      </View>
      {children}
    </View>
  );
}

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
  backendReachable?: boolean | null;
  isCheckingBackend?: boolean;
  sourceLanguage: string;
  setSourceLanguage: (lang: string) => void;
  targetLanguage: string;
  setTargetLanguage: (lang: string) => void;
  onClearData: () => void;
  volume?: number;
  setVolume?: (vol: number) => void;
  playbackSpeed?: number;
  setPlaybackSpeed?: (speed: number) => void;
  audioQuality?: keyof typeof AUDIO_QUALITIES;
  setAudioQuality?: (quality: keyof typeof AUDIO_QUALITIES) => void;
  audioEnvironment?: string;
  setAudioEnvironment?: (environment: string) => void;
  debugMode?: boolean;
  setDebugMode?: (enabled: boolean) => void;
  barrierMode?: boolean;
  setBarrierMode?: (enabled: boolean) => void;
  showRecentUrls?: boolean;
  setShowRecentUrls?: (visible: boolean) => void;
  batchRecording?: boolean;
  isBatchUploading?: boolean;
  batchUploadProgress?: number;
  batchRecordDisabled?: boolean;
  onStartBatchRecord?: () => void | Promise<void>;
  onStopBatchRecord?: () => void | Promise<void>;
  onCancelBatchUpload?: () => void;
  lowBandwidthMode?: boolean;
  setLowBandwidthMode?: (enabled: boolean) => void;
  diagnostics?: Record<string, any> | null;
  diagnosticsStatus?: string;
  onRefreshDiagnostics?: () => void | Promise<void>;
  latencyMetrics?: {
    sttLatency?: number;
    translationLatency?: number;
    ttsLatency?: number;
    endToEndLatency?: number;
    first_audio?: number;
  };
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
  { code: "nl", name: "Dutch", native: "Nederlands", flag: "🇳🇱" },
  { code: "hi", name: "Hindi", native: "हिन्दी", flag: "🇮🇳" },
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
  audioEnvironment = "auto",
  setAudioEnvironment,
  debugMode = false,
  setDebugMode,
  barrierMode = true,
  setBarrierMode,
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
  showRecentUrls = false,
  setShowRecentUrls,
  backendReachable = null,
  isCheckingBackend = false,
  batchRecording = false,
  isBatchUploading = false,
  batchUploadProgress = 0,
  batchRecordDisabled = false,
  onStartBatchRecord,
  onStopBatchRecord,
  onCancelBatchUpload,
  lowBandwidthMode = false,
  setLowBandwidthMode,
  diagnostics = null,
  diagnosticsStatus = "checking",
  onRefreshDiagnostics,
  latencyMetrics = {},
}: SettingsScreenProps) {
  const [localVolume, setLocalVolume] = useState(volume);
  const [localSpeed, setLocalSpeed] = useState(playbackSpeed);
  const [localUrl, setLocalUrl] = useState(wsUrl);
  const [confirmClear, setConfirmClear] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const bridgeSrv = bridgeServerStatusMessages();

  useEffect(() => {
    setLocalUrl(wsUrl);
  }, [wsUrl]);

  useEffect(() => {
    setLocalVolume(volume);
  }, [volume]);

  useEffect(() => {
    setLocalSpeed(playbackSpeed);
  }, [playbackSpeed]);

  const handleVolumeChange = (value: number) => {
    setLocalVolume(value);
    setVolume?.(value);
  };

  const handleSpeedChange = (value: number) => {
    setLocalSpeed(value);
    setPlaybackSpeed?.(value);
  };

  return (
    <ScrollView style={styles.container}>
      <LinearGradient
        colors={["rgba(103, 232, 249, 0.35)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.headerShine}
        pointerEvents="none"
      />
      <View style={styles.headerRow}>
        <View style={styles.headerTitleWrap}>
          <NeoBrandMark subline="SETTINGS" compact />
          <Text style={styles.title}>Preferences</Text>
          <Text style={styles.subtitle}>Languages, audio, and server connection.</Text>
        </View>
        {onClose ? (
          <Pressable
            onPress={onClose}
            style={({ pressed }) => [styles.closeBtn, pressed && styles.closeBtnPressed]}
            accessibilityRole="button"
            accessibilityLabel="Close settings"
          >
            <Ionicons name="close" size={22} color="#e2e8f0" />
          </Pressable>
        ) : null}
      </View>

      <SettingsSection title="Bridge server" icon="server-outline">
        <Text style={styles.settingDescription}>Railway HTTPS URL or local IP — where Anai links your conversation.</Text>
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
          style={[styles.urlInput, focusedField === "url" && styles.urlInputFocused]}
          onFocus={() => setFocusedField("url")}
          onBlur={() => setFocusedField((f) => (f === "url" ? null : f))}
          accessibilityLabel="Bridge server URL"
        />
        {recentUrls.length > 0 ? (
          <>
            <Pressable
              style={({ pressed }) => [styles.recentToggle, pressed && styles.recentTogglePressed]}
              onPress={() => setShowRecentUrls?.(!showRecentUrls)}
              accessibilityRole="button"
              accessibilityLabel={showRecentUrls ? "Hide recent bridge servers" : "Show recent bridge servers"}
            >
              <Ionicons name={showRecentUrls ? "chevron-up" : "time-outline"} size={14} color="#94a3b8" />
              <Text style={styles.recentToggleText}>
                {showRecentUrls ? "Hide recent servers" : `Recent bridge servers (${recentUrls.length})`}
              </Text>
            </Pressable>
            {showRecentUrls ? (
              <View style={styles.chipRow}>
                {recentUrls.map((url) => (
                  <Pressable
                    key={url}
                    style={[styles.chip, localUrl === url && styles.chipActive]}
                    onPress={() => {
                      setLocalUrl(url);
                      setWsUrl(url);
                      onSaveUrl?.(url);
                    }}
                  >
                    <Text numberOfLines={1} style={[styles.chipText, localUrl === url && styles.chipTextActive]}>
                      {url.replace(/^https?:\/\//, "").slice(0, 28)}
                    </Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </>
        ) : null}
        {isCheckingBackend ? (
          <View style={styles.connectionRow}>
            <Ionicons name="sync-outline" size={14} color="#94a3b8" />
            <Text style={styles.connectionStatus}>{bridgeSrv.checking}</Text>
          </View>
        ) : backendReachable === true ? (
          <View style={styles.connectionRow}>
            <Ionicons name="checkmark-circle" size={14} color="#34d399" />
            <Text style={[styles.connectionStatus, styles.connectionOk]}>{bridgeSrv.reachable}</Text>
          </View>
        ) : backendReachable === false ? (
          <View style={styles.connectionRow}>
            <Ionicons name="close-circle" size={14} color="#f87171" />
            <Text style={[styles.connectionStatus, styles.connectionBad]}>{bridgeSrv.unreachable}</Text>
          </View>
        ) : null}
        <View style={styles.buttonRow}>
          <Pressable
            style={({ pressed }) => [styles.actionChip, pressed && styles.actionChipPressed]}
            onPress={() => onTestConnection?.()}
          >
            <Text style={styles.actionChipText}>{isCheckingBackend ? bridgeSrv.testing : bridgeSrv.testLink}</Text>
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.actionChip, styles.actionChipPrimary, pressed && styles.actionChipPrimaryPressed]}
            onPress={() => onSaveUrl?.(localUrl)}
          >
            <Text style={[styles.actionChipText, styles.actionChipTextPrimary]}>{bridgeSrv.saveRelink}</Text>
          </Pressable>
        </View>
      </SettingsSection>

      <SettingsSection title="Account" icon="person-circle-outline">
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
              style={[styles.urlInput, focusedField === "user" && styles.urlInputFocused]}
              onFocus={() => setFocusedField("user")}
              onBlur={() => setFocusedField((f) => (f === "user" ? null : f))}
              accessibilityLabel="Username"
            />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor="#64748b"
              secureTextEntry
              style={[styles.urlInput, focusedField === "pass" && styles.urlInputFocused]}
              onFocus={() => setFocusedField("pass")}
              onBlur={() => setFocusedField((f) => (f === "pass" ? null : f))}
              accessibilityLabel="Password"
            />
            <Pressable style={[styles.actionChip, styles.actionChipPrimary]} onPress={() => onLogin?.()}>
              <Text style={[styles.actionChipText, styles.actionChipTextPrimary]}>Sign in</Text>
            </Pressable>
          </>
        )}
      </SettingsSection>

      {setBarrierMode ? (
        <SettingsSection title="Conversation bridge" icon="people-outline">
          <View style={styles.settingRow}>
            <Text style={styles.label}>Together mode</Text>
            <Pressable
              style={[styles.toggle, barrierMode && styles.toggleActive]}
              onPress={() => setBarrierMode(!barrierMode)}
            >
              <Text style={[styles.toggleText, barrierMode && styles.toggleTextActive]}>
                {barrierMode ? "ON" : "OFF"}
              </Text>
            </Pressable>
          </View>
          <Text style={styles.settingDescription}>
            When on, each person stays in their language — Anai bridges meaning to the other side.
          </Text>
        </SettingsSection>
      ) : null}
      
      <SettingsSection title="Audio Settings" icon="volume-high-outline">
        <View style={styles.settingRow}>
          <Text style={styles.label}>Volume</Text>
          <Text style={styles.value}>{Math.round(localVolume * 100)}%</Text>
        </View>
        <View style={styles.settingsVolumeWrap}>
          <VolumeControl volume={localVolume} onVolumeChange={handleVolumeChange} wide />
        </View>

        <View style={styles.settingRow}>
          <Text style={styles.label}>TTS Speed</Text>
          <Text style={styles.value}>{localSpeed.toFixed(1)}x</Text>
        </View>
        <View style={styles.settingsVolumeWrap}>
          <SpeedControl speed={localSpeed} onSpeedChange={handleSpeedChange} wide />
        </View>

        {(
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
                  onPress={() => setAudioQuality?.(key as keyof typeof AUDIO_QUALITIES)}
                >
                  <Text style={[styles.chipText, audioQuality === key && styles.chipTextActive]}>
                    {quality.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Text style={styles.settingDescription}>{AUDIO_QUALITIES[audioQuality]?.description}</Text>
            <View style={styles.settingRow}>
              <Text style={styles.label}>Room noise</Text>
              <Text style={styles.value}>{audioEnvironment}</Text>
            </View>
            <View style={styles.chipRow}>
              {["auto", "quiet", "office", "restaurant", "street", "crowded"].map((env) => (
                <Pressable
                  key={env}
                  style={[styles.chip, audioEnvironment === env && styles.chipActive]}
                  onPress={() => setAudioEnvironment?.(env)}
                >
                  <Text style={[styles.chipText, audioEnvironment === env && styles.chipTextActive]}>
                    {env}
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        )}
      </SettingsSection>

      {onStartBatchRecord ? (
        <SettingsSection title="Clip bridge" icon="mic-outline">
          <Text style={styles.settingDescription}>
            Record a short clip and bridge it in one shot. Pause the live bridge first.
          </Text>
          {isBatchUploading ? (
            <>
              <View style={styles.settingRow}>
                <Text style={styles.label}>Uploading clip</Text>
                <Text style={styles.value}>{Math.round(batchUploadProgress)}%</Text>
              </View>
              <Pressable style={styles.actionChip} onPress={() => onCancelBatchUpload?.()}>
                <Text style={styles.actionChipText}>Cancel upload</Text>
              </Pressable>
            </>
          ) : (
            <Pressable
              style={({ pressed }) => [
                styles.actionChip,
                batchRecording ? styles.actionChipDanger : styles.actionChipPrimary,
                pressed && (batchRecording ? styles.actionChipDangerPressed : styles.actionChipPrimaryPressed),
                batchRecordDisabled && styles.actionChipDisabled,
              ]}
              disabled={batchRecordDisabled && !batchRecording}
              onPress={() => (batchRecording ? onStopBatchRecord?.() : onStartBatchRecord?.())}
            >
              <Text style={[styles.actionChipText, !batchRecording && styles.actionChipTextPrimary]}>
                {batchRecording ? "Stop & bridge clip" : batchRecordDisabled ? "Bridge live" : "Record clip"}
              </Text>
            </Pressable>
          )}
        </SettingsSection>
      ) : null}
      
      <SettingsSection title="Bridge languages" icon="language-outline">
        <View style={styles.settingRow}>
          <Text style={styles.label}>You speak</Text>
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
          <Text style={styles.label}>{barrierMode ? "They hear" : "Bridged out"}</Text>
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
      </SettingsSection>

      <SettingsSection title="Bridge link quality" icon="cellular-outline">
        <View style={styles.settingRow}>
          <Text style={styles.label}>Low bandwidth mode</Text>
          <Pressable
            style={[styles.toggle, lowBandwidthMode && styles.toggleActive]}
            onPress={() => setLowBandwidthMode?.(!lowBandwidthMode)}
          >
            <Text style={[styles.toggleText, lowBandwidthMode && styles.toggleTextActive]}>
              {lowBandwidthMode ? "ON" : "OFF"}
            </Text>
          </Pressable>
        </View>
        <Text style={styles.settingDescription}>
          Skips partial live voice on slow Wi‑Fi. Final bridged meaning still speaks when confident.
        </Text>
      </SettingsSection>

      <SettingsSection title="Backend health" icon="pulse-outline">
        <View style={styles.settingRow}>
          <Text style={styles.label}>Diagnostics</Text>
          <Text style={styles.value}>
            {diagnosticsStatus === "online" ? "Online" : diagnosticsStatus === "checking" ? "Checking…" : "Offline"}
          </Text>
        </View>
        {diagnostics?.cip?.mode ? (
          <View style={styles.settingRow}>
            <Text style={styles.label}>CIP mode</Text>
            <Text style={styles.value}>{String(diagnostics.cip.mode)}</Text>
          </View>
        ) : null}
        {diagnostics?.stt_provider ? (
          <View style={styles.settingRow}>
            <Text style={styles.label}>STT provider</Text>
            <Text style={styles.value}>{String(diagnostics.stt_provider)}</Text>
          </View>
        ) : null}
        {diagnostics?.tts_neural ? (
          <View style={styles.settingRow}>
            <Text style={styles.label}>Neural voice</Text>
            <Text style={styles.value}>{diagnostics.tts_neural.ready ? "Ready" : "Warming up"}</Text>
          </View>
        ) : null}
        <Pressable style={styles.actionChip} onPress={() => onRefreshDiagnostics?.()}>
          <Text style={styles.actionChipText}>Refresh diagnostics</Text>
        </Pressable>
      </SettingsSection>

      {setDebugMode && (
        <SettingsSection title="Developer Options" icon="code-slash-outline">
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
          {debugMode ? (
            <PerformanceDashboard
              diagnostics={diagnostics}
              diagnosticsStatus={diagnosticsStatus}
              latencyMetrics={latencyMetrics}
              onRefresh={onRefreshDiagnostics}
            />
          ) : null}
        </SettingsSection>
      )}
      
      <SettingsSection title="About" icon="information-circle-outline">
        <View style={styles.settingRow}>
          <Text style={styles.label}>Build</Text>
          <Text style={styles.value}>{MOBILE_BUILD_ID}</Text>
        </View>
        <View style={styles.settingRow}>
          <Text style={styles.label}>App</Text>
          <Text style={styles.value}>Anai</Text>
        </View>
        <Text style={styles.settingDescription}>
          Session glossary terms from your PC settings are applied automatically while bridging.
        </Text>
      </SettingsSection>
      
      <SettingsSection title="Danger Zone" icon="warning-outline" danger>
        <Pressable
          style={({ pressed }) => [styles.button, pressed && styles.buttonPressed, confirmClear && styles.buttonDanger]}
          onPress={() => {
            if (!confirmClear) {
              setConfirmClear(true);
              return;
            }
            setConfirmClear(false);
            onClearData?.();
          }}
        >
          <Text style={styles.buttonText}>{confirmClear ? "Tap again to confirm wipe" : "Clear All Stored Data"}</Text>
        </Pressable>
      </SettingsSection>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: "#03050a" },
  headerShine: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    zIndex: 1,
  },
  headerRow: { flexDirection: "row", alignItems: "flex-start", gap: 12, marginBottom: 8 },
  headerTitleWrap: { flex: 1, minWidth: 0 },
  closeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.2)",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 4,
  },
  closeBtnPressed: {
    backgroundColor: "#1e293b",
    borderColor: "rgba(103, 232, 249, 0.28)",
  },
  connectionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 10,
  },
  title: { fontSize: 28, fontWeight: "900", color: '#f8fafc', marginBottom: 4 },
  titleAccent: { color: '#67e8f9' },
  subtitle: { color: '#94a3b8', fontSize: 13, marginBottom: 10, lineHeight: 18 },
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
  urlInputFocused: {
    borderColor: "rgba(103, 232, 249, 0.55)",
    backgroundColor: "#0f172a",
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 10,
    elevation: 3,
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
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 4,
  },
  actionChipPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.98 }],
  },
  actionChipPrimaryPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.98 }],
  },
  actionChipText: { color: "#cbd5e1", fontSize: 13, fontWeight: "900" },
  actionChipTextPrimary: { color: "#07131f" },
  section: {
    backgroundColor: '#07111f',
    padding: 15,
    borderRadius: 22,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.16)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.22,
    shadowRadius: 16,
    elevation: 5,
    overflow: 'hidden',
    position: 'relative',
  },
  sectionShine: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 2,
    zIndex: 1,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  sectionIconRing: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.28)',
  },
  sectionIconRingDanger: {
    backgroundColor: 'rgba(248, 113, 113, 0.1)',
    borderColor: 'rgba(248, 113, 113, 0.28)',
  },
  sectionTitle: { color: '#67e8f9', fontSize: 13, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.7 },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: 'rgba(148, 163, 184, 0.12)' },
  label: { color: '#93a4bd', fontSize: 14 },
  value: { color: '#e5ecff', fontSize: 14, fontWeight: '900', flexShrink: 1, textAlign: 'right' },
  settingDescription: { color: '#64748b', fontSize: 12, marginTop: 8, marginBottom: 4 },
  buttonRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  settingsVolumeWrap: { marginTop: 4, marginBottom: 8, width: '100%' },
  adjustButton: {
    width: 44,
    height: 44,
    borderRadius: 999,
    backgroundColor: 'rgba(20, 184, 166, 0.26)',
    borderWidth: 1,
    borderColor: 'rgba(45, 212, 191, 0.46)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#2dd4bf',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
    elevation: 2,
  },
  adjustButtonPressed: {
    transform: [{ scale: 0.94 }],
    opacity: 0.9,
  },
  adjustButtonText: { color: '#ccfbf1', fontSize: 20, fontWeight: '900' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10, marginBottom: 6 },
  chip: { paddingVertical: 8, paddingHorizontal: 10, borderRadius: 999, backgroundColor: 'rgba(15, 23, 42, 0.78)', borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.16)' },
  chipActive: {
    backgroundColor: 'rgba(20, 184, 166, 0.26)',
    borderColor: 'rgba(45, 212, 191, 0.46)',
    shadowColor: '#2dd4bf',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
    elevation: 2,
  },
  chipText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  chipTextActive: { color: '#ccfbf1' },
  toggle: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(15, 23, 42, 0.78)', borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.16)' },
  toggleActive: { backgroundColor: 'rgba(20, 184, 166, 0.26)', borderColor: 'rgba(45, 212, 191, 0.46)' },
  toggleText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  toggleTextActive: { color: '#ccfbf1' },
  dangerZone: {
    backgroundColor: '#160b13',
    borderColor: 'rgba(248, 113, 113, 0.45)',
    shadowColor: '#f87171',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 3,
  },
  dangerTitle: { color: '#f87171', fontSize: 13, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.7 },
  button: { backgroundColor: '#dc2626', padding: 13, borderRadius: 999, alignItems: 'center', marginTop: 10 },
  buttonDanger: { backgroundColor: '#991b1b' },
  buttonPressed: { transform: [{ scale: 0.98 }] },
  buttonText: { color: '#fff', fontWeight: '900', fontSize: 14 },
  connectionStatus: { fontSize: 13, fontWeight: '800', color: '#94a3b8' },
  connectionOk: { color: '#6ee7b7' },
  connectionBad: { color: '#fca5a5' },
  recentToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingVertical: 6,
  },
  recentTogglePressed: { opacity: 0.8 },
  recentToggleText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  actionChipDanger: {
    backgroundColor: 'rgba(248, 113, 113, 0.18)',
    borderColor: 'rgba(248, 113, 113, 0.42)',
  },
  actionChipDangerPressed: { opacity: 0.88, transform: [{ scale: 0.98 }] },
  actionChipDisabled: { opacity: 0.45 },
});
