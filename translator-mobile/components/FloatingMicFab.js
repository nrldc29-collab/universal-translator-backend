import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function FloatingMicFab({
  visible = false,
  onPress,
  isListening = false,
  isArmed = false,
  audioLevel = 0,
  disabled = false,
  accessibilityLabel = "Open bridge controls",
}) {
  const opacity = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.82)).current;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: visible ? 1 : 0,
        duration: visible ? 220 : 160,
        useNativeDriver: true,
      }),
      Animated.spring(scale, {
        toValue: visible ? 1 : 0.82,
        speed: 18,
        bounciness: visible ? 6 : 0,
        useNativeDriver: true,
      }),
    ]).start();
  }, [visible, opacity, scale]);

  useEffect(() => {
    if (!isListening) {
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
  }, [isListening, pulse]);

  const haloScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.14] });
  const haloOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 0.65] });
  const level = Math.max(0, Math.min(1, audioLevel));

  return (
    <Animated.View
      pointerEvents={visible ? "auto" : "none"}
      style={[styles.floatingMicFabWrap, { opacity, transform: [{ scale }] }]}
    >
      {isListening ? (
        <Animated.View
          style={[styles.floatingMicFabHalo, { opacity: haloOpacity, transform: [{ scale: haloScale }] }]}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <Pressable
        onPress={onPress}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel}
        accessibilityState={{ disabled, selected: isArmed || isListening }}
        style={({ pressed }) => [
          styles.floatingMicFab,
          isListening && styles.floatingMicFabListening,
          isArmed && !isListening && styles.floatingMicFabArmed,
          disabled && styles.floatingMicFabDisabled,
          pressed && !disabled && styles.floatingMicFabPressed,
        ]}
      >
        <View
          style={[
            styles.floatingMicFabRing,
            isListening && styles.floatingMicFabRingLive,
            { transform: [{ scale: 1 + level * 0.08 }] },
          ]}
        />
        <Ionicons
          name={isListening ? "radio" : isArmed ? "mic" : "mic-outline"}
          size={26}
          color={isListening ? "#a7f3d0" : "#f8fafc"}
        />
        {isListening ? <View style={styles.floatingMicFabLed} /> : null}
      </Pressable>
      <View
        style={[
          styles.floatingMicFabLabel,
          isListening && styles.floatingMicFabLabelLive,
          isArmed && !isListening && styles.floatingMicFabLabelArmed,
        ]}
        pointerEvents="none"
      >
        <Text style={styles.floatingMicFabLabelText}>
          {isListening ? "Bridge live" : isArmed ? "Open bridge" : "Start"}
        </Text>
      </View>
    </Animated.View>
  );
}
