import { useEffect, useRef } from "react";
import { View, Text, ActivityIndicator, Animated } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import styles from "../AppStyles";
import NeoBrandMark from "./NeoBrandMark";
import CosmicAmbience from "./CosmicAmbience";
import { loadingScreenMessage } from "../constants/productVoice";

export default function LoadingScreen({ message = loadingScreenMessage() }) {
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
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [pulse]);

  return (
    <LinearGradient
      colors={["#03050a", "#071018", "#0a1628", "#03050a"]}
      locations={[0, 0.35, 0.7, 1]}
      style={styles.loadingScreen}
    >
      <CosmicAmbience />
      <View style={styles.loadingBrandWrap} accessibilityRole="progressbar" accessibilityLabel={message}>
        <Animated.View style={[styles.loadingOrbRing, { transform: [{ scale: pulse }] }]}>
          <View style={styles.loadingOrbCore}>
            <Text style={styles.loadingOrbMic}>⬡</Text>
          </View>
        </Animated.View>
        <NeoBrandMark subline="BRIDGE" />
      </View>
      <ActivityIndicator size="large" color="#22d3ee" />
      <Animated.Text style={[styles.loadingScreenText, { opacity: textOpacity }]}>{message}</Animated.Text>
    </LinearGradient>
  );
}
