import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import setupStyles from "./WelcomeSetupModal.styles";

export default function SetupHeroIcon() {
  const pulse = useRef(new Animated.Value(0)).current;
  const haloScale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 1400, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 1400, useNativeDriver: true }),
      ]),
    );
    const haloLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(haloScale, { toValue: 1.08, duration: 1800, useNativeDriver: true }),
        Animated.timing(haloScale, { toValue: 1, duration: 1800, useNativeDriver: true }),
      ]),
    );
    pulseLoop.start();
    haloLoop.start();
    return () => {
      pulseLoop.stop();
      haloLoop.stop();
    };
  }, [pulse, haloScale]);

  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.85] });

  return (
    <Animated.View style={[setupStyles.heroIconHalo, { transform: [{ scale: haloScale }] }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Animated.View style={[setupStyles.heroIconRingPulse, { opacity: ringOpacity }]} />
      <Animated.View style={setupStyles.heroIconRing}>
        <Ionicons name="git-network-outline" size={34} color="#67e8f9" />
      </Animated.View>
    </Animated.View>
  );
}
