import { View, Text, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { compactRepairLabel } from "../utils/brainPlan";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { brainPanelTitle } from "../constants/productVoice";

export default function BrainRepairPanel({
  visible = false,
  message = "",
  repairOptions = [],
  highlightTerms = [],
  riskScore = null,
  onRepairPress,
  panelStyle = null,
  title = brainPanelTitle(),
}) {
  const hasContent = Boolean(
    message
    || repairOptions.length
    || highlightTerms.length
    || (typeof riskScore === "number" && riskScore > 0),
  );
  const { mounted, style } = useAnimatedPresence(visible && hasContent, { initialOffset: 6, duration: 200, exitDuration: 160 });

  if (!mounted) return null;

  return (
    <View style={[styles.brainRepairPanel, panelStyle, style]} accessibilityRole="summary">
      <View style={styles.brainRepairHeader}>
        <Ionicons name="git-network-outline" size={12} color="#67e8f9" />
        <Text style={styles.brainRepairTitle}>{title}</Text>
        {typeof riskScore === "number" && riskScore > 0 ? (
          <Text style={styles.brainRepairRisk}>{Math.round(riskScore * 100)}% risk</Text>
        ) : null}
      </View>
      {message ? <Text style={styles.brainRepairMessage}>{message}</Text> : null}
      {highlightTerms.length ? (
        <View style={styles.brainRepairChipRow}>
          {highlightTerms.slice(0, 4).map((term) => (
            <View key={term} style={styles.brainRepairChip}>
              <Text style={styles.brainRepairChipText}>{term}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {repairOptions.length ? (
        <View style={styles.brainRepairActions}>
          {repairOptions.slice(0, 3).map((option, index) => (
            <Pressable
              key={`${option.type || "repair"}-${index}`}
              onPress={() => onRepairPress?.(option)}
              style={({ pressed }) => [styles.brainRepairAction, pressed && styles.brainRepairActionPressed]}
              accessibilityRole="button"
              accessibilityLabel={compactRepairLabel(option)}
            >
              <Text style={styles.brainRepairActionText}>{compactRepairLabel(option)}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}
