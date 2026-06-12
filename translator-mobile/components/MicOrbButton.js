import { useEffect, useRef } from "react";
import { View, Text, Pressable, ActivityIndicator, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import MicCosmicRing from "./MicCosmicRing";

const GRILLE_BARS = 9;

export default function MicOrbButton({
  onPress,
  disabled = false,
  pressed = false,
  isListening = false,
  isSpeaking = false,
  isArmed = false,
  isOffline = false,
  isConnecting = false,
  isBusy = false,
  isProcessing = false,
  icon = "mic",
  label = "Start",
  hint = "",
  compact = false,
  tiny = false,
  audioLevel = 0,
  accessibilityLabel,
}) {
  const pulse = useRef(new Animated.Value(0)).current;
  const spin = useRef(new Animated.Value(0)).current;
  const grillePulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!isListening) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 720, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 720, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isListening, pulse]);

  useEffect(() => {
    const shouldSpin = (isConnecting && !isArmed) || isProcessing;
    if (!shouldSpin) {
      spin.stopAnimation();
      spin.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration: 850, useNativeDriver: true }),
    );
    loop.start();
    return () => loop.stop();
  }, [isConnecting, isProcessing, isArmed, spin]);

  useEffect(() => {
    if (!isListening) {
      grillePulse.stopAnimation();
      grillePulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(grillePulse, { toValue: 1, duration: 680, useNativeDriver: true }),
        Animated.timing(grillePulse, { toValue: 0, duration: 680, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isListening, grillePulse]);

  const sizeStyle = tiny ? styles.micOrbTiny : compact ? styles.micOrbCompact : styles.micOrb;
  const coreStyle = tiny ? styles.micOrbCoreTiny : compact ? styles.micOrbCoreCompact : styles.micOrbCore;
  const iconSize = tiny ? 30 : compact ? 36 : 44;

  const pulseScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] });
  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.75] });
  const spinRotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const grilleBoost = grillePulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.18] });
  const levelBoost = Math.max(0, Math.min(1, audioLevel));

  const showCosmicRing = isArmed || isListening || isSpeaking;
  const cosmicVariant = isSpeaking ? "bridge" : "listen";

  return (
    <View style={styles.micPanel}>
      <MicCosmicRing visible={showCosmicRing} sizeStyle={sizeStyle} variant={cosmicVariant} />
      {isListening ? (
        <Animated.View
          style={[styles.micOrbHalo, sizeStyle, { opacity: pulseOpacity, transform: [{ scale: pulseScale }] }]}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        />
      ) : null}
      {isListening ? (
        <View style={[styles.micOrbEnergyRim, sizeStyle]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />
      ) : null}
      <Pressable
        onPress={onPress}
        disabled={disabled}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel || label}
        accessibilityState={{ disabled, selected: isArmed || isListening }}
        hitSlop={10}
        style={({ pressed: isPressed }) => [
          styles.micOrbPressable,
          sizeStyle,
          isOffline && styles.micOrbOffline,
          isArmed && styles.micOrbArmed,
          isListening && styles.micOrbListening,
          isSpeaking && styles.micOrbSpeaking,
          isConnecting && styles.micOrbBusy,
          (isPressed || pressed) && styles.micOrbPressed,
          disabled && styles.micOrbDisabled,
        ]}
      >
        <View style={[styles.micOrbOuterRing, sizeStyle]} />
        <View style={[styles.micOrbRing, sizeStyle, isListening && styles.micOrbRingLive]} />
        {((isConnecting && !isArmed) || isProcessing) ? (
          <Animated.View
            style={[styles.micOrbSpin, sizeStyle, { transform: [{ rotate: spinRotate }] }]}
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
          />
        ) : null}
        <View style={[styles.micOrbGrille, coreStyle]}>
          {Array.from({ length: GRILLE_BARS }, (_, index) => {
            const barLevel = 0.55 + levelBoost * (0.35 + (index % 3) * 0.12);
            return (
              <Animated.View
                key={`bar-${index}`}
                style={[
                  styles.micOrbGrilleBar,
                  isListening && styles.micOrbGrilleBarLive,
                  {
                    opacity: 0.45 + (index % 3) * 0.12 + levelBoost * 0.2,
                    transform: isListening
                      ? [{ scaleY: Animated.multiply(grilleBoost, barLevel) }]
                      : undefined,
                  },
                ]}
              />
            );
          })}
        </View>
        <View style={[styles.micOrbCore, coreStyle]}>
          <View style={styles.micOrbWaveLines} pointerEvents="none">
            <View style={[styles.micOrbWaveLine, isListening && styles.micOrbWaveLineLive]} />
            <View style={[styles.micOrbWaveLine, styles.micOrbWaveLineLower, isListening && styles.micOrbWaveLineLive]} />
          </View>
          {isConnecting && !isArmed ? (
            <ActivityIndicator size="large" color="#f8fafc" />
          ) : isSpeaking ? (
            <Ionicons name="volume-high" size={iconSize} color="rgba(233, 213, 255, 0.95)" />
          ) : (
            <Ionicons name={icon} size={iconSize} color="rgba(248, 250, 252, 0.92)" />
          )}
        </View>
        {isListening ? <View style={styles.micOrbRecLed} /> : null}
      </Pressable>
      <Text style={[styles.micOrbLabel, isListening && styles.micOrbLabelLive]}>{label}</Text>
      {hint ? (
        <View style={styles.micOrbHintPill}>
          <Ionicons
            name={isListening ? "radio-outline" : isOffline ? "cloud-offline-outline" : "information-circle-outline"}
            size={12}
            color={isListening ? "#5eead4" : "#67e8f9"}
          />
          <Text style={[styles.micOrbHint, isListening && styles.micOrbHintLive]}>{hint}</Text>
        </View>
      ) : null}
    </View>
  );
}
