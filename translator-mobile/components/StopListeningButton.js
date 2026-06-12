import { useEffect, useRef } from "react";
import { Pressable, Text, View, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { pauseBridgeLabel } from "../constants/productVoice";

export default function StopListeningButton({ onPress, label = pauseBridgeLabel() }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1100, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1100, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.12, 0.38] });

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.stopListeningBtn, pressed && styles.stopListeningBtnPressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Animated.View style={[styles.stopListeningGlow, { opacity: glowOpacity }]} pointerEvents="none" />
      <View style={styles.stopListeningIconWrap}>
        <Ionicons name="pause-circle" size={14} color="#fcd34d" />
      </View>
      <Text style={styles.stopListeningText}>{label}</Text>
    </Pressable>
  );
}
