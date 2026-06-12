import { useEffect, useRef } from "react";
import { Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { liveStatusDefaults } from "../constants/productVoice";

const DEFAULTS = liveStatusDefaults();
const MODE_META = {
  listening: { icon: "radio", color: "#34d399", panelStyle: null, label: DEFAULTS.listening },
  speaking: { icon: "volume-high", color: "#d8b4fe", panelStyle: styles.liveStatusPanelSpeaking, label: DEFAULTS.speaking },
  translating: { icon: "heart", color: "#fbbf24", panelStyle: styles.liveStatusPanelTranslating, label: DEFAULTS.translating },
  armed: { icon: "pulse", color: "#67e8f9", panelStyle: styles.liveStatusPanelArmed, label: DEFAULTS.armed },
  cert_advisory: { icon: "ear-outline", color: "#fbbf24", panelStyle: styles.liveStatusPanelTranslating, label: DEFAULTS.cert_advisory },
  cert_required: { icon: "shield-checkmark-outline", color: "#fb923c", panelStyle: styles.liveStatusPanelSpeaking, label: DEFAULTS.cert_required },
  clarify: { icon: "help-circle-outline", color: "#fbbf24", panelStyle: styles.liveStatusPanelTranslating, label: DEFAULTS.clarify },
};

export default function LiveStatusPanel({
  visible = false,
  mode = "listening",
  label = "",
}) {
  const pulse = useRef(new Animated.Value(0)).current;
  const meta = MODE_META[mode] || MODE_META.listening;
  const { mounted, style } = useAnimatedPresence(visible, { initialOffset: 4, duration: 200, exitDuration: 160 });

  useEffect(() => {
    if (!visible) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: mode === "speaking" ? 650 : 800, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: mode === "speaking" ? 650 : 800, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [visible, mode, pulse]);

  if (!mounted) return null;

  const dotScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, mode === "listening" ? 1.35 : 1.25] });
  const dotOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.65, 1] });
  const displayLabel = label || meta.label;

  return (
    <Animated.View
      style={[styles.liveStatusPanel, meta.panelStyle, style]}
      accessibilityRole="text"
      accessibilityLiveRegion="polite"
    >
      <Animated.View style={[styles.liveStatusDot, { opacity: dotOpacity, transform: [{ scale: dotScale }], backgroundColor: meta.color }]} />
      <Ionicons name={meta.icon} size={13} color={meta.color} />
      <Text style={[styles.liveStatusText, mode === "speaking" && styles.liveStatusTextSpeaking, mode === "translating" && styles.liveStatusTextTranslating]}>
        {displayLabel}
      </Text>
    </Animated.View>
  );
}
