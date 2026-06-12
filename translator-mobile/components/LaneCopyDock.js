import { useEffect, useRef, useState } from "react";
import { View, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";

export default function LaneCopyDock({
  visible = false,
  onShare,
  onCopy,
  tone = "source",
}) {
  const { mounted, style: presenceStyle } = useAnimatedPresence(visible, { initialOffset: 10, axis: "x", duration: 220, exitDuration: 160 });
  const copyFlash = useRef(new Animated.Value(0)).current;
  const [copyIcon, setCopyIcon] = useState("copy-outline");

  useEffect(() => {
    if (!visible) setCopyIcon("copy-outline");
  }, [visible]);

  const handleCopy = () => {
    onCopy?.();
    setCopyIcon("checkmark");
    copyFlash.setValue(0);
    Animated.sequence([
      Animated.timing(copyFlash, { toValue: 1, duration: 140, useNativeDriver: false }),
      Animated.timing(copyFlash, { toValue: 0, duration: 520, useNativeDriver: false }),
    ]).start(() => setCopyIcon("copy-outline"));
  };

  if (!mounted) return null;

  const iconColor = tone === "target" ? "#bbf7d0" : "#cbd5e1";
  const copyBorderColor = copyFlash.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(148, 163, 184, 0.2)", tone === "target" ? "rgba(52, 211, 153, 0.65)" : "rgba(103, 232, 249, 0.65)"],
  });
  const copyBackgroundColor = copyFlash.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(15, 23, 42, 0.7)", tone === "target" ? "rgba(6, 46, 42, 0.92)" : "rgba(15, 35, 55, 0.92)"],
  });

  return (
    <Animated.View
      style={[styles.laneCopyDock, presenceStyle]}
      accessibilityRole="toolbar"
      accessibilityLabel="Share and copy bridged conversation"
    >
      <View style={styles.laneActionBtn}>
        <Pressable
          onPress={onShare}
          style={({ pressed }) => [styles.laneActionBtnInner, pressed && styles.laneActionBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Share bridged text"
        >
          <Ionicons name="share-outline" size={16} color={iconColor} />
        </Pressable>
      </View>
      <Animated.View style={[styles.laneActionBtn, { borderColor: copyBorderColor, backgroundColor: copyBackgroundColor }]}>
        <Pressable
          onPress={handleCopy}
          style={({ pressed }) => [styles.laneActionBtnInner, pressed && styles.laneActionBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Copy bridged text"
        >
          <Ionicons name={copyIcon} size={16} color={copyIcon === "checkmark" ? "#34d399" : iconColor} />
        </Pressable>
      </Animated.View>
    </Animated.View>
  );
}
