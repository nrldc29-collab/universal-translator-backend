import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function ErrorBanner({ message, actionLabel, onAction, onDismiss, variant = "error" }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-8)).current;

  useEffect(() => {
    if (!message) return;
    opacity.setValue(0);
    translateY.setValue(-8);
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 4, useNativeDriver: true }),
    ]).start();
  }, [message, variant, opacity, translateY]);

  if (!message) return null;

  const isWarning = variant === "warning";
  return (
    <Animated.View
      style={[
        styles.banner,
        isWarning ? styles.bannerWarning : styles.bannerError,
        { opacity, transform: [{ translateY }] },
      ]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={[styles.bannerIconWrap, isWarning ? styles.bannerIconWarning : styles.bannerIconError]}>
        <Ionicons name={isWarning ? "warning" : "alert-circle"} size={18} color={isWarning ? "#fbbf24" : "#f87171"} />
      </View>
      <Text style={styles.bannerText}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable
          onPress={onAction}
          style={({ pressed }) => [styles.bannerAction, pressed && styles.bannerActionPressed]}
          accessibilityRole="button"
          accessibilityLabel={actionLabel}
        >
          <Text style={styles.bannerActionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
      {onDismiss ? (
        <Pressable
          onPress={onDismiss}
          hitSlop={8}
          style={({ pressed }) => pressed && styles.bannerDismissPressed}
          accessibilityRole="button"
          accessibilityLabel="Dismiss"
        >
          <Ionicons name="close" size={18} color="#94a3b8" />
        </Pressable>
      ) : null}
    </Animated.View>
  );
}
