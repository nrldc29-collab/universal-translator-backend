import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useMountForPresence } from "../hooks/useMountForPresence";

export default function ConfidenceWarningBanner({ visible = false, message = "", onDismiss }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-6)).current;
  const show = Boolean(visible && message);
  const { mounted, mountedRef, setMounted } = useMountForPresence(show);

  useEffect(() => {
    if (show) {
      opacity.setValue(0);
      translateY.setValue(-6);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 4, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    if (!mountedRef.current) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 160, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: -6, duration: 160, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setMounted(false);
    });
    return undefined;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mountedRef tracks mount without re-running the effect
  }, [show, opacity, translateY, setMounted]);

  if (!mounted || !message) return null;

  return (
    <Animated.View
      style={[styles.banner, styles.bannerWarning, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={[styles.bannerAccent, { backgroundColor: "#fbbf24" }]} pointerEvents="none" />
      <View style={[styles.bannerIconWrap, styles.bannerIconWarning]}>
        <Ionicons name="shield-outline" size={18} color="#fbbf24" />
      </View>
      <Text style={styles.bannerText}>{message}</Text>
      {onDismiss ? (
        <Pressable
          onPress={onDismiss}
          style={({ pressed }) => pressed && styles.bannerDismissPressed}
          accessibilityRole="button"
          accessibilityLabel="Dismiss confidence warning"
        >
          <Ionicons name="close" size={16} color="rgba(226, 232, 240, 0.88)" />
        </Pressable>
      ) : null}
    </Animated.View>
  );
}
