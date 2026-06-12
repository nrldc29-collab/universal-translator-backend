import { View, Text, Pressable } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { modeChipA11y, modeChipLabel } from "../constants/productVoice";

export default function RouteModeStrip({
  sourceLabel = "English",
  targetLabel = "French",
  twoWay = true,
  speakerLabel = "",
  onToggleMode,
}) {
  return (
    <View style={styles.routeModeStripWrap}>
      <LinearGradient
        colors={["rgba(103, 232, 249, 0.2)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.routeModeStripShine}
        pointerEvents="none"
      />
      <View style={styles.routeModeStrip} accessibilityRole="text">
        <Ionicons name="git-network-outline" size={12} color="rgba(103, 232, 249, 0.62)" />
        <Text numberOfLines={1} style={styles.routeModeText}>
          {twoWay ? `${sourceLabel} ↔ ${targetLabel}` : `${sourceLabel} → ${targetLabel}`}
        </Text>
        <Pressable
          onPress={onToggleMode}
          disabled={!onToggleMode}
          accessibilityRole="button"
          accessibilityLabel={modeChipA11y(twoWay)}
          style={({ pressed }) => [
            styles.routeModeChip,
            twoWay && styles.routeModeChipActive,
            !onToggleMode && styles.routeModeChipDisabled,
            pressed && onToggleMode && styles.routeModeChipPressed,
          ]}
        >
          <Ionicons name={twoWay ? "people" : "arrow-forward"} size={12} color={twoWay ? "#5eead4" : "#94a3b8"} />
          <Text style={[styles.routeModeChipText, twoWay && styles.routeModeChipTextActive]}>
            {modeChipLabel(twoWay)}
          </Text>
        </Pressable>
      </View>
      {speakerLabel ? (
        <View style={styles.routeModeSpeakerPill}>
          <Ionicons name="person" size={11} color="#67e8f9" />
          <Text style={styles.routeModeSpeaker}>{speakerLabel}</Text>
        </View>
      ) : null}
    </View>
  );
}
