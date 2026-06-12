import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function LaneHeader({
  flag = "🌐",
  label = "",
  isLive = false,
  isBusy = false,
  tone = "source",
  attention = "",
}) {
  const livePulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isLive) {
      livePulse.stopAnimation();
      livePulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(livePulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(livePulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isLive, livePulse]);

  const dotOpacity = livePulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 1] });

  return (
    <View style={styles.laneHeader}>
      <View style={styles.laneLabelRow}>
        <Text style={styles.laneLabelFlag}>{flag}</Text>
        <Text style={[styles.laneLabel, styles.laneLabelFlex, isLive && styles.laneLabelLive]}>
          {label}
        </Text>
      </View>
      {attention === "required" ? (
        <View style={[styles.laneAttentionBadge, styles.laneAttentionBadgeRequired]}>
          <Ionicons name="shield-checkmark" size={10} color="#fb923c" />
          <Text style={styles.laneAttentionBadgeText}>VERIFY</Text>
        </View>
      ) : null}
      {attention === "advisory" ? (
        <View style={[styles.laneAttentionBadge, styles.laneAttentionBadgeAdvisory]}>
          <Ionicons name="ear" size={10} color="#fbbf24" />
          <Text style={styles.laneAttentionBadgeText}>LISTEN</Text>
        </View>
      ) : null}
      {isBusy ? (
        <View style={[styles.laneStatusBadge, styles.laneStatusBadgeBusy]}>
          <Text style={[styles.laneStatusBadgeText, styles.laneStatusBadgeTextBusy]}>FLOW</Text>
        </View>
      ) : null}
      {isLive && !isBusy && !attention ? (
        <View style={[styles.laneStatusBadge, tone === "target" ? styles.laneStatusBadgeTarget : styles.laneStatusBadgeSource]}>
          <Animated.View style={[styles.laneStatusBadgeDot, { opacity: dotOpacity }]} />
          <Text style={styles.laneStatusBadgeText}>LIVE</Text>
        </View>
      ) : null}
    </View>
  );
}
