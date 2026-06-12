import { GestureHandlerRootView } from "react-native-gesture-handler";
import "react-native-reanimated";
import { registerRootComponent } from "expo";
import { Component, useEffect, useState } from "react";
import { DevSettings, ScrollView, Text, View, Pressable, ActivityIndicator, Linking } from "react-native";
import * as Clipboard from "expo-clipboard";
import { LinearGradient } from "expo-linear-gradient";
import NeoBrandMark from "./components/NeoBrandMark";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import App from "./App";
import { MOBILE_BUILD_ID, isRemoteBuildNewer } from "./constants/mobileBuild";
import { shouldAutoReloadForMetro } from "./utils/metroBuildReload";
import { cancelDiscovery, cancelLogin } from "./hooks/useMobileAuth";
import {
  deriveApiUrlFromExpo,
  deriveExpoUrlFromInfo,
  deriveLanHostFromExpo,
  fetchMobileConnectInfo,
  isOffLanBackendUrl,
  probeMetroBuildId,
  probeMetroBundleReady,
  probeMetroBundleSignature,
  resolveServerUrl,
  waitForBackendReady,
} from "./utils/discoverServer";

const RECOVERABLE_STARTUP =
  /setIsPlayingTts|doesn't exist|has not been registered|main was not registered|Property '.*' doesn't exist|bundle warming|bundle not ready/i;

class RootErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, autoReloading: false, retried: false };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error("Anai startup error:", error);
    const message = String(error?.message || error || "");
    if (!this.state.retried && RECOVERABLE_STARTUP.test(message)) {
      this.setState({ autoReloading: true, retried: true });
      setTimeout(() => {
        try {
          DevSettings.reload();
        } catch {
          this.setState({ autoReloading: false });
        }
      }, 1200);
    }
  }

  handleRetry = () => {
    this.setState({ error: null });
    try {
      DevSettings.reload();
    } catch {
      // DevSettings may be unavailable outside Expo Go.
    }
  };

  render() {
    if (this.state.autoReloading) {
      return (
        <View style={{ flex: 1, backgroundColor: "#03050a", padding: 24, justifyContent: "center", alignItems: "center" }}>
          <ActivityIndicator color="#22d3ee" size="large" />
          <Text style={{ color: "#94a3b8", marginTop: 16, fontSize: 15, fontWeight: "600", textAlign: "center" }}>
            Reloading fresh bundle ({MOBILE_BUILD_ID})…
          </Text>
        </View>
      );
    }
    if (this.state.error) {
      const message = String(this.state.error?.message || this.state.error || "Unknown startup error");
      return (
        <View style={{ flex: 1, backgroundColor: "#03050a", padding: 24, justifyContent: "center" }}>
          <Text style={{ color: "#f87171", fontSize: 18, fontWeight: "700", marginBottom: 8 }}>
            Anai could not start
          </Text>
          <Text style={{ color: "#94a3b8", fontSize: 14, lineHeight: 20, marginBottom: 8 }}>
            Wait for Metro to finish bundling on your PC, then tap Try again. If this keeps happening, force-close Expo Go and reopen the project URL.
          </Text>
          <Text style={{ color: "#64748b", fontSize: 12, marginBottom: 16 }}>
            Build on phone: {MOBILE_BUILD_ID}
          </Text>
          <ScrollView style={{ maxHeight: 180, marginBottom: 20 }}>
            <Text style={{ color: "#e2e8f0", fontSize: 13, lineHeight: 18 }} selectable>
              {message}
            </Text>
          </ScrollView>
          <Pressable
            onPress={this.handleRetry}
            style={{
              backgroundColor: "#22d3ee",
              borderRadius: 12,
              paddingVertical: 14,
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            <Text style={{ color: "#07131f", fontSize: 16, fontWeight: "700" }}>Try again</Text>
          </Pressable>
          {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null) ? (
            <Pressable
              onPress={() => Linking.openURL(deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null)).catch(() => {})}
              style={{
                backgroundColor: "#111827",
                borderRadius: 12,
                paddingVertical: 12,
                alignItems: "center",
                marginBottom: 8,
                borderWidth: 1,
                borderColor: "#334155",
              }}
            >
              <Text style={{ color: "#e2e8f0", fontSize: 15, fontWeight: "800" }}>Open in Expo Go</Text>
            </Pressable>
          ) : null}
          <Pressable onPress={() => copyExpoUrl()} style={{ paddingVertical: 8, marginBottom: 8 }}>
            <Text style={{ color: "#94a3b8", fontSize: 13, fontWeight: "700", textAlign: "center" }}>Copy Expo URL</Text>
          </Pressable>
          <Text style={{ color: "#64748b", fontSize: 12, lineHeight: 18, textAlign: "center" }}>
            Still broken? Force-close Expo Go completely, reopen{" "}
            {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null) || "the Expo URL from your PC"}, and wait for the full bundle.
          </Text>
        </View>
      );
    }
    return this.props.children;
  }
}

