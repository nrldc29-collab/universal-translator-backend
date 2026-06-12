import { View, Text, Pressable, Animated } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import helpStyles from "./HelpTipsModal.styles";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";

export default function HelpTipCard({ tip, index = 0, visible = false }) {
  const { mounted, style } = useAnimatedPresence(visible, {
    delay: index * 68,
    initialOffset: 18,
    axis: "x",
    duration: 280,
    exitDuration: 180,
  });

  if (!mounted) return null;

  return (
    <Animated.View style={style}>
      <Pressable style={({ pressed }) => [helpStyles.card, pressed && helpStyles.cardPressed]}>
        <LinearGradient
          colors={["rgba(103, 232, 249, 0.22)", "transparent"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={helpStyles.cardShine}
          pointerEvents="none"
        />
        <View style={helpStyles.cardAccent} pointerEvents="none" />
        <View style={helpStyles.tipNumberWrap}>
          <Text style={helpStyles.tipNumber}>{index + 1}</Text>
        </View>
        <View style={helpStyles.iconWrap}>
          <Ionicons name={tip.icon} size={20} color="#22d3ee" />
        </View>
        <View style={helpStyles.cardBody}>
          <Text style={helpStyles.cardTitle}>{tip.title}</Text>
          <Text style={helpStyles.cardText}>{tip.body}</Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}
