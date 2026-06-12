import { useEffect, useRef, useState } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function ErrorBanner({ message, actionLabel, onAction, onDismiss, variant = "error" }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-8)).current;
  const [displayMessage, setDisplayMessage] = useState(message || "");
  const [displayVariant, setDisplayVariant] = useState(variant);

  useEffect(() => {
    if (message) {
      setDisplayMessage(message);
      setDisplayVariant(variant);
      opacity.setValue(0);
      translateY.setValue(-8);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 4, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    if (!displayMessage) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 180, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: -8, duration: 180, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setDisplayMessage("");
    });
    return undefined;
  }, [message, variant, opacity, translateY, displayMessage]);

  if (!displayMessage) return null;

  const isWarning = displayVariant === "warning";
  const accentColor = isWarning ? "#fbbf24" : "#f87171";
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
      <View style={[styles.bannerAccent, { backgroundColor: accentColor }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />
      <View style={[styles.bannerIconWrap, isWarning ? styles.bannerIconWarning : styles.bannerIconError]}>
        <Ionicons name={isWarning ? "warning" : "alert-circle"} size={18} color={isWarning ? "#fbbf24" : "#f87171"} />
      </View>
      <Text style={styles.bannerText}>{displayMessage}</Text>
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
