import { useEffect, useRef } from "react";
import { View, Animated } from "react-native";
import styles from "../AppStyles";

const BAR_COUNT = 7;

function MeterBar({ active, delayMs, level = 0 }) {
  const animatedLevel = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    if (!active) {
      animatedLevel.stopAnimation();
      animatedLevel.setValue(0.28);
      return undefined;
    }
    const target = 0.28 + Math.max(0, Math.min(1, level)) * (0.45 + (delayMs % 3) * 0.1);
    Animated.timing(animatedLevel, {
      toValue: target,
      duration: 90,
      useNativeDriver: true,
    }).start();
    return undefined;
  }, [active, delayMs, level, animatedLevel]);

  return (
    <Animated.View
      style={[
        styles.voiceMeterBar,
        active && styles.voiceMeterBarActive,
        { transform: [{ scaleY: animatedLevel }] },
      ]}
    />
  );
}

export default function VoiceMeter({ active = false, idle = false, level = 0 }) {
  const showBars = active || idle;
  return (
    <View style={[styles.voiceMeter, !showBars && styles.voiceMeterMuted, idle && !active && styles.voiceMeterIdle]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {Array.from({ length: BAR_COUNT }, (_, index) => (
        <MeterBar
          key={`meter-${index}`}
          active={active}
          delayMs={index * 90}
          level={active ? level * (0.75 + (index % 4) * 0.08) : idle ? 0.18 + (index % 3) * 0.04 : 0}
        />
      ))}
    </View>
  );
}
