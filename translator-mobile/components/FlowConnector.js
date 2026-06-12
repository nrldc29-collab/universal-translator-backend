import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import styles from "../AppStyles";

export default function FlowConnector({ active = false }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!active) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, pulse]);

  const backgroundColor = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(45, 212, 191, 0.35)", "rgba(103, 232, 249, 0.85)"],
  });
  const width = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [14, 20],
  });

  const lineOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.25, 0.85],
  });

  return (
    <View style={styles.flowConnectorWrap} pointerEvents="none">
      <Animated.View style={[styles.flowConnectorLine, active && { opacity: lineOpacity }]} />
      <View style={styles.flowConnectorHubWrap}>
        <Animated.View
          style={[
            styles.flowConnector,
            active && styles.flowConnectorActive,
            active && { backgroundColor, width },
          ]}
        />
        <Text style={[styles.flowConnectorHub, active && styles.flowConnectorHubActive]} accessibilityElementsHidden>⬡</Text>
      </View>
      <Animated.View style={[styles.flowConnectorLine, active && { opacity: lineOpacity }]} />
    </View>
  );
}
