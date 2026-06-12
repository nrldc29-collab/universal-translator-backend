import { View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import styles from "../AppStyles";
import MicPanelPulse from "./MicPanelPulse";

export default function MicPanelFrame({ children, isListening = false, isArmed = false, isBridgingOut = false }) {
  return (
    <View
      style={[
        styles.micPanelFrame,
        isArmed && styles.micPanelFrameArmed,
        isListening && styles.micPanelFrameListening,
        isBridgingOut && styles.micPanelFrameBridging,
      ]}
    >
      <MicPanelPulse visible={isListening || isBridgingOut} />
      <LinearGradient
        colors={["rgba(103, 232, 249, 0.28)", "rgba(45, 212, 191, 0.12)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.micPanelFrameShine}
        pointerEvents="none"
      />
      {children}
    </View>
  );
}
