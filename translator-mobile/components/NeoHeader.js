import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import VolumeControl from "./VolumeControl";
import NeoBrandMark from "./NeoBrandMark";
import { neoConnectionBadge } from "../constants/productVoice";

export default function NeoHeader({
  isConnected = false,
  isConnecting = false,
  isListening = false,
  isSpeaking = false,
  statusLabel = "Offline",
  buildTag = "",
  volume = 0.8,
  onVolumeChange,
  compact = false,
  onHelp,
  onAssistant,
  assistantEnabled = true,
  onShare,
  shareEnabled = true,
  onSettings,
  onStatusPress,
  statusColor = "#94a3b8",
  focusedMode = false,
}) {
  const pulse = useRef(new Animated.Value(0)).current;
  const connLabel = neoConnectionBadge({ isConnecting, isConnected });
  const shouldPulse = isConnected || isConnecting;

  useEffect(() => {
    if (!shouldPulse) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const duration = isSpeaking ? 450 : isListening ? 500 : isConnecting ? 650 : 900;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [shouldPulse, isListening, isSpeaking, isConnecting, pulse]);

  const dotScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, isListening || isSpeaking ? 1.45 : 1.25] });
  const dotOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.75, 1] });

  return (
    <View style={styles.neoHeader}>
      <View style={styles.neoHeaderSide}>
        {!focusedMode && onVolumeChange ? (
          <VolumeControl volume={volume} onVolumeChange={onVolumeChange} compact={compact} />
        ) : (
          <View style={styles.neoHeaderSpacer} />
        )}
      </View>

      <View style={[styles.neoBrand, isConnected && styles.neoBrandLive]}>
        <NeoBrandMark live={isConnected} compact subline={isConnected ? "BRIDGE" : ""} />
        <Pressable
          onPress={onStatusPress}
          disabled={!onStatusPress}
          style={({ pressed }) => [styles.neoStatusBlock, pressed && onStatusPress && styles.neoStatusRowPressed]}
          accessibilityRole="button"
          accessibilityLabel={
            isConnected
              ? `Bridge ${connLabel}, ${statusLabel}. Tap to disconnect`
              : `Bridge ${connLabel}. Tap to link bridge`
          }
        >
          <View style={styles.neoStatusRow}>
            <Animated.View
              style={[
                styles.neoConnDot,
                isConnected && styles.neoConnDotOnline,
                isConnecting && styles.neoConnDotConnecting,
                !isConnected && !isConnecting && styles.neoConnDotOffline,
                shouldPulse && { opacity: dotOpacity, transform: [{ scale: dotScale }] },
              ]}
            />
            <Text style={[styles.neoConnLabel, { color: statusColor }]}>{connLabel}</Text>
            {buildTag ? <Text style={styles.neoBuildStamp}>{buildTag}</Text> : null}
          </View>
          {isConnected && statusLabel ? (
            <Text numberOfLines={1} style={styles.neoStatusDetail}>{statusLabel}</Text>
          ) : null}
        </Pressable>
      </View>

      <View style={[styles.neoHeaderSide, styles.neoHeaderSideRight]}>
        <Pressable
          onPress={onHelp}
          style={({ pressed }) => [styles.neoIconBtn, pressed && styles.neoIconBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Help"
        >
          <View style={styles.neoIconBtnInner}>
            <Ionicons name="help-circle-outline" size={17} color="#e2e8f0" />
          </View>
        </Pressable>
        {onAssistant ? (
          <Pressable
            onPress={assistantEnabled ? onAssistant : undefined}
            disabled={!assistantEnabled}
            style={({ pressed }) => [
              styles.neoIconBtn,
              !assistantEnabled && styles.neoIconBtnDisabled,
              pressed && assistantEnabled && styles.neoIconBtnPressed,
            ]}
            accessibilityRole="button"
            accessibilityLabel="Open NAIA assistant"
            accessibilityState={{ disabled: !assistantEnabled }}
          >
            <View style={[styles.neoIconBtnInner, assistantEnabled && isConnected && styles.neoIconBtnInnerLive]}>
              <Ionicons name="sparkles-outline" size={17} color={assistantEnabled && isConnected ? "#a7f3d0" : "#e2e8f0"} />
            </View>
          </Pressable>
        ) : null}
        {onShare ? (
          <Pressable
            onPress={shareEnabled ? onShare : undefined}
            disabled={!shareEnabled}
            style={({ pressed }) => [
              styles.neoIconBtn,
              !shareEnabled && styles.neoIconBtnDisabled,
              pressed && shareEnabled && styles.neoIconBtnPressed,
            ]}
            accessibilityRole="button"
            accessibilityLabel="Share session"
            accessibilityState={{ disabled: !shareEnabled }}
          >
            <View style={styles.neoIconBtnInner}>
              <Ionicons name="share-outline" size={17} color="#e2e8f0" />
            </View>
          </Pressable>
        ) : null}
        <Pressable
          onPress={onSettings}
          style={({ pressed }) => [styles.neoIconBtn, pressed && styles.neoIconBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Settings"
        >
          <View style={[styles.neoIconBtnInner, isConnected && styles.neoIconBtnInnerLive]}>
            <Ionicons name="settings-outline" size={17} color={isConnected ? "#a7f3d0" : "#e2e8f0"} />
          </View>
        </Pressable>
      </View>
    </View>
  );
}
