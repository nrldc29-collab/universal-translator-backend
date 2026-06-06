import { View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function Toast({ message, variant = "info" }) {
  if (!message) return null;
  const icon = variant === "success" ? "checkmark-circle" : variant === "error" ? "alert-circle" : "information-circle";
  const tone = variant === "success" ? "#34d399" : variant === "error" ? "#f87171" : "#67e8f9";
  return (
    <View style={styles.toast} accessibilityRole="alert" accessibilityLiveRegion="polite">
      <Ionicons name={icon} size={18} color={tone} />
      <Text style={styles.toastText}>{message}</Text>
    </View>
  );
}
