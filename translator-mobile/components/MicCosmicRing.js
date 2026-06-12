import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import styles from "../AppStyles";

export default function MicCosmicRing({ visible = false, sizeStyle, variant = "listen" }) {
  const bridging = variant === "bridge";
  const spin = useRef(new Animated.Value(0)).current;
  const spinReverse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) {
      spin.stopAnimation();
      spinReverse.stopAnimation();
      spin.setValue(0);
      spinReverse.setValue(0);
      return undefined;
    }
    const forward = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration: 9000, useNativeDriver: true }),
    );
    const reverse = Animated.loop(
      Animated.timing(spinReverse, { toValue: 1, duration: 14000, useNativeDriver: true }),
    );
    forward.start();
    reverse.start();
    return () => {
      forward.stop();
      reverse.stop();
    };
  }, [visible, spin, spinReverse]);

  if (!visible) return null;

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const rotateReverse = spinReverse.interpolate({ inputRange: [0, 1], outputRange: ["360deg", "0deg"] });

  return (
    <>
      <Animated.View
        style={[
          styles.micCosmicRingOuter,
          bridging && styles.micCosmicRingOuterBridge,
          sizeStyle,
          { transform: [{ rotate }] },
        ]}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
      <Animated.View
        style={[
          styles.micCosmicRingInner,
          bridging && styles.micCosmicRingInnerBridge,
          sizeStyle,
          { transform: [{ rotate: rotateReverse }] },
        ]}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
    </>
  );
}