function formatBundleMb(bytes) {
  const n = Number(bytes) || 0;
  if (n <= 0) return "";
  return `${(n / 1_000_000).toFixed(1)} MB`;
}

async function copyExpoUrl(label) {
  const expoUrl = deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null);
  if (!expoUrl) return false;
  try {
    await Clipboard.setStringAsync(expoUrl);
    return true;
  } catch {
    return false;
  }
}

function BootstrapGate({ children }) {
  const [gate, setGate] = useState({ phase: "checking" });
  const [bootKey, setBootKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const bootstrapWithTimeout = (promise, timeoutMs = 20000) => {
      let timeoutId;
      return Promise.race([
        promise.finally(() => {
          if (timeoutId) clearTimeout(timeoutId);
        }),
        new Promise((_, reject) => {
          timeoutId = setTimeout(
            () => reject(new Error("Bootstrap discovery timed out")),
            timeoutMs,
          );
        }),
      ]);
    };
    (async () => {
      try {
        const bootstrapFallback = deriveApiUrlFromExpo();
        let resolved = await bootstrapWithTimeout(
          resolveServerUrl(bootstrapFallback, { shouldAbort: () => cancelled }),
        );
        if (!resolved.healthy) {
          const tunnelResolved = await bootstrapWithTimeout(
            resolveServerUrl(bootstrapFallback, {
              preferOffLan: true,
              shouldAbort: () => cancelled,
            }),
            15000,
          );
          if (tunnelResolved.healthy) {
            resolved = tunnelResolved;
          }
        }
        if (!resolved.healthy && resolved.apiUrl) {
          const warmed = await waitForBackendReady(resolved.apiUrl, {
            maxAttempts: 12,
            delayMs: 1500,
            shouldAbort: () => cancelled,
          });
          if (warmed) {
            resolved = { ...resolved, healthy: true };
          }
        }
        const info = resolved.mobileInfo || (resolved.apiUrl
          ? await fetchMobileConnectInfo(resolved.apiUrl, { shouldAbort: () => cancelled })
          : null);
        const preferredExpoPort = info?.expo_port || "";
        const metroProbe = await probeMetroBuildId(resolved.hostname, preferredExpoPort, {
          shouldAbort: () => cancelled,
        });
        if (cancelled) return;
        if (!resolved.healthy && resolved.apiUrl && !cancelled) {
          const warmedLate = await waitForBackendReady(resolved.apiUrl, {
            maxAttempts: 4,
            delayMs: 1000,
            shouldAbort: () => cancelled,
          });
          if (cancelled) return;
          if (warmedLate) {
            resolved = { ...resolved, healthy: true };
          }
        }
        if (await shouldAutoReloadForMetro(metroProbe?.buildId, MOBILE_BUILD_ID)) {
          try {
            DevSettings.reload();
            return;
          } catch {
            // Fall through to setup gate.
          }
        }

        const needsMetro = !Boolean(resolved.apiUrl && isOffLanBackendUrl(resolved.apiUrl));
        if (needsMetro && metroProbe?.metroBase) {
          if (!cancelled) {
            setGate({ phase: "bundling", buildId: MOBILE_BUILD_ID, bundleBytes: 0 });
          }
          let bundleReady = await probeMetroBundleReady(resolved.hostname, preferredExpoPort, {
            maxAttempts: 40,
            delayMs: 2000,
            shouldAbort: () => cancelled,
            onProgress: ({ bytes, ready }) => {
              if (cancelled) return;
              setGate((current) => ({
                ...current,
                phase: "bundling",
                buildId: MOBILE_BUILD_ID,
                bundleBytes: bytes || current.bundleBytes || 0,
                bundleReady: ready,
              }));
            },
          });
          if (cancelled) return;
          if (bundleReady) {
            bundleReady = await probeMetroBundleSignature(resolved.hostname, preferredExpoPort, {
              shouldAbort: () => cancelled,
            });
          }
          if (cancelled) return;
          if (!bundleReady && !cancelled) {
            setGate({
              phase: "setup",
              setupUrl: resolved.apiUrl ? `${resolved.apiUrl}/mobile` : "",
              expoUrl: deriveExpoUrlFromInfo(resolved.hostname, info),
              webAppUrl: String(info?.web_app_url || (resolved.apiUrl ? `${resolved.apiUrl}/mobile/app` : "")).trim(),
              webAppHttpsUrl: String(
                info?.web_app_https_url
                || (info?.backend_https_url ? `${String(info.backend_https_url).replace(/\/+$/, "")}/mobile/app` : ""),
              ).trim(),
              apiUrl: resolved.apiUrl || deriveApiUrlFromExpo(),
              buildId: MOBILE_BUILD_ID,
              remoteBuildId: metroProbe?.buildId || "",
              setupReason: "bundling",
            });
            return;
          }
        }

        const setupUrl = resolved.apiUrl ? `${resolved.apiUrl}/mobile` : "";
        const expoUrl = deriveExpoUrlFromInfo(resolved.hostname, info);
        const webAppUrl = String(info?.web_app_url || (resolved.apiUrl ? `${resolved.apiUrl}/mobile/app` : "")).trim();
        const webAppHttpsUrl = String(
          info?.web_app_https_url
          || (info?.backend_https_url ? `${String(info.backend_https_url).replace(/\/+$/, "")}/mobile/app` : ""),
        ).trim();
        const buildMismatch = isRemoteBuildNewer(metroProbe?.buildId, MOBILE_BUILD_ID);
        const canReachMetro = Boolean(metroProbe?.buildId);
        const metroUnreachable = needsMetro && !canReachMetro;
        const needsSetup = buildMismatch || metroUnreachable;
        const setupReason = buildMismatch
          ? "build"
          : metroUnreachable
          ? "metro"
          : !resolved.healthy
          ? "warming"
          : "unknown";

        if (!cancelled) {
          if (needsSetup) {
            setGate({
              phase: "setup",
              setupUrl,
              expoUrl,
              webAppUrl,
              webAppHttpsUrl,
              apiUrl: (resolved.healthy ? resolved.apiUrl : "")
                || String(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "").trim().replace(/\/+$/, "")
                || deriveApiUrlFromExpo(),
              buildId: MOBILE_BUILD_ID,
              remoteBuildId: metroProbe?.buildId || info?.build_id || "",
              setupReason,
            });
          } else {
            setGate({
              phase: "ready",
              apiUrl: resolved.apiUrl || deriveApiUrlFromExpo(),
            });
          }
        }
      } catch (error) {
        console.error("Bootstrap gate failed:", error);
        if (!cancelled) {
          const tunnelApi = String(process.env.EXPO_PUBLIC_TUNNEL_API_URL || "").trim().replace(/\/+$/, "");
          const fallbackApi = deriveApiUrlFromExpo() || tunnelApi;
          const expoUrl = deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null);
          const lanHost = deriveLanHostFromExpo();
          const httpsFallback = lanHost ? `https://${lanHost}:8443/mobile/app` : "";
          setGate({
            phase: "setup",
            setupUrl: fallbackApi ? `${fallbackApi}/mobile` : "",
            expoUrl,
            webAppUrl: fallbackApi ? `${fallbackApi}/mobile/app` : "",
            webAppHttpsUrl: httpsFallback,
            apiUrl: fallbackApi,
            buildId: MOBILE_BUILD_ID,
            remoteBuildId: "",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
      cancelLogin();
      cancelDiscovery();
    };
  }, [bootKey]);

  if (gate.phase === "checking") {
    return (
      <LinearGradient colors={["#03050a", "#071018", "#0a1628", "#03050a"]} style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
        <NeoBrandMark compact />
        <ActivityIndicator color="#22d3ee" size="large" style={{ marginTop: 18 }} />
        <Text style={{ color: "#94a3b8", marginTop: 14, fontSize: 14, fontWeight: "600" }}>
          Finding your bridge server…
        </Text>
        <Text style={{ color: "#64748b", marginTop: 8, fontSize: 12 }}>
          Build {MOBILE_BUILD_ID}
        </Text>
        {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null) ? (
          <Text selectable style={{ color: "#475569", marginTop: 10, fontSize: 11, textAlign: "center" }}>
            {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null)}
          </Text>
        ) : null}
      </LinearGradient>
    );
  }

  if (gate.phase === "bundling") {
    return (
      <LinearGradient colors={["#03050a", "#071018", "#0a1628", "#03050a"]} style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 24 }}>
        <NeoBrandMark compact />
        <ActivityIndicator color="#22d3ee" size="large" style={{ marginTop: 18 }} />
        <Text style={{ color: "#94a3b8", marginTop: 14, fontSize: 14, fontWeight: "600", textAlign: "center" }}>
          Waiting for Metro to finish bundling on your PC…
        </Text>
        <Text style={{ color: "#64748b", marginTop: 8, fontSize: 12, textAlign: "center" }}>
          Build {gate.buildId || MOBILE_BUILD_ID} · usually 30–60s after Metro restart
        </Text>
        {gate.bundleBytes > 0 ? (
          <Text style={{ color: "#22d3ee", marginTop: 8, fontSize: 12, fontWeight: "700" }}>
            PC bundle: {formatBundleMb(gate.bundleBytes)}{gate.bundleReady ? " · ready" : " · warming"}
          </Text>
        ) : null}
        {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null) ? (
          <Text selectable style={{ color: "#475569", marginTop: 10, fontSize: 11, textAlign: "center" }}>
            {deriveExpoUrlFromInfo(deriveLanHostFromExpo(), null)}
          </Text>
        ) : null}
        <Pressable
          onPress={() => copyExpoUrl()}
          style={{ marginTop: 12, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: "#334155" }}
        >
          <Text style={{ color: "#94a3b8", fontWeight: "700", fontSize: 13 }}>Copy Expo URL</Text>
        </Pressable>
        <Pressable
          onPress={() => {
            try {
              DevSettings.reload();
            } catch {
              setBootKey((key) => key + 1);
              setGate({ phase: "checking" });
            }
          }}
          style={{ marginTop: 10, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 12, borderWidth: 1, borderColor: "#334155" }}
        >
          <Text style={{ color: "#67e8f9", fontWeight: "800", fontSize: 14 }}>Reload when PC shows ~1280 modules</Text>
        </Pressable>
      </LinearGradient>
    );
  }

  if (gate.phase === "setup") {
    return (
      <LinearGradient colors={["#03050a", "#071018", "#0a1628", "#03050a"]} style={{ flex: 1, padding: 24, justifyContent: "center" }}>
        <NeoBrandMark subline="UPDATE" compact />
        <Text style={{ color: "#fbbf24", fontSize: 22, fontWeight: "900", marginBottom: 8, marginTop: 12 }}>
          {gate.setupReason === "metro"
            ? "Cannot reach Metro"
            : gate.setupReason === "bundling"
            ? "Metro bundle not ready"
            : "Update required"}
        </Text>
        <Text style={{ color: "#cbd5e1", fontSize: 15, lineHeight: 22, marginBottom: 10 }}>
          {gate.setupReason === "metro"
            ? `Expo Go cannot reach Metro on your PC. Force-close Expo Go, confirm Local Network is ON, then reopen ${gate.expoUrl || "the Expo URL from your PC"}.`
            : gate.setupReason === "bundling"
            ? `Metro on your PC has not finished the full app bundle yet. Wait until the PC terminal shows ~1280 modules bundled, then tap Reload.`
            : `This phone needs build ${gate.buildId}. Force-close Expo Go, reopen the Expo URL from your PC, and wait for the full bundle (~40s).`}
        </Text>
        {gate.remoteBuildId ? (
          <Text style={{ color: "#94a3b8", fontSize: 12, marginBottom: 16 }}>
            Bridge build on PC: {gate.remoteBuildId}
          </Text>
        ) : null}
        {(gate.webAppHttpsUrl || gate.webAppUrl) ? (
          <Pressable
            onPress={() => Linking.openURL(gate.webAppHttpsUrl || gate.webAppUrl).catch(() => {})}
            style={{ backgroundColor: "#22d3ee", borderRadius: 14, paddingVertical: 14, marginBottom: 10 }}
          >
            <Text style={{ textAlign: "center", fontWeight: "900", color: "#07131f", fontSize: 16 }}>
              {gate.webAppHttpsUrl ? "Open Safari bridge (HTTPS · microphone)" : "Open conversation bridge in Safari"}
            </Text>
          </Pressable>
        ) : null}
        {gate.setupUrl ? (
          <Pressable
            onPress={() => Linking.openURL(gate.setupUrl).catch(() => {})}
            style={{
              backgroundColor: "#111827",
              borderRadius: 14,
              paddingVertical: 14,
              marginBottom: 10,
              borderWidth: 1,
              borderColor: "#334155",
            }}
          >
            <Text style={{ textAlign: "center", fontWeight: "800", color: "#e2e8f0", fontSize: 15 }}>
              Open setup page (Safari)
            </Text>
          </Pressable>
        ) : null}
        {gate.expoUrl ? (
          <Pressable
            onPress={() => Linking.openURL(gate.expoUrl).catch(() => {})}
            style={{
              backgroundColor: "#111827",
              borderRadius: 14,
              paddingVertical: 14,
              marginBottom: 10,
              borderWidth: 1,
              borderColor: "#334155",
            }}
          >
            <Text style={{ textAlign: "center", fontWeight: "800", color: "#e2e8f0", fontSize: 15 }}>
              Open in Expo Go
            </Text>
          </Pressable>
        ) : null}
        <Pressable
          onPress={() => {
            setBootKey((key) => key + 1);
            setGate({ phase: "checking" });
          }}
          style={{ backgroundColor: "#22d3ee", borderRadius: 14, paddingVertical: 14, marginBottom: 10 }}
        >
          <Text style={{ textAlign: "center", color: "#07131f", fontWeight: "900", fontSize: 15 }}>
            {gate.setupReason === "bundling" ? "Wait for Metro bundle again" : "Check again"}
          </Text>
        </Pressable>
        <Pressable
          onPress={() => {
            try {
              DevSettings.reload();
            } catch {
              setBootKey((key) => key + 1);
              setGate({ phase: "checking" });
            }
          }}
          style={{ paddingVertical: 14 }}
        >
          <Text style={{ textAlign: "center", color: "#67e8f9", fontWeight: "800", fontSize: 15 }}>Reload app</Text>
        </Pressable>
        {gate.expoUrl ? (
          <Pressable onPress={() => copyExpoUrl()} style={{ paddingVertical: 10 }}>
            <Text style={{ textAlign: "center", color: "#94a3b8", fontWeight: "700", fontSize: 13 }}>Copy {gate.expoUrl}</Text>
          </Pressable>
        ) : null}
        {gate.apiUrl ? (
          <Text selectable style={{ color: "#64748b", fontSize: 11, marginTop: 12, textAlign: "center" }}>
            Server: {gate.apiUrl}
          </Text>
        ) : null}
      </LinearGradient>
    );
  }

  return children(gate.apiUrl || "");
}

function Root() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <RootErrorBoundary>
          <BootstrapGate>
            {(bootstrapApiUrl) => <App bootstrapApiUrl={bootstrapApiUrl} />}
          </BootstrapGate>
        </RootErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

registerRootComponent(Root);
