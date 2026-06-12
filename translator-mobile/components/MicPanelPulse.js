import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import styles from "../AppStyles";

export default function MicPanelPulse({ visible = false }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1200, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1200, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [visible, pulse]);

  if (!visible) return null;

  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.15, 0.48] });

  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.micPanelPulse, { opacity }]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
