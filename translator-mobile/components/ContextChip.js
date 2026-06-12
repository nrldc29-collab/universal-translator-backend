import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";

export default function ContextChip({ label }) {
  const { mounted, style } = useAnimatedPresence(Boolean(label), { initialOffset: 0, duration: 220, exitDuration: 160 });

  if (!mounted) return null;

  return (
    <Animated.View style={[styles.contextChip, style]} accessibilityRole="text">
      <View style={styles.contextChipDot} pointerEvents="none" />
      <Ionicons name="git-network-outline" size={14} color="#67e8f9" />
      <Text style={styles.contextChipText}>{label}</Text>
    </Animated.View>
  );
}
