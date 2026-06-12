import { useEffect, useRef } from "react";
import { View, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function LaneBridgeSpan({ active = false }) {
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

  const lineOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.2, 0.75],
  });
  const hubScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.08],
  });
  const hubBg = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(103, 232, 249, 0.12)", "rgba(45, 212, 191, 0.38)"],
  });

  return (
    <View style={styles.laneBridgeSpan} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Animated.View style={[styles.laneBridgeLine, active && { opacity: lineOpacity }]} />
      <Animated.View
        style={[
          styles.laneBridgeHub,
          active && styles.laneBridgeHubActive,
          active && { backgroundColor: hubBg, transform: [{ scale: hubScale }] },
        ]}
      >
        <Ionicons name="git-network-outline" size={11} color={active ? "#5eead4" : "#64748b"} />
      </Animated.View>
      <Animated.View style={[styles.laneBridgeLine, active && { opacity: lineOpacity }]} />
    </View>
  );
}
