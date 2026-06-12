import { useEffect, useRef } from "react";
import { View, Text, Animated, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { turnRailHeader, turnChipA11y } from "../constants/productVoice";

function TurnChip({ turn, active = false, delayMs = 0, onPress, exiting = false }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(8)).current;

  useEffect(() => {
    if (exiting) {
      Animated.parallel([
        Animated.timing(opacity, { toValue: 0, duration: 160, useNativeDriver: true }),
        Animated.timing(translateY, { toValue: 8, duration: 160, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    opacity.setValue(0);
    translateY.setValue(8);
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 240, delay: delayMs, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, speed: 18, bounciness: 4, delay: delayMs, useNativeDriver: true }),
    ]).start();
    return undefined;
  }, [turn.id, delayMs, exiting, opacity, translateY]);

  const certRequired = turn.certStep === "required";
  const certAdvisory = turn.certStep === "advisory" || turn.nativeListen;

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole="button"
      accessibilityLabel={turnChipA11y({ ...turn, certStep: certRequired ? "required" : certAdvisory ? "advisory" : turn.certStep })}
    >
      <Animated.View
        style={[
          styles.turnChip,
          turn.clarify && styles.turnChipWarning,
          certRequired && styles.turnChipCertRequired,
          active && styles.turnChipActive,
          { opacity, transform: [{ translateY }] },
        ]}
      >
        <View
          style={[
            styles.turnChipAccent,
            active && styles.turnChipAccentActive,
            (turn.clarify || certAdvisory) && styles.turnChipAccentWarning,
            certRequired && { backgroundColor: "#fb923c" },
          ]}
          pointerEvents="none"
        />
        {certAdvisory ? (
          <View style={styles.turnChipCertBadge} pointerEvents="none">
            <Ionicons name={certRequired ? "shield-checkmark" : "ear"} size={10} color="#fbbf24" />
          </View>
        ) : null}
        {active ? (
          <View style={styles.turnChipLiveDot} pointerEvents="none" />
        ) : null}
        <Text style={styles.turnChipSpeaker} numberOfLines={1}>{turn.speakerLabel}</Text>
        {turn.sourceText ? (
          <Text numberOfLines={2} style={styles.turnChipSource}>{turn.sourceText}</Text>
        ) : null}
        {turn.translatedText ? (
          <>
            <View style={styles.turnChipBridgeRow}>
              <Ionicons name="git-network-outline" size={10} color="#5eead4" />
              <View style={styles.turnChipBridgeLine} />
            </View>
            <Text numberOfLines={2} style={styles.turnChipBridged}>{turn.translatedText}</Text>
          </>
        ) : null}
      </Animated.View>
    </Pressable>
  );
}

export default function TurnHistoryRail({ turns = [], onTurnPress }) {
  const { mounted, style } = useAnimatedPresence(turns.length > 0, { initialOffset: 8, duration: 220, exitDuration: 160 });

  if (!mounted) return null;

  const visibleTurns = turns.slice(-3);

  return (
    <Animated.View style={[styles.turnRailWrap, style]}>
      <View style={styles.turnRailHeader}>
        <Ionicons name="git-network-outline" size={12} color="rgba(148, 163, 184, 0.72)" />
        <Text style={styles.turnRailHeaderText}>{turnRailHeader()}</Text>
      </View>
      <View style={styles.turnRail}>
        {visibleTurns.map((turn, index, list) => (
          <TurnChip
            key={turn.id}
            turn={turn}
            active={index === list.length - 1}
            delayMs={index * 55}
            onPress={onTurnPress ? () => onTurnPress(turn) : undefined}
          />
        ))}
      </View>
    </Animated.View>
  );
}
