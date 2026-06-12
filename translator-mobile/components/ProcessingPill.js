import { useEffect, useRef } from "react";
import { Text, ActivityIndicator, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { processingPillMessage } from "../constants/productVoice";

export default function ProcessingPill({ visible = false, message = processingPillMessage() }) {
  const { mounted, style: presenceStyle } = useAnimatedPresence(visible, { initialOffset: 8, duration: 220, exitDuration: 160 });
  const shimmer = useRef(new Animated.Value(0)).current;
  const sparkle = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!mounted) {
      shimmer.stopAnimation();
      sparkle.stopAnimation();
      shimmer.setValue(0);
      sparkle.setValue(1);
      return undefined;
    }
    const shimmerLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(shimmer, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(shimmer, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    const sparkleLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(sparkle, { toValue: 1.18, duration: 700, useNativeDriver: true }),
        Animated.timing(sparkle, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    shimmerLoop.start();
    sparkleLoop.start();
    return () => {
      shimmerLoop.stop();
      sparkleLoop.stop();
    };
  }, [mounted, shimmer, sparkle]);

  if (!mounted) return null;

  const glowOpacity = shimmer.interpolate({ inputRange: [0, 1], outputRange: [0.08, 0.28] });

  return (
    <Animated.View
      style={[styles.processingPill, presenceStyle]}
      accessibilityRole="text"
      accessibilityLiveRegion="polite"
    >
      <Animated.View
        style={[styles.processingPillGlow, { opacity: glowOpacity }]}
        pointerEvents="none"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
      <Animated.View style={[styles.processingPillIcon, { transform: [{ scale: sparkle }] }]}>
        <Ionicons name="heart-outline" size={13} color="#fbbf24" />
      </Animated.View>
      <ActivityIndicator size="small" color="#fbbf24" />
      <Text style={styles.processingPillText}>{message}</Text>
    </Animated.View>
  );
}
