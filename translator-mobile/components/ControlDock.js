import { View, Text, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

function IconControl({
  icon,
  label,
  onPress,
  disabled = false,
  active = false,
  urgent = false,
  danger = false,
  bridgeLinked = false,
  accessibilityLabel = label,
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled, selected: active }}
      hitSlop={8}
      style={({ pressed }) => [
        styles.iconControl,
        styles.iconControlInDock,
        active && styles.iconControlActive,
        bridgeLinked && styles.iconControlBridgeLinked,
        urgent && styles.iconControlUrgent,
        danger && styles.iconControlDanger,
        disabled && styles.iconControlDisabled,
        pressed && !disabled && styles.iconControlPressed,
      ]}
    >
      {active ? (
        <View
          style={[styles.iconControlGlow, bridgeLinked && styles.iconControlBridgeGlow]}
          pointerEvents="none"
        />
      ) : null}
      <Ionicons
        name={icon}
        size={20}
        color={danger ? "#fecaca" : urgent ? "#fbbf24" : active ? "#07131f" : "#dbeafe"}
      />
      <Text
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.72}
        style={[
          styles.iconControlText,
          active && styles.iconControlTextActive,
          urgent && styles.iconControlTextUrgent,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export default function ControlDock({ compact = false, items = [] }) {
  if (!items.length) return null;

  return (
    <View style={[styles.controlDock, compact && styles.controlDockCompact]} accessibilityRole="toolbar">
      {items.map((item, index) => (
        <View key={item.key} style={styles.controlDockItemWrap}>
          {index > 0 ? <View style={styles.controlDockDivider} pointerEvents="none" /> : null}
          <IconControl {...item} />
        </View>
      ))}
    </View>
  );
}
