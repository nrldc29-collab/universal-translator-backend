import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function FlowStep({ icon, label, active = false, accessibilityLabel = "" }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!active) {
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
  }, [active, pulse]);

  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0, 0.35] });

  return (
    <View
      style={[styles.flowStep, active && styles.flowStepActive]}
      accessibilityRole="text"
      accessibilityLabel={accessibilityLabel || `${label}${active ? ", active" : ""}`}
    >
      {active ? (
        <Animated.View
          style={[styles.flowStepGlow, { opacity: glowOpacity }]}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <Ionicons
        name={icon === "heart" ? "heart" : icon}
        size={14}
        color={active ? (icon === "heart" ? "#fb7185" : "#07131f") : (icon === "heart" ? "#fda4af" : "#a5b4fc")}
      />
      <Text
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.8}
        style={[styles.flowStepText, active && styles.flowStepTextActive]}
      >
        {label}
      </Text>
    </View>
  );
}
