import { View, Text, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function ErrorBanner({ message, actionLabel, onAction, onDismiss, variant = "error" }) {
  if (!message) return null;
  const isWarning = variant === "warning";
  return (
    <View
      style={[styles.banner, isWarning ? styles.bannerWarning : styles.bannerError]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <Ionicons name={isWarning ? "warning" : "alert-circle"} size={20} color={isWarning ? "#fbbf24" : "#f87171"} />
      <Text style={styles.bannerText}>{message}</Text>
      {actionLabel && onAction ? (
        <Pressable onPress={onAction} style={styles.bannerAction} accessibilityRole="button" accessibilityLabel={actionLabel}>
          <Text style={styles.bannerActionText}>{actionLabel}</Text>
        </Pressable>
      ) : null}
      {onDismiss ? (
        <Pressable onPress={onDismiss} hitSlop={8} accessibilityRole="button" accessibilityLabel="Dismiss">
          <Ionicons name="close" size={18} color="#94a3b8" />
        </Pressable>
      ) : null}
    </View>
  );
}
