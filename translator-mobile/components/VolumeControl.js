import { useRef, useCallback, useMemo } from "react";
import { View, Pressable, PanResponder } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function VolumeControl({ volume = 0.8, onVolumeChange, compact = false, wide = false }) {
  const trackWidthRef = useRef(72);
  const muted = volume <= 0.05;

  const applyVolume = useCallback((locationX) => {
    const width = trackWidthRef.current || 72;
    const ratio = Math.max(0, Math.min(1, locationX / width));
    onVolumeChange?.(Math.max(0.05, ratio));
  }, [onVolumeChange]);

  const panResponder = useMemo(
    () => PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (event) => applyVolume(event.nativeEvent.locationX),
      onPanResponderMove: (event) => applyVolume(event.nativeEvent.locationX),
    }),
    [applyVolume],
  );

  const iconName = muted ? "volume-mute" : volume < 0.45 ? "volume-low" : "volume-high";
  const fillWidth = `${Math.round(volume * 100)}%`;

  return (
    <View style={[styles.volumeControl, compact && styles.volumeControlCompact, wide && styles.volumeControlWide]}>
      <Pressable
        onPress={() => onVolumeChange?.(muted ? 0.8 : 0.05)}
        style={({ pressed }) => [styles.volumeToggle, pressed && styles.volumeTogglePressed]}
        accessibilityRole="button"
        accessibilityLabel={muted ? "Unmute playback" : "Mute playback"}
      >
        <Ionicons name={iconName} size={16} color={muted ? "#f87171" : "rgba(148, 163, 184, 0.75)"} />
      </Pressable>
      <View
        style={[styles.volumeTrack, wide && styles.volumeTrackWide]}
        onLayout={(event) => {
          trackWidthRef.current = event.nativeEvent.layout.width;
        }}
        {...panResponder.panHandlers}
        accessibilityRole="adjustable"
        accessibilityLabel={`Playback volume ${Math.round(volume * 100)} percent`}
        accessibilityValue={{ min: 5, max: 100, now: Math.round(volume * 100) }}
      >
        <View style={styles.volumeTrackBase} />
        <View style={[styles.volumeTrackFill, !muted && volume > 0.5 && styles.volumeTrackFillHot, { width: fillWidth }]} />
        <View style={[styles.volumeThumb, !muted && styles.volumeThumbLive, { left: fillWidth }]} />
      </View>
    </View>
  );
}
