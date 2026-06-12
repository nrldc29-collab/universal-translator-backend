import { View } from "react-native";
import styles from "../AppStyles";

const GRID_LINES = 8;

export default function CosmicGridOverlay() {
  return (
    <View style={styles.cosmicGridOverlay} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {Array.from({ length: GRID_LINES }, (_, index) => (
        <View
          key={`grid-h-${index}`}
          style={[styles.cosmicGridLineH, { top: `${10 + index * 11}%` }]}
        />
      ))}
      {Array.from({ length: 5 }, (_, index) => (
        <View
          key={`grid-v-${index}`}
          style={[styles.cosmicGridLineV, { left: `${8 + index * 20}%` }]}
        />
      ))}
    </View>
  );
}
