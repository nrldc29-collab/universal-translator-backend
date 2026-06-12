import { View, Text, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

function MetricRow({ label, value }) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value} numberOfLines={2}>{value}</Text>
    </View>
  );
}

function StatusPill({ ok, okLabel = "OK", badLabel = "Issue" }) {
  return (
    <View style={[styles.pill, ok ? styles.pillOk : styles.pillBad]}>
      <Text style={[styles.pillText, ok ? styles.pillTextOk : styles.pillTextBad]}>
        {ok ? okLabel : badLabel}
      </Text>
    </View>
  );
}

/**
 * @param {{
 *   diagnostics?: Record<string, any> | null,
 *   diagnosticsStatus?: string,
 *   latencyMetrics?: Record<string, any>,
 *   onRefresh?: (() => void) | null,
 * }} props
 */
export default function PerformanceDashboard({
  diagnostics = null,
  diagnosticsStatus = "checking",
  latencyMetrics = {},
  onRefresh,
}) {
  if (!diagnostics && diagnosticsStatus === "checking") {
    return (
      <View style={styles.stateBox}>
        <Ionicons name="sync-outline" size={16} color="#94a3b8" />
        <Text style={styles.stateText}>Loading performance metrics…</Text>
      </View>
    );
  }

  if (!diagnostics) {
    return (
      <View style={styles.stateBox}>
        <Text style={styles.stateText}>Diagnostics unavailable</Text>
        {onRefresh ? (
          <Pressable onPress={onRefresh} style={styles.refreshBtn}>
            <Text style={styles.refreshText}>Retry</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }

  const cache = diagnostics.predictive_cache || {};
  const hitRate = Number(cache.hit_rate || 0) * 100;
  const optimization = diagnostics.optimization_feedback || {};
  const translation = diagnostics.translation || {};
  const streaming = diagnostics.streaming || {};

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Ionicons name="pulse-outline" size={14} color="#67e8f9" />
        <Text style={styles.title}>Live performance</Text>
        {onRefresh ? (
          <Pressable onPress={onRefresh} style={styles.iconBtn} accessibilityLabel="Refresh metrics">
            <Ionicons name="refresh-outline" size={16} color="#67e8f9" />
          </Pressable>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Session latency</Text>
        <MetricRow label="STT" value={latencyMetrics.sttLatency ? `${latencyMetrics.sttLatency}ms` : "—"} />
        <MetricRow label="Understand" value={latencyMetrics.translationLatency ? `${latencyMetrics.translationLatency}ms` : "—"} />
        <MetricRow label="TTS" value={latencyMetrics.ttsLatency ? `${latencyMetrics.ttsLatency}ms` : "—"} />
        <MetricRow label="First audio" value={latencyMetrics.first_audio ? `${latencyMetrics.first_audio}ms` : "—"} />
        <MetricRow label="End to end" value={latencyMetrics.endToEndLatency ? `${latencyMetrics.endToEndLatency}ms` : "—"} />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Predictive cache</Text>
        <MetricRow label="Status" value={<StatusPill ok={cache.enabled} okLabel="Enabled" badLabel="Disabled" />} />
        {cache.enabled ? (
          <>
            <MetricRow label="Hit rate" value={`${hitRate.toFixed(1)}%`} />
            <MetricRow label="Hits / misses" value={`${cache.hits || 0} / ${cache.misses || 0}`} />
          </>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Bridge backend</Text>
        <MetricRow label="Runtime" value={translation.runtime || "—"} />
        <MetricRow label="Backend" value={translation.backend || "—"} />
        <MetricRow label="Device" value={translation.device || "—"} />
        <MetricRow
          label="Remote"
          value={<StatusPill ok={translation.remote_translator_reachable} okLabel="Reachable" badLabel="Unreachable" />}
        />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Streaming</Text>
        <MetricRow label="VAD silent checks" value={String(streaming.vad_silent_checks ?? "—")} />
        <MetricRow label="Speech merge" value={streaming.speech_merge_ms != null ? `${streaming.speech_merge_ms}ms` : "—"} />
        <MetricRow label="Min speech bytes" value={String(streaming.min_speech_bytes ?? "—")} />
      </View>

      {optimization.enabled != null ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Optimization</Text>
          <MetricRow
            label="Feedback loop"
            value={<StatusPill ok={optimization.enabled} okLabel="Active" badLabel="Inactive" />}
          />
          {optimization.status ? <MetricRow label="Status" value={optimization.status} /> : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10, marginTop: 4 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { flex: 1, color: "#67e8f9", fontSize: 12, fontWeight: "800", letterSpacing: 0.4, textTransform: "uppercase" },
  iconBtn: { padding: 4 },
  card: {
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.22)",
    backgroundColor: "rgba(8, 28, 36, 0.72)",
    gap: 6,
  },
  cardTitle: { color: "#e2e8f0", fontSize: 12, fontWeight: "800", marginBottom: 2 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  label: { color: "#94a3b8", fontSize: 12, fontWeight: "600", flex: 1 },
  value: { color: "#f8fafc", fontSize: 12, fontWeight: "700", flexShrink: 1, textAlign: "right" },
  pill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, borderWidth: 1 },
  pillOk: { backgroundColor: "rgba(52, 211, 153, 0.12)", borderColor: "rgba(52, 211, 153, 0.35)" },
  pillBad: { backgroundColor: "rgba(248, 113, 113, 0.12)", borderColor: "rgba(248, 113, 113, 0.35)" },
  pillText: { fontSize: 10, fontWeight: "800", textTransform: "uppercase" },
  pillTextOk: { color: "#6ee7b7" },
  pillTextBad: { color: "#fca5a5" },
  stateBox: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 8 },
  stateText: { color: "#94a3b8", fontSize: 12, fontWeight: "600" },
  refreshBtn: {
    marginLeft: "auto",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.32)",
  },
  refreshText: { color: "#67e8f9", fontSize: 11, fontWeight: "700" },
});
