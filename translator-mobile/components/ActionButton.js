import { Text, Pressable } from "react-native";
import styles from "../AppStyles";

export default function ActionButton({ title, onPress, tone = "primary", disabled = false, style }) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.actionButton,
        styles[`actionButton_${tone}`],
        disabled && styles.actionButtonDisabled,
        pressed && !disabled && styles.actionButtonPressed,
        style,
      ]}
    >
      <Text style={[styles.actionButtonText, tone === "ghost" && styles.actionButtonTextGhost]}>{title}</Text>
    </Pressable>
  );
}
