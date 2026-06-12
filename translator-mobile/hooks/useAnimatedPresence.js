import { useEffect, useRef, useState } from "react";
import { Animated } from "react-native";

export function useAnimatedPresence(
  visible,
  {
    duration = 240,
    exitDuration = 180,
    delay = 0,
    initialOffset = 8,
    axis = "y",
  } = {},
) {
  const opacity = useRef(new Animated.Value(visible ? 1 : 0)).current;
  const offset = useRef(new Animated.Value(visible ? 0 : initialOffset)).current;
  const [mounted, setMounted] = useState(visible);
  const mountedRef = useRef(mounted);
  mountedRef.current = mounted;

  useEffect(() => {
    if (visible) {
      setMounted((current) => (current ? current : true));
      offset.setValue(initialOffset);
      const enter = Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration, delay, useNativeDriver: true }),
        Animated.spring(offset, { toValue: 0, speed: 18, bounciness: 4, delay, useNativeDriver: true }),
      ]);
      enter.start();
      return () => enter.stop();
    }
    if (!mountedRef.current) return undefined;
    const exit = Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: exitDuration, useNativeDriver: true }),
      Animated.timing(offset, { toValue: initialOffset, duration: exitDuration, useNativeDriver: true }),
    ]);
    exit.start(({ finished }) => {
      if (finished) setMounted(false);
    });
    return () => exit.stop();
  }, [visible, duration, exitDuration, delay, initialOffset, opacity, offset]);

  const transform = axis === "x" ? [{ translateX: offset }] : [{ translateY: offset }];
  return { mounted, style: { opacity, transform } };
}
