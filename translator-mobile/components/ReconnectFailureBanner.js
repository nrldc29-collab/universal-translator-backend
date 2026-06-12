import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { reconnectFailureMessage } from "../constants/productVoice";
import { useMountForPresence } from "../hooks/useMountForPresence";

export default function ReconnectFailureBanner({
  visible = false,
  message = reconnectFailureMessage(),
  onRetry,
  onDismiss,
}) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-8)).current;
  const show = Boolean(visible && message);
  const { mounted, mountedRef, setMounted } = useMountForPresence(show);

  useEffect(() => {
    if (show) {
      opacity.setValue(0);
      translateY.setValue(-8);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 4, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    if (!mountedRef.current) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 180, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: -8, duration: 180, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setMounted(false);
    });
    return undefined;
  }, [show, opacity, translateY, setMounted]);

  if (!mounted || !message) return null;

  return (
    <Animated.View
      style={[styles.banner, styles.bannerError, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={[styles.bannerAccent, { backgroundColor: "#f87171" }]} pointerEvents="none" />
      <View style={[styles.bannerIconWrap, styles.bannerIconError]}>
        <Ionicons name="cloud-offline-outline" size={18} color="#f87171" />
      </View>
      <Text style={styles.bannerText}>{message}</Text>
      <View style={styles.certBannerActions}>
        {onRetry ? (
          <Pressable
            onPress={onRetry}
            style={({ pressed }) => [styles.certBannerAction, pressed && styles.certBannerActionPressed]}
            accessibilityRole="button"
            accessibilityLabel="Retry bridge connection"
          >
            <Text style={styles.certBannerActionText}>Retry</Text>
          </Pressable>
        ) : null}
        {onDismiss ? (
          <Pressable
            onPress={onDismiss}
            style={({ pressed }) => pressed && styles.bannerDismissPressed}
            accessibilityRole="button"
            accessibilityLabel="Dismiss"
          >
            <Ionicons name="close" size={16} color="#94a3b8" />
          </Pressable>
        ) : null}
      </View>
    </Animated.View>
  );
}
