import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { emptyStateCopy } from "../constants/productVoice";

function TipRow({ icon, text }) {
  return (
    <View style={styles.emptyStateTip}>
      <Ionicons name={icon} size={14} color="rgba(45, 212, 191, 0.7)" />
      <Text style={styles.emptyStateTipText}>{text}</Text>
    </View>
  );
}

export default function EmptyTranscriptState({
  visible = true,
  isOffline = false,
  isPaused = false,
  isStreaming = false,
  isInterpreterActive = false,
  twoWay = true,
  onStart,
  onConnect,
}) {
  const { mounted, style: presenceStyle } = useAnimatedPresence(visible, { initialOffset: 10, duration: 260, exitDuration: 180 });
  const iconPulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible || !isStreaming) {
      iconPulse.stopAnimation();
      iconPulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(iconPulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(iconPulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [visible, isStreaming, iconPulse]);

  if (!mounted) return null;

  const { title, description } = emptyStateCopy({
    isOffline,
    isStreaming,
    isPaused,
    isInterpreterActive,
    twoWay,
  });

  const iconScale = iconPulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] });

  return (
    <Animated.View style={[styles.emptyState, isOffline && styles.emptyStateOffline, presenceStyle]}>
      <Animated.View style={[styles.emptyStateIcon, isOffline && styles.emptyStateIconOffline, isStreaming && { transform: [{ scale: iconScale }] }]}>
        <Ionicons
          name={isOffline ? "cloud-offline-outline" : isStreaming ? "radio-outline" : isPaused ? "pause-circle-outline" : "git-network-outline"}
          size={26}
          color={isOffline ? "#67e8f9" : isPaused ? "#fbbf24" : "#5eead4"}
        />
      </Animated.View>
      <Text style={styles.emptyStateTitle}>{title}</Text>
      <Text style={styles.emptyStateDescription}>{description}</Text>
      <View style={styles.emptyStateTips}>
        {isOffline ? (
          <>
            <TipRow icon="wifi-outline" text="Phone and PC on the same network" />
            <TipRow icon="link-outline" text="Tap Link bridge below or use Safari HTTPS for mic" />
            <TipRow icon="mic-outline" text="One tap opens the conversation bridge" />
          </>
        ) : (
          <>
            <TipRow icon="language-outline" text="Pick the two languages you're bridging" />
            <TipRow icon="people-outline" text={twoWay ? "Together mode — either person can speak" : "Speak naturally in your language"} />
            <TipRow icon="volume-high-outline" text="Anai bridges meaning out loud, automatically" />
            {isInterpreterActive ? (
              <>
                <TipRow icon="ear-outline" text="Follow native-speaker hints before relying on voice" />
                <TipRow icon="git-network-outline" text="Tap meaning-check chips when understanding looks uncertain" />
              </>
            ) : null}
          </>
        )}
      </View>
      {isOffline && onConnect ? (
        <Pressable
          onPress={onConnect}
          style={({ pressed }) => [styles.emptyStateCta, pressed && styles.emptyStateCtaPressed]}
          accessibilityRole="button"
          accessibilityLabel="Link conversation bridge"
        >
          <Ionicons name="link" size={15} color="#07131f" />
          <Text style={styles.emptyStateCtaText}>Link bridge</Text>
        </Pressable>
      ) : null}
      {!isOffline && !isInterpreterActive && onStart ? (
        <Pressable
          onPress={onStart}
          style={({ pressed }) => [styles.emptyStateCta, pressed && styles.emptyStateCtaPressed]}
          accessibilityRole="button"
          accessibilityLabel="Open the conversation bridge"
        >
          <Ionicons name="mic" size={15} color="#07131f" />
          <Text style={styles.emptyStateCtaText}>Open bridge</Text>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}
