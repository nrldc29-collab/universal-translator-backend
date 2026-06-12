import { useEffect, useRef, useState } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function Toast({ message, variant = "info" }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(14)).current;
  const glow = useRef(new Animated.Value(0)).current;
  const [displayMessage, setDisplayMessage] = useState(message || "");
  const [displayVariant, setDisplayVariant] = useState(variant);

  useEffect(() => {
    if (message) {
      setDisplayMessage(message);
      setDisplayVariant(variant);
      opacity.setValue(0);
      translateY.setValue(14);
      glow.setValue(0);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 18, bounciness: 5, useNativeDriver: true }),
      ]).start();
      if (variant === "success") {
        Animated.sequence([
          Animated.timing(glow, { toValue: 1, duration: 180, useNativeDriver: true }),
          Animated.timing(glow, { toValue: 0, duration: 640, useNativeDriver: true }),
        ]).start();
      }
      return undefined;
    }
    if (!displayMessage) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: 10, duration: 200, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setDisplayMessage("");
    });
    return undefined;
  }, [message, variant, opacity, translateY, glow, displayMessage]);

  if (!displayMessage) return null;

  const icon = displayVariant === "success" ? "checkmark-circle" : displayVariant === "error" ? "alert-circle" : "information-circle";
  const tone = displayVariant === "success" ? "#34d399" : displayVariant === "error" ? "#f87171" : "#67e8f9";
  const variantStyle =
    displayVariant === "success" ? styles.toastSuccess : displayVariant === "error" ? styles.toastError : styles.toastInfo;
  const glowOpacity = glow.interpolate({ inputRange: [0, 1], outputRange: [0, 0.55] });

  return (
    <Animated.View
      style={[styles.toast, variantStyle, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      {displayVariant === "success" ? (
        <Animated.View
          style={[styles.toastGlow, { opacity: glowOpacity, backgroundColor: tone }]}
          pointerEvents="none"
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      <View style={[styles.toastAccent, { backgroundColor: tone }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />
      <View style={[styles.toastIconWrap, { borderColor: `${tone}44` }]}>
        <Ionicons name={icon} size={17} color={tone} />
      </View>
      <Text style={styles.toastText}>{displayMessage}</Text>
    </Animated.View>
  );
}
