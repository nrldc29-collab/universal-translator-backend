import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { routeCaptions } from "../constants/productVoice";

function RouteBridgeHub({ onPress, isBridging = false }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isBridging) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isBridging, pulse]);

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.06] });
  const glowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.85] });

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={isBridging ? "Conversation bridge active — tap to swap languages" : "Swap source and target languages"}
      hitSlop={8}
      style={({ pressed }) => [pressed && styles.routeCenterPressed]}
    >
      <Animated.View
        style={[
          styles.routeCenter,
          isBridging && styles.routeCenterBridging,
          isBridging && { transform: [{ scale }], shadowOpacity: glowOpacity },
        ]}
      >
        <Ionicons
          name={isBridging ? "git-network-outline" : "swap-horizontal"}
          size={19}
          color="#0f172a"
        />
      </Animated.View>
    </Pressable>
  );
}

export default function LanguageRouteBand({
  sourceFlag = "🌐",
  targetFlag = "🌐",
  sourceLabel = "English",
  targetLabel = "French",
  sourceActive = false,
  targetActive = false,
  twoWay = true,
  isBridging = false,
  compact = false,
  onPickSource,
  onPickTarget,
  onSwap,
}) {
  const captions = routeCaptions(twoWay);
  return (
    <View style={[styles.routeBand, compact && styles.routeBandCompact]}>
      <LinearGradient
        colors={["rgba(103, 232, 249, 0.35)", "rgba(45, 212, 191, 0.15)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.routeBandShine}
        pointerEvents="none"
      />
      <Pressable
        onPress={onPickSource}
        style={({ pressed }) => [
          styles.routeSide,
          styles.routeSideSource,
          sourceActive && styles.routeSideActive,
          compact && styles.routeSideCompact,
          pressed && styles.routeSidePressed,
        ]}
        accessibilityRole="button"
        accessibilityLabel={`You speak ${sourceLabel}. Tap to change.`}
      >
        <View style={styles.routeSideContent}>
          <Text style={styles.routeCaption}>{captions.source}</Text>
          <View style={styles.routeSideRow}>
            <Text style={styles.routeFlag}>{sourceFlag}</Text>
            <Text
              numberOfLines={1}
              adjustsFontSizeToFit
              style={[styles.routeLanguage, sourceActive && styles.routeLanguageActive]}
            >
              {sourceLabel}
            </Text>
            <Ionicons name="chevron-down" size={14} color="#94a3b8" />
          </View>
        </View>
      </Pressable>
      <RouteBridgeHub onPress={onSwap} isBridging={isBridging} />
      <Pressable
        onPress={onPickTarget}
        style={({ pressed }) => [
          styles.routeSide,
          styles.routeSideTarget,
          targetActive && styles.routeSideActive,
          compact && styles.routeSideCompact,
          pressed && styles.routeSidePressed,
        ]}
        accessibilityRole="button"
        accessibilityLabel={`${captions.target}: ${targetLabel}. Tap to change.`}
      >
        <View style={styles.routeSideContent}>
          <Text style={[styles.routeCaption, styles.routeCaptionTarget]}>{captions.target}</Text>
          <View style={styles.routeSideRow}>
            <Text style={styles.routeFlag}>{targetFlag}</Text>
            <Text
              numberOfLines={1}
              adjustsFontSizeToFit
              style={[styles.routeLanguage, targetActive && styles.routeLanguageActive]}
            >
              {targetLabel}
            </Text>
            <Ionicons name="chevron-down" size={14} color="#94a3b8" />
          </View>
        </View>
      </Pressable>
    </View>
  );
}
