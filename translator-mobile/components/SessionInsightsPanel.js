import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";

function InsightChip({ icon, label, tone = "default" }) {
  return (
    <View style={[styles.debugInsightChip, tone === "live" && styles.debugInsightChipLive, tone === "warn" && styles.debugInsightChipWarn]}>
      <Ionicons name={icon} size={11} color={tone === "live" ? "#5eead4" : tone === "warn" ? "#fbbf24" : "#67e8f9"} />
      <Text style={styles.debugInsightChipText}>{label}</Text>
    </View>
  );
}

export default function SessionInsightsPanel({
  visible = false,
  semanticContext = null,
  conversationBrain = "",
  brainMessage = "",
  emotionInfo = null,
  isStreaming = false,
  isTranslating = false,
  showTechnical = false,
  latencyMetrics = {},
  hasPartialStt = false,
  hasPartialTranslation = false,
  diagnostics = null,
  diagnosticsStatus = "",
}) {
  const intent = semanticContext?.last_intent || semanticContext?.intent;
  const mood = semanticContext?.conversation_mood || semanticContext?.mood || emotionInfo?.tone;
  const emotion = semanticContext?.emotion || emotionInfo?.emotion;
  const topics = Array.isArray(semanticContext?.topics) ? semanticContext.topics : [];
  const latency = latencyMetrics.endToEndLatency || latencyMetrics.ttsLatency || latencyMetrics.translationLatency;
  const hasInsights = Boolean(
    conversationBrain
    || brainMessage
    || (intent && intent !== "statement")
    || (mood && mood !== "neutral")
    || emotion
    || topics.length
    || (showTechnical && (latency || isStreaming || isTranslating || hasPartialStt || hasPartialTranslation))
    || (showTechnical && diagnostics),
  );
  const shouldShow = visible && hasInsights;
  const { mounted, style } = useAnimatedPresence(shouldShow, { initialOffset: 6 });

  if (!mounted) return null;

  return (
    <Animated.View style={[styles.debugInsightsPanel, styles.sessionInsightsPanel, style]} accessibilityRole="summary">
      <View style={styles.debugInsightsHeader}>
        <Ionicons name="sparkles-outline" size={12} color="#67e8f9" />
        <Text style={styles.debugInsightsTitle}>{showTechnical ? "Session insights" : "Conversation pulse"}</Text>
      </View>
      <View style={styles.debugInsightsGrid}>
        {showTechnical ? (
          <>
            <InsightChip icon="ear" label={isStreaming ? "STT live" : hasPartialStt ? "STT partial" : "STT idle"} tone={isStreaming ? "live" : "default"} />
            <InsightChip icon="heart" label={isTranslating ? "Understanding" : hasPartialTranslation ? "Draft bridge" : "Bridge idle"} tone={isTranslating ? "live" : "default"} />
            {latency ? <InsightChip icon="speedometer-outline" label={`${latency}ms`} /> : null}
            {latencyMetrics.first_audio ? <InsightChip icon="flash-outline" label={`First audio ${latencyMetrics.first_audio}ms`} tone="live" /> : null}
            {diagnostics?.cip?.mode ? <InsightChip icon="git-network-outline" label={`CIP ${diagnostics.cip.mode}`} /> : null}
            {diagnostics?.stt_provider ? <InsightChip icon="mic-outline" label={`STT ${diagnostics.stt_provider}`} /> : null}
            {diagnostics?.tts_neural?.ready === false ? (
              <InsightChip icon="volume-mute-outline" label="Neural voice warming" tone="warn" />
            ) : null}
            {diagnosticsStatus === "offline" ? <InsightChip icon="cloud-offline-outline" label="Diagnostics offline" tone="warn" /> : null}
          </>
        ) : null}
        {conversationBrain ? (
          <InsightChip
            icon="bulb-outline"
            label={conversationBrain.length > 42 ? `${conversationBrain.slice(0, 39)}…` : conversationBrain}
            tone="live"
          />
        ) : null}
        {brainMessage ? (
          <InsightChip
            icon="git-branch-outline"
            label={brainMessage.length > 42 ? `${brainMessage.slice(0, 39)}…` : brainMessage}
            tone="warn"
          />
        ) : null}
        {intent && intent !== "statement" ? <InsightChip icon="chatbubble-ellipses-outline" label={`Intent: ${intent}`} /> : null}
        {mood && mood !== "neutral" ? <InsightChip icon="happy-outline" label={`Mood: ${mood}`} tone="warn" /> : null}
        {emotion ? <InsightChip icon="heart-outline" label={`Emotion: ${emotion}`} tone="warn" /> : null}
        {topics.slice(0, showTechnical ? 3 : 4).map((topic) => (
          <InsightChip key={topic} icon="pricetag-outline" label={topic} />
        ))}
      </View>
    </Animated.View>
  );
}
