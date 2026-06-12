import { useEffect, useRef } from "react";
import { View, Text, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { transcriptHeaderLabel } from "../constants/productVoice";

export default function TranscriptStackHeader({ label = transcriptHeaderLabel(), sublabel = "", turnCount = 0 }) {
  const badgeScale = useRef(new Animated.Value(1)).current;
  const prevCount = useRef(turnCount);

  useEffect(() => {
    if (turnCount > prevCount.current) {
      badgeScale.setValue(0.72);
      Animated.spring(badgeScale, { toValue: 1, speed: 20, bounciness: 8, useNativeDriver: true }).start();
    }
    prevCount.current = turnCount;
  }, [turnCount, badgeScale]);

  return (
    <View style={styles.transcriptStackHeaderWrap}>
      <View style={styles.transcriptStackHeader}>
        <View style={styles.transcriptStackHeaderIcon}>
          <Ionicons name="git-network-outline" size={13} color="#67e8f9" />
        </View>
        <Text style={styles.transcriptStackHeaderText}>{label}</Text>
        {turnCount > 0 ? (
          <>
            <Text style={styles.transcriptStackSubtext}>
              {sublabel || `${turnCount} bridge exchange${turnCount === 1 ? "" : "s"}`}
            </Text>
            <Animated.View style={[styles.transcriptStackBadge, { transform: [{ scale: badgeScale }] }]}>
              <Text style={styles.transcriptStackBadgeText}>{turnCount}</Text>
            </Animated.View>
          </>
        ) : null}
      </View>
      <View style={styles.transcriptStackHeaderLine} pointerEvents="none" />
    </View>
  );
}
