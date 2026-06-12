import { useEffect, useRef } from "react";
import { Animated } from "react-native";

export default function LaneLiveText({
  text = "",
  placeholder = "",
  style,
  placeholderStyle,
  numberOfLines = 4,
}) {
  const opacity = useRef(new Animated.Value(1)).current;
  const displayText = text || placeholder;
  const isPlaceholder = !text;

  useEffect(() => {
    if (!text) {
      opacity.setValue(1);
      return undefined;
    }
    opacity.setValue(0.35);
    Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }).start();
    return undefined;
  }, [text, opacity]);

  return (
    <Animated.Text
      numberOfLines={numberOfLines}
      accessibilityLiveRegion="polite"
      style={[isPlaceholder ? placeholderStyle : style, !isPlaceholder && { opacity }]}
    >
      {displayText}
    </Animated.Text>
  );
}
