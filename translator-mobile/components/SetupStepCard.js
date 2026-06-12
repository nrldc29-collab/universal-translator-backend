import { useEffect, useRef } from "react";
import { Animated } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import setupStyles from "./WelcomeSetupModal.styles";

export default function SetupStepCard({ active = false, children }) {
  const opacity = useRef(new Animated.Value(active ? 1 : 0.92)).current;
  const translateY = useRef(new Animated.Value(active ? 0 : 6)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, { toValue: active ? 1 : 0.92, duration: 260, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: active ? 0 : 6, speed: 18, bounciness: active ? 4 : 0, useNativeDriver: true }),
    ]).start();
  }, [active, opacity, translateY]);

  return (
    <Animated.View
      style={[
        setupStyles.card,
        active && setupStyles.cardActive,
        { opacity, transform: [{ translateY }] },
      ]}
    >
      <LinearGradient
        colors={["rgba(103, 232, 249, 0.45)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={setupStyles.cardShine}
        pointerEvents="none"
      />
      {children}
    </Animated.View>
  );
}
