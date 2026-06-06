import { View, Text, ActivityIndicator } from "react-native";
import styles from "../AppStyles";

export default function LoadingScreen({ message = "Loading interpreter..." }) {
  return (
    <View style={styles.loadingScreen} accessibilityRole="progressbar" accessibilityLabel={message}>
      <ActivityIndicator size="large" color="#22d3ee" />
      <Text style={styles.loadingScreenText}>{message}</Text>
    </View>
  );
}
