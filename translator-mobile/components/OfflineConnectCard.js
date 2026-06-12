import { View, Text, Pressable, ActivityIndicator } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import styles from "../AppStyles";
import { offlineConnectCopy } from "../constants/productVoice";

export default function OfflineConnectCard({
  buildId = "",
  title = offlineConnectCopy().title,
  message = "",
  isConnecting = false,
  hasWebApp = false,
  hasPhoneSetup = false,
  onOpenWeb,
  onConnect,
  onReload,
  onSetupHelp,
  webAppLabel = "Open in Safari",
}) {
  return (
    <View style={styles.offlineCta}>
      <LinearGradient
        colors={["rgba(248, 113, 113, 0.35)", "rgba(103, 232, 249, 0.15)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={styles.offlineCtaShine}
        pointerEvents="none"
      />
      <View style={styles.offlineCtaAccent} pointerEvents="none" />
      <View style={styles.offlineCtaTitleRow}>
        <View style={styles.offlineCtaIcon}>
          <Ionicons name="cloud-offline-outline" size={22} color="#67e8f9" />
        </View>
        <View style={styles.offlineCtaTitleText}>
          <Text style={styles.offlineCtaTitle}>{title}</Text>
          {buildId ? <Text style={styles.offlineCtaMeta}>Build {buildId}</Text> : null}
        </View>
      </View>
      <Text style={styles.offlineCtaText}>{message}</Text>
      {hasWebApp ? (
        <Pressable
          onPress={onOpenWeb}
          style={({ pressed }) => [styles.offlineCtaBtnPrimary, pressed && styles.offlineCtaBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Open conversation bridge in Safari"
        >
          <Ionicons name="globe-outline" size={18} color="#07131f" />
          <Text style={styles.offlineCtaBtnPrimaryText}>{webAppLabel}</Text>
        </Pressable>
      ) : null}
      <Pressable
        onPress={onConnect}
        style={({ pressed }) => [
          hasWebApp ? styles.offlineCtaBtnSecondary : styles.offlineCtaBtnPrimary,
          pressed && styles.offlineCtaBtnPressed,
          hasWebApp && styles.offlineCtaBtnSecondaryBlock,
        ]}
        accessibilityRole="button"
        accessibilityLabel="Link bridge server"
      >
        {isConnecting ? <ActivityIndicator size="small" color={hasWebApp ? "#67e8f9" : "#07131f"} /> : null}
        {hasWebApp ? (
          <Text style={styles.offlineCtaBtnSecondaryText}>
            {isConnecting ? "Linking…" : "Link in Expo Go"}
          </Text>
        ) : (
          <>
            {!isConnecting ? <Ionicons name="link" size={18} color="#07131f" /> : null}
            <Text style={styles.offlineCtaBtnPrimaryText}>
              {isConnecting ? "Linking…" : "Link bridge server"}
            </Text>
          </>
        )}
      </Pressable>
      <View style={styles.offlineCtaActions}>
        <Pressable
          onPress={onReload}
          style={({ pressed }) => [styles.offlineCtaBtnSecondary, pressed && styles.offlineCtaBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Reload latest app code"
        >
          <Text style={styles.offlineCtaBtnSecondaryText}>Reload app</Text>
        </Pressable>
        {hasPhoneSetup ? (
          <Pressable
            onPress={onSetupHelp}
            style={({ pressed }) => [styles.offlineCtaBtnSecondary, pressed && styles.offlineCtaBtnPressed]}
            accessibilityRole="button"
            accessibilityLabel="Open phone setup page in browser"
          >
            <Text style={styles.offlineCtaBtnSecondaryText}>Setup help</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}
