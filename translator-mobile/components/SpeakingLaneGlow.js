import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import styles from "../AppStyles";

export default function SpeakingLaneGlow({ visible = false }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [visible, pulse]);

  if (!visible) return null;

  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.12, 0.32] });

  return (
    <Animated.View
      style={[styles.speakingLaneGlow, { opacity }]}
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
