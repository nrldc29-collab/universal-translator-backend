import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import styles from "../AppStyles";
import CosmicGridOverlay from "./CosmicGridOverlay";

export default function CosmicAmbience() {
  const drift = useRef(new Animated.Value(0)).current;
  const glowDrift = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const gridLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(drift, { toValue: 1, duration: 18000, useNativeDriver: true }),
        Animated.timing(drift, { toValue: 0, duration: 18000, useNativeDriver: true }),
      ]),
    );
    const glowLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(glowDrift, { toValue: 1, duration: 12000, useNativeDriver: true }),
        Animated.timing(glowDrift, { toValue: 0, duration: 12000, useNativeDriver: true }),
      ]),
    );
    gridLoop.start();
    glowLoop.start();
    return () => {
      gridLoop.stop();
      glowLoop.stop();
    };
  }, [drift, glowDrift]);

  const gridShiftX = drift.interpolate({ inputRange: [0, 1], outputRange: [0, 14] });
  const gridShiftY = drift.interpolate({ inputRange: [0, 1], outputRange: [0, 10] });
  const glowShiftX = glowDrift.interpolate({ inputRange: [0, 1], outputRange: [-8, 12] });
  const glowShiftY = glowDrift.interpolate({ inputRange: [0, 1], outputRange: [0, -10] });
  const blueShiftX = glowDrift.interpolate({ inputRange: [0, 1], outputRange: [10, -6] });

  return (
    <>
      <Animated.View
        style={[styles.cosmicGridDriftWrap, { transform: [{ translateX: gridShiftX }, { translateY: gridShiftY }] }]}
        pointerEvents="none"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <CosmicGridOverlay />
      </Animated.View>
      <Animated.View
        style={[styles.cosmicGlow, { transform: [{ translateX: glowShiftX }, { translateY: glowShiftY }] }]}
        pointerEvents="none"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
      <Animated.View
        style={[styles.cosmicGlowBlue, { transform: [{ translateX: blueShiftX }, { translateY: glowShiftY }] }]}
        pointerEvents="none"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
    </>
  );
}
