import { useEffect, useRef } from "react";
import { StyleSheet, Animated, Easing, ViewStyle } from "react-native";

interface AnimatedCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  delay?: number;
}

export default function AnimatedCard({ children, style, delay = 0 }: AnimatedCardProps) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: 300,
        delay,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(translateY, {
        toValue: 0,
        duration: 300,
        delay,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    ]).start();
  }, [delay, opacity, translateY]);

  return (
    <Animated.View
      style={[
        styles.card,
        style,
        {
          opacity,
          transform: [{ translateY }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#07111f',
    borderRadius: 22,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.16)',
    shadowColor: '#22d3ee',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 5,
  },
});