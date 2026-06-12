import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

function resolveTone({
  isConnected,
  isConnecting,
  isStreaming,
  isTranslating,
  isPlayingTts,
  onCellularWithLanServer,
}) {
  if (!isConnected) {
    if (onCellularWithLanServer) return "warning";
    if (isConnecting) return "connecting";
    return "offline";
  }
  if (isStreaming) return "listening";
  if (isPlayingTts) return "speaking";
  if (isTranslating) return "translating";
  return "online";
}

const TONE_COLORS = {
  offline: "#f87171",
  warning: "#fbbf24",
  connecting: "#67e8f9",
  online: "#34d399",
  listening: "#34d399",
  translating: "#fbbf24",
  speaking: "#d8b4fe",
};

export default function StatusStrip({
  onPress,
  compact = false,
  isConnected = false,
  isConnecting = false,
  isStreaming = false,
  isTranslating = false,
  isPlayingTts = false,
  onCellularWithLanServer = false,
  systemColor = "#94a3b8",
  visibleStatusLine = "",
  statusDetail = "",
  buildMeta = "",
  debugExpanded = false,
  accessibilityLabel = "Status",
  accessibilityHint = "",
}) {
  const pulse = useRef(new Animated.Value(0)).current;
  const tone = resolveTone({
    isConnected,
    isConnecting,
    isStreaming,
    isTranslating,
    isPlayingTts,
    onCellularWithLanServer,
  });
  const accentColor = TONE_COLORS[tone] || systemColor;
  const shouldPulse = isConnected && (isStreaming || isTranslating || isPlayingTts);

  useEffect(() => {
    if (!shouldPulse) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [shouldPulse, pulse]);

  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.08, 0.22] });

  const iconName = !isConnected
    ? (isConnecting ? "sync" : "cloud-offline-outline")
    : isStreaming
      ? "radio"
      : isPlayingTts
        ? "volume-high"
        : isTranslating
          ? "heart-outline"
          : "git-network-outline";

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.statusStrip,
        compact && styles.statusStripCompact,
        isConnected && styles.statusStripOnline,
        isConnected && isStreaming && styles.statusStripListening,
        isConnected && isTranslating && !isStreaming && styles.statusStripTranslating,
        isConnected && isPlayingTts && styles.statusStripSpeaking,
        !isConnected && styles.statusStripOffline,
        onCellularWithLanServer && !isConnected && styles.statusStripWarning,
        pressed && styles.statusStripPressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
    >
      {shouldPulse ? (
        <Animated.View
          style={[styles.statusStripGlow, { opacity: glowOpacity, backgroundColor: accentColor }]}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <LinearGradient
        colors={[`${accentColor}55`, `${accentColor}22`, "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.statusStripShine}
        pointerEvents="none"
      />
      <View style={[styles.statusStripAccent, { backgroundColor: accentColor }]} pointerEvents="none" />
      <Ionicons name={iconName} size={18} color={systemColor} />
      <View style={styles.statusTextWrap}>
        <Text numberOfLines={2} accessibilityLiveRegion="polite" style={[styles.statusLine, { color: systemColor }]}>
          {visibleStatusLine}
        </Text>
        {statusDetail ? (
          <Text numberOfLines={2} style={[styles.statusDetail, !isConnected && styles.statusDetailOffline]}>
            {statusDetail}
          </Text>
        ) : null}
        {buildMeta ? (
          <Text numberOfLines={2} style={styles.statusDetailMuted}>
            {buildMeta}
          </Text>
        ) : null}
      </View>
      {isConnected && debugExpanded ? (
        <View style={styles.statusStripDebugChip}>
          <Text style={styles.statusStripDebugChipText}>TECH</Text>
        </View>
      ) : null}
      <Ionicons
        name={debugExpanded ? "chevron-down" : "chevron-forward"}
        size={14}
        color="rgba(148, 163, 184, 0.55)"
      />
    </Pressable>
  );
}
