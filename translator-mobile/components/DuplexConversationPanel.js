import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { duplexCopy, duplexPersonBadge } from "../constants/productVoice";

function BridgePulse({ active = false }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!active) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 750, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 0, duration: 750, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, pulse]);

  const glow = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(103, 232, 249, 0.15)", "rgba(45, 212, 191, 0.55)"],
  });
  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.08],
  });

  return (
    <Animated.View
      style={[
        styles.duplexBridge,
        active && styles.duplexBridgeActive,
        active && { backgroundColor: glow, transform: [{ scale }] },
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <Ionicons name="git-network-outline" size={14} color={active ? "#5eead4" : "#67e8f9"} />
    </Animated.View>
  );
}

function PersonLane({ label, language, isActive, isListening, compact }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isActive || !isListening) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 800, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isActive, isListening, pulse]);

  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0, 0.45] });

  return (
    <View
      style={[
        styles.duplexPersonLane,
        compact && styles.duplexPersonLaneCompact,
        isActive && styles.duplexPersonLaneActive,
      ]}
      accessibilityRole="text"
      accessibilityLabel={`${label} speaks ${language}${isActive ? ", currently active" : ""}`}
    >
      {isActive && isListening ? (
        <Animated.View style={[styles.duplexPersonGlow, { opacity: glowOpacity }]} pointerEvents="none" />
      ) : null}
      <View style={styles.duplexPersonHead}>
        <Ionicons name="person-circle-outline" size={14} color={isActive ? "#5eead4" : "#94a3b8"} />
        <Text style={[styles.duplexPersonLabel, isActive && styles.duplexPersonLabelActive]}>{label}</Text>
      </View>
      <Text style={styles.duplexPersonLang}>{language}</Text>
      {isActive ? (
        <View style={styles.duplexPersonLiveBadge}>
          <View style={styles.duplexPersonLiveDot} />
          <Text style={styles.duplexPersonLiveText}>{duplexPersonBadge(isListening)}</Text>
        </View>
      ) : null}
    </View>
  );
}

export default function DuplexConversationPanel({
  visible = false,
  compact = false,
  sourceLabel = "English",
  targetLabel = "French",
  activeSpeakerIndex = 1,
  activeSpeakerLabel = "Person 1",
  routeConfidence = 0,
  isStreaming = false,
}) {
  const { mounted, style } = useAnimatedPresence(visible, { initialOffset: 6, duration: 220, exitDuration: 160 });

  if (!mounted) return null;

  const personOneActive = Number(activeSpeakerIndex) === 1;
  const personTwoActive = Number(activeSpeakerIndex) === 2;
  const personOneLabel = personOneActive ? activeSpeakerLabel : "Person 1";
  const personTwoLabel = personTwoActive ? activeSpeakerLabel : "Person 2";
  const confidenceLabel = routeConfidence > 0 ? `${Math.round(routeConfidence * 100)}% route` : "Auto-route";
  const { title, subtitle } = duplexCopy();

  return (
    <Animated.View
      style={[styles.duplexPanel, compact && styles.duplexPanelCompact, style]}
      accessibilityRole="summary"
      accessibilityLabel={`${title}. ${subtitle}`}
    >
      <View style={styles.duplexPanelHeader}>
        <Ionicons name="git-network-outline" size={13} color="#67e8f9" />
        <View style={styles.duplexPanelTitleWrap}>
          <Text style={styles.duplexPanelTitle}>{title}</Text>
          <Text style={styles.duplexPanelSubtitle}>{subtitle}</Text>
        </View>
        <Text style={styles.duplexPanelMeta}>{confidenceLabel}</Text>
      </View>
      <View style={styles.duplexPersonRow}>
        <PersonLane
          label={personOneLabel}
          language={sourceLabel}
          isActive={personOneActive}
          isListening={personOneActive && isStreaming}
          compact={compact}
        />
        <BridgePulse active={isStreaming} />
        <PersonLane
          label={personTwoLabel}
          language={targetLabel}
          isActive={personTwoActive}
          isListening={personTwoActive && isStreaming}
          compact={compact}
        />
      </View>
    </Animated.View>
  );
}
