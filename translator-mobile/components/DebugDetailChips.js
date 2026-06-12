import { View, Text, Animated } from "react-native";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";

export default function DebugDetailChips({ visible = false, detail = "" }) {
  const shouldShow = Boolean(visible && detail);
  const { mounted, style } = useAnimatedPresence(shouldShow, { initialOffset: 6, duration: 220, exitDuration: 160 });

  if (!mounted) return null;

  const chips = String(detail)
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);

  if (!chips.length) return null;

  return (
    <Animated.View
      style={[styles.debugDetailChips, style]}
      accessibilityRole="text"
      accessibilityLabel={`Technical details: ${detail}`}
    >
      {chips.map((chip) => (
        <View key={chip} style={styles.debugDetailChip}>
          <Text style={styles.debugDetailChipText}>{chip}</Text>
        </View>
      ))}
    </Animated.View>
  );
}
