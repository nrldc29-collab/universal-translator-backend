import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function Toast({ message, variant = "info" }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(14)).current;

  useEffect(() => {
    if (!message) return;
    opacity.setValue(0);
    translateY.setValue(14);
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, speed: 18, bounciness: 5, useNativeDriver: true }),
    ]).start();
  }, [message, variant, opacity, translateY]);

  if (!message) return null;

  const icon = variant === "success" ? "checkmark-circle" : variant === "error" ? "alert-circle" : "information-circle";
  const tone = variant === "success" ? "#34d399" : variant === "error" ? "#f87171" : "#67e8f9";
  const variantStyle =
    variant === "success" ? styles.toastSuccess : variant === "error" ? styles.toastError : styles.toastInfo;

  return (
    <Animated.View
      style={[styles.toast, variantStyle, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={[styles.toastIconWrap, { borderColor: `${tone}44` }]}>
        <Ionicons name={icon} size={17} color={tone} />
      </View>
      <Text style={styles.toastText}>{message}</Text>
    </Animated.View>
  );
}
