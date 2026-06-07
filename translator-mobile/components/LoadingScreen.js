import { useEffect, useRef } from "react";
import { View, Text, ActivityIndicator, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";

export default function LoadingScreen({ message = "Preparing your interpreter…" }) {
  const pulse = useRef(new Animated.Value(1)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(textOpacity, { toValue: 1, duration: 500, delay: 200, useNativeDriver: true }).start();
  }, [textOpacity]);

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1.06, duration: 1200, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 1200, useNativeDriver: true }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, [pulse]);

  return (
    <View style={styles.loadingScreen} accessibilityRole="progressbar" accessibilityLabel={message}>
      <View style={styles.loadingBrandWrap}>
        <Animated.View style={[styles.loadingIconRing, { transform: [{ scale: pulse }] }]}>
          <Ionicons name="language" size={32} color="#22d3ee" />
        </Animated.View>
        <View style={styles.loadingBrandRow}>
          <Text style={styles.loadingBrandMark}>AN</Text>
          <Text style={styles.loadingBrandAccent}>AI</Text>
        </View>
        <Text style={styles.loadingBrandSub}>TRANSLATOR</Text>
      </View>
      <ActivityIndicator size="large" color="#22d3ee" />
      <Animated.Text style={[styles.loadingScreenText, { opacity: textOpacity }]}>{message}</Animated.Text>
    </View>
  );
}
