import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useMountForPresence } from "../hooks/useMountForPresence";

export default function ClarifyPill({
  visible = false,
  message = "",
  onSpeakAgain,
  onDismiss,
}) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(6)).current;
  const show = Boolean(visible && message);
  const { mounted, mountedRef, setMounted } = useMountForPresence(show);

  useEffect(() => {
    if (show) {
      opacity.setValue(0);
      translateY.setValue(6);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 5, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    if (!mountedRef.current) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 160, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: 6, duration: 160, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setMounted(false);
    });
    return undefined;
  }, [show, opacity, translateY, setMounted]);

  if (!mounted || !message) return null;

  return (
    <Animated.View
      style={[styles.clarifyPill, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={styles.clarifyPillRow}>
        <View style={styles.clarifyPillIconWrap}>
          <Ionicons name="help-circle-outline" size={18} color="#fbbf24" />
        </View>
        <View style={styles.clarifyPillBody}>
          <Text style={styles.clarifyPillText}>{message}</Text>
          <View style={styles.clarifyPillActions}>
            {onSpeakAgain ? (
              <Pressable
                onPress={onSpeakAgain}
                style={({ pressed }) => [styles.clarifyPillPrimary, pressed && styles.clarifyPillPressed]}
                accessibilityRole="button"
                accessibilityLabel="Speak again"
              >
                <Text style={styles.clarifyPillPrimaryText}>Speak again</Text>
              </Pressable>
            ) : null}
            {onDismiss ? (
              <Pressable
                onPress={onDismiss}
                style={({ pressed }) => [styles.clarifyPillSecondary, pressed && styles.clarifyPillPressed]}
                accessibilityRole="button"
                accessibilityLabel="Dismiss"
              >
                <Text style={styles.clarifyPillSecondaryText}>Dismiss</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      </View>
    </Animated.View>
  );
}
