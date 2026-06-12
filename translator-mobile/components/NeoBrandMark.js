import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import styles from "../AppStyles";

export default function NeoBrandMark({ subline = "", live = false, compact = false }) {
  const glow = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!live) {
      glow.stopAnimation();
      glow.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, { toValue: 1, duration: 1400, useNativeDriver: true }),
        Animated.timing(glow, { toValue: 0, duration: 1400, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [live, glow]);

  const glowOpacity = glow.interpolate({ inputRange: [0, 1], outputRange: [0.15, 0.45] });

  return (
    <View style={[styles.neoBrand, live && styles.neoBrandLive, compact && styles.neoBrandCompact]}>
      {live ? (
        <Animated.View
          style={[styles.neoBrandGlow, { opacity: glowOpacity }]}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <Text style={[styles.neoMarkWord, compact && styles.neoMarkWordCompact]} accessibilityRole="header">
        Anai
      </Text>
      {subline ? <Text style={[styles.neoSub, compact && styles.neoSubCompact]}>{subline}</Text> : null}
    </View>
  );
}
