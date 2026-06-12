import { Children } from "react";
import { View } from "react-native";
import styles from "../AppStyles";

/** Groups cert / clarify / confidence alerts with consistent spacing. */
export default function ConversationQualityStack({ children }) {
  const items = Children.toArray(children).filter(Boolean);
  if (!items.length) return null;
  return <View style={styles.qualityAlertStack}>{items}</View>;
}
