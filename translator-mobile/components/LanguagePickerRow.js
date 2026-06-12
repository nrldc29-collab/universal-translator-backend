import { useEffect, useRef } from "react";
import { Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import pickerStyles from "./LanguagePickerModal.styles";

export default function LanguagePickerRow({
  language,
  active = false,
  isSource = false,
  index = 0,
  visible = false,
  onSelect,
}) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(8)).current;

  useEffect(() => {
    if (!visible) {
      opacity.setValue(0);
      translateY.setValue(8);
      return undefined;
    }
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 200, delay: Math.min(index * 36, 360), useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 3, delay: Math.min(index * 36, 360), useNativeDriver: true }),
    ]).start();
    return undefined;
  }, [visible, index, opacity, translateY]);

  return (
    <Animated.View style={{ opacity, transform: [{ translateY }] }}>
      <Pressable
        onPress={() => onSelect(language.code)}
        style={({ pressed }) => [
          pickerStyles.row,
          active && (isSource ? pickerStyles.rowActiveSource : pickerStyles.rowActiveTarget),
          pressed && pickerStyles.rowPressed,
        ]}
        accessibilityRole="button"
        accessibilityState={{ selected: active }}
        accessibilityLabel={language.label}
      >
        <Text style={pickerStyles.flag}>{language.flag}</Text>
        <Text style={[pickerStyles.label, active && pickerStyles.labelActive]}>{language.label}</Text>
        {active ? <Ionicons name="checkmark-circle" size={20} color="#22d3ee" /> : null}
      </Pressable>
    </Animated.View>
  );
}
