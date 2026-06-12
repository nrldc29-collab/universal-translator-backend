import { useEffect, useRef } from "react";
import { Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { connectionStripStatus } from "../constants/productVoice";

export default function ConnectionStrip({
  visible = false,
  isListening = false,
  isSpeaking = false,
  isReconnecting = false,
  reconnectAttempt = 0,
  reconnectMax = 10,
  label = "Bridge linked",
}) {
  const { mounted, style } = useAnimatedPresence(visible, { initialOffset: 4, duration: 200, exitDuration: 140 });
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!mounted || (!isListening && !isSpeaking)) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 850, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 850, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [mounted, isListening, isSpeaking, pulse]);

  if (!mounted) return null;

  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.08, 0.22] });
  const statusLabel = connectionStripStatus({
    isReconnecting,
    isListening,
    isSpeaking,
    reconnectAttempt,
    reconnectMax,
    connectedLabel: label,
  });
  const stripStyle = isReconnecting
    ? styles.connectionStripReconnecting
    : isListening
      ? styles.connectionStripListening
      : isSpeaking
        ? styles.connectionStripSpeaking
        : null;

  return (
    <Animated.View style={[styles.connectionStrip, stripStyle, style]}>
      {(isListening || isSpeaking) ? (
        <Animated.View
          style={[styles.connectionStripGlow, { opacity: glowOpacity }]}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <Ionicons
        name={
          isReconnecting
            ? "cloud-offline-outline"
            : isListening
              ? "radio"
              : isSpeaking
                ? "volume-high"
                : "git-network-outline"
        }
        size={14}
        color={isReconnecting ? "#fbbf24" : isListening ? "#34d399" : isSpeaking ? "#fbbf24" : "#67e8f9"}
      />
      <Text style={styles.connectionStripText}>{statusLabel}</Text>
    </Animated.View>
  );
}
