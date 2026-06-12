const fs = require("fs");
const path = require("path");

describe("quality / certification / brain UI wiring", () => {
  const appSource = fs.readFileSync(path.join(__dirname, "../App.js"), "utf8");

  const qualityComponents = [
    "NativeSpeakerCertBanner",
    "BrainRepairPanel",
    "ClarifyPill",
    "ConfidenceWarningBanner",
    "ReconnectFailureBanner",
    "ConversationQualityStack",
    "ConnectionStrip",
    "LiveStatusPanel",
    "TurnHistoryRail",
    "DuplexConversationPanel",
    "SessionInsightsPanel",
    "DebugInsightsPanel",
  ];

  const qualityHandlers = [
    "applyCertificationFromMessage",
    "applyBrainPayload",
    "shouldSuppressTtsPlayback",
    "applyConfidenceSignals",
    "applySharedSession",
    "runRepairOption",
    "humanCertStep",
    "certificationBanner",
    "shouldBlockTtsForCert",
    "shouldSkipBrainTts",
  ];

  const wsCases = [
    "cip",
    "clarify",
    "cancelled",
    "vad_error",
    "translation",
    "tts_style",
    "stage",
    "session_restored",
    "session_sync",
  ];

  it.each(qualityComponents)("imports and renders %s", (name) => {
    expect(appSource).toMatch(new RegExp(`import\\s+${name}\\s+from`));
    expect(appSource).toMatch(new RegExp(`<${name}[\\s/>]`));
  });

  it.each(qualityHandlers)("defines or uses %s", (name) => {
    expect(appSource).toMatch(new RegExp(name));
  });

  it.each(wsCases)("handles WebSocket type %s", (type) => {
    expect(appSource).toMatch(new RegExp(`case\\s+"${type}"`));
  });

  it("gates TTS on tts_skipped stage", () => {
    expect(appSource).toMatch(/message\.stage === "tts_skipped"/);
    expect(appSource).toMatch(/suppressTurnAudioRef\.current = true/);
  });

  it("wires low bandwidth mode to Settings and TTS suppression", () => {
    expect(appSource).toMatch(/lowBandwidthMode/);
    expect(appSource).toMatch(/LOW_BANDWIDTH_KEY/);
    expect(appSource).toMatch(/lowBandwidthModeRef\.current && message\?\.partial/);
  });

  it("wires reconnect progress and failure banner", () => {
    expect(appSource).toMatch(/onReconnectProgress/);
    expect(appSource).toMatch(/onReconnectFailed/);
    expect(appSource).toMatch(/ReconnectFailureBanner/);
  });

  it("wires performance dashboard through SettingsScreen", () => {
    const settingsSource = fs.readFileSync(
      path.join(__dirname, "../components/SettingsScreen.tsx"),
      "utf8",
    );
    expect(settingsSource).toMatch(/import PerformanceDashboard from/);
    expect(settingsSource).toMatch(/<PerformanceDashboard/);
    expect(appSource).toMatch(/latencyMetrics=/);
    expect(appSource).toMatch(/onRefreshDiagnostics/);
  });
});
