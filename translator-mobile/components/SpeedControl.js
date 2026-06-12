import { useRef, useCallback, useMemo } from "react";
import { View, Text, PanResponder } from "react-native";
import styles from "../AppStyles";

const MIN_SPEED = 0.5;
const MAX_SPEED = 2.0;

export default function SpeedControl({ speed = 1.0, onSpeedChange, wide = false }) {
  const trackWidthRef = useRef(120);

  const applySpeed = useCallback((locationX) => {
    const width = trackWidthRef.current || 120;
    const ratio = Math.max(0, Math.min(1, locationX / width));
    const next = MIN_SPEED + ratio * (MAX_SPEED - MIN_SPEED);
    onSpeedChange?.(Math.round(next * 10) / 10);
  }, [onSpeedChange]);

  const panResponder = useMemo(
    () => PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (event) => applySpeed(event.nativeEvent.locationX),
      onPanResponderMove: (event) => applySpeed(event.nativeEvent.locationX),
    }),
    [applySpeed],
  );

  const ratio = (speed - MIN_SPEED) / (MAX_SPEED - MIN_SPEED);
  const fillWidth = `${Math.round(ratio * 100)}%`;

  return (
    <View style={[styles.speedControl, wide && styles.speedControlWide]}>
      <Text style={styles.speedControlLabel}>{speed.toFixed(1)}x</Text>
      <View
        style={[styles.speedTrack, wide && styles.speedTrackWide]}
        onLayout={(event) => {
          trackWidthRef.current = event.nativeEvent.layout.width;
        }}
        {...panResponder.panHandlers}
        accessibilityRole="adjustable"
        accessibilityLabel={`Playback speed ${speed.toFixed(1)} times`}
        accessibilityValue={{ min: MIN_SPEED * 10, max: MAX_SPEED * 10, now: Math.round(speed * 10) }}
      >
        <View style={styles.speedTrackBase} />
        <View style={[styles.speedTrackFill, { width: fillWidth }]} />
        <View style={[styles.speedThumb, { left: fillWidth }]} />
      </View>
    </View>
  );
}
