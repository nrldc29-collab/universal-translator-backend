import { useEffect, useRef } from "react";
import { View, Text, Pressable, Animated } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { certTitles } from "../constants/productVoice";
import { useMountForPresence } from "../hooks/useMountForPresence";

const CERT_TITLES = certTitles();
const STEP_META = {
  advisory: {
    icon: "ear-outline",
    title: CERT_TITLES.advisory,
    variant: "advisory",
    accent: "#fbbf24",
    panel: styles.certBannerAdvisory,
    iconWrap: styles.certBannerIconAdvisory,
  },
  required: {
    icon: "shield-checkmark-outline",
    title: CERT_TITLES.required,
    variant: "required",
    accent: "#fb923c",
    panel: styles.certBannerRequired,
    iconWrap: styles.certBannerIconRequired,
  },
};

export default function NativeSpeakerCertBanner({
  step = "advisory",
  message = "",
  onReview,
  onDismiss,
}) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-8)).current;
  const show = Boolean(message && step !== "none");
  const { mounted, mountedRef, setMounted } = useMountForPresence(show);

  useEffect(() => {
    if (show) {
      opacity.setValue(0);
      translateY.setValue(-8);
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }),
        Animated.spring(translateY, { toValue: 0, speed: 20, bounciness: 4, useNativeDriver: true }),
      ]).start();
      return undefined;
    }
    if (!mountedRef.current) return undefined;
    Animated.parallel([
      Animated.timing(opacity, { toValue: 0, duration: 180, useNativeDriver: true }),
      Animated.timing(translateY, { toValue: -8, duration: 180, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished) setMounted(false);
    });
    return undefined;
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mountedRef tracks mount without re-running the effect
  }, [message, step, show, opacity, translateY, setMounted]);

  if (!mounted || !message || step === "none") return null;

  const meta = STEP_META[step] || STEP_META.advisory;

  return (
    <Animated.View
      style={[styles.certBanner, meta.panel, { opacity, transform: [{ translateY }] }]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      accessibilityLabel={`${meta.title}. ${message}`}
    >
      <View style={[styles.certBannerAccent, { backgroundColor: meta.accent }]} pointerEvents="none" />
      <View style={[styles.certBannerIconWrap, meta.iconWrap]}>
        <Ionicons name={meta.icon} size={20} color={meta.accent} />
      </View>
      <View style={styles.certBannerCopy}>
        <Text style={styles.certBannerTitle}>{meta.title}</Text>
        <Text style={styles.certBannerText}>{message}</Text>
      </View>
      <View style={styles.certBannerActions}>
        {onReview ? (
          <Pressable
            onPress={onReview}
            style={({ pressed }) => [styles.certBannerAction, pressed && styles.certBannerActionPressed]}
            accessibilityRole="button"
            accessibilityLabel="Review bridged meaning with native speaker"
          >
            <Text style={styles.certBannerActionText}>Review</Text>
          </Pressable>
        ) : null}
        {onDismiss ? (
          <Pressable
            onPress={onDismiss}
            style={({ pressed }) => [styles.certBannerDismiss, pressed && styles.certBannerActionPressed]}
            accessibilityRole="button"
            accessibilityLabel="Dismiss"
          >
            <Ionicons name="close" size={16} color="rgba(226, 232, 240, 0.88)" />
          </Pressable>
        ) : null}
      </View>
    </Animated.View>
  );
}
