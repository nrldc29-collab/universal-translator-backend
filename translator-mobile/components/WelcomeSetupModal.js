import { useEffect, useState } from "react";
import { Modal, View, Text, TextInput, Pressable, ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, SafeAreaView } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import setupStyles from "./WelcomeSetupModal.styles";
import NeoBrandMark from "./NeoBrandMark";
import SetupHeroIcon from "./SetupHeroIcon";
import SetupStepCard from "./SetupStepCard";

export default function WelcomeSetupModal({
  visible,
  wsUrl,
  setWsUrl,
  username,
  setUsername,
  password,
  setPassword,
  onTestConnection,
  onLogin,
  onContinue,
  onDismiss,
  onStartCloud,
  cloudApiUrl = "",
  backendReachable,
  isChecking,
}) {
  const [step, setStep] = useState(0);
  const [focusedField, setFocusedField] = useState(null);

  useEffect(() => {
    if (visible) setStep(0);
  }, [visible]);

  async function handleTest() {
    const ok = await onTestConnection?.();
    if (ok) setStep(1);
  }

  const setupProgress = backendReachable ? (step >= 1 ? 2 : 1) : 0;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={() => {
        if (backendReachable === true) (onDismiss || onContinue)?.();
      }}
    >
      <SafeAreaView style={setupStyles.container}>
        <LinearGradient
          colors={["rgba(103, 232, 249, 0.35)", "transparent"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={setupStyles.headerShine}
          pointerEvents="none"
        />
        <KeyboardAvoidingView style={setupStyles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <ScrollView contentContainerStyle={setupStyles.scroll} keyboardShouldPersistTaps="handled">
            <View style={setupStyles.hero}>
              <SetupHeroIcon />
              <NeoBrandMark compact />
              <Text style={setupStyles.title}>
                Welcome to <Text style={setupStyles.titleAccent}>Anai</Text>
              </Text>
              <Text style={setupStyles.subtitle}>
                {cloudApiUrl
                  ? "Talk across languages in real time. Start with Anai Cloud — no PC or Wi‑Fi setup — or connect your own bridge server."
                  : "Bridge languages in real conversation. Link to your bridge server, then tap Start — each person can stay in their own language."}
              </Text>
              {cloudApiUrl ? (
                <Pressable
                  onPress={onStartCloud}
                  disabled={isChecking}
                  style={({ pressed }) => [
                    setupStyles.primaryBtn,
                    setupStyles.cloudHeroBtn,
                    pressed && setupStyles.btnPressed,
                    isChecking && setupStyles.btnDisabled,
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Start talking with Anai Cloud"
                >
                  {isChecking ? (
                    <ActivityIndicator color="#07131f" />
                  ) : (
                    <View style={setupStyles.cloudHeroBtnInner}>
                      <Ionicons name="cloud-outline" size={18} color="#07131f" />
                      <Text style={setupStyles.primaryBtnText}>Start talking</Text>
                    </View>
                  )}
                </Pressable>
              ) : null}
              {cloudApiUrl ? (
                <Text style={setupStyles.cloudDivider}>or use your own bridge</Text>
              ) : null}
              <View style={setupStyles.stepRow} accessibilityLabel={`Setup step ${setupProgress + 1} of 3`}>
                {[0, 1, 2].map((i) => (
                  <View
                    key={i}
                    style={[
                      setupStyles.stepDot,
                      i < setupProgress && setupStyles.stepDotDone,
                      i === setupProgress && setupStyles.stepDotActive,
                    ]}
                  />
                ))}
              </View>
            </View>

            <SetupStepCard active={setupProgress === 0}>
              <View style={setupStyles.cardHead}>
                <View style={setupStyles.cardIconWrap}>
                  <Ionicons name="server-outline" size={15} color="#67e8f9" />
                </View>
                <Text style={setupStyles.cardTitle}>1. Bridge server</Text>
              </View>
              <Text style={setupStyles.hint}>
                Use your Railway URL or local network IP (same Wi‑Fi as this phone).
              </Text>
              <TextInput
                value={wsUrl}
                onChangeText={setWsUrl}
                placeholder="http://192.168.1.100:8000"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                style={[setupStyles.input, focusedField === "url" && setupStyles.inputFocused]}
                onFocus={() => setFocusedField("url")}
                onBlur={() => setFocusedField((f) => (f === "url" ? null : f))}
                accessibilityLabel="Bridge server URL"
              />
              <Pressable
                onPress={handleTest}
                disabled={isChecking}
                style={({ pressed }) => [setupStyles.primaryBtn, pressed && setupStyles.btnPressed, isChecking && setupStyles.btnDisabled]}
                accessibilityRole="button"
                accessibilityLabel="Test bridge server link"
              >
                {isChecking ? (
                  <ActivityIndicator color="#07131f" />
                ) : (
                  <Text style={setupStyles.primaryBtnText}>
                    {backendReachable === true ? "Bridge reachable — continue" : "Test bridge link"}
                  </Text>
                )}
              </Pressable>
              {backendReachable === true && (
                <View style={setupStyles.successRow}>
                  <Ionicons name="checkmark-circle" size={16} color="#34d399" />
                  <Text style={setupStyles.successText}>Bridge server reachable</Text>
                </View>
              )}
              {backendReachable === false && (
                <Text style={setupStyles.errorText}>Could not reach the bridge server. Check the URL and try again.</Text>
              )}
            </SetupStepCard>

            {(step >= 1 || backendReachable) && (
              <SetupStepCard active={setupProgress === 1}>
                <View style={setupStyles.cardHead}>
                  <View style={setupStyles.cardIconWrap}>
                    <Ionicons name="person-circle-outline" size={15} color="#67e8f9" />
                  </View>
                  <Text style={setupStyles.cardTitle}>2. Sign in (if required)</Text>
                </View>
                <Text style={setupStyles.hint}>Leave as demo/demo if your server allows anonymous access.</Text>
                <TextInput
                  value={username}
                  onChangeText={setUsername}
                  placeholder="Username"
                  placeholderTextColor="#64748b"
                  autoCapitalize="none"
                  style={[setupStyles.input, focusedField === "user" && setupStyles.inputFocused]}
                  onFocus={() => setFocusedField("user")}
                  onBlur={() => setFocusedField((f) => (f === "user" ? null : f))}
                  accessibilityLabel="Username"
                />
                <TextInput
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Password"
                  placeholderTextColor="#64748b"
                  secureTextEntry
                  style={[setupStyles.input, focusedField === "pass" && setupStyles.inputFocused]}
                  onFocus={() => setFocusedField("pass")}
                  onBlur={() => setFocusedField((f) => (f === "pass" ? null : f))}
                  accessibilityLabel="Password"
                />
                <Pressable
                  onPress={onLogin}
                  style={({ pressed }) => [setupStyles.secondaryBtn, pressed && setupStyles.btnPressed]}
                  accessibilityRole="button"
                  accessibilityLabel="Sign in to bridge server"
                >
                  <Text style={setupStyles.secondaryBtnText}>Sign in</Text>
                </Pressable>
              </SetupStepCard>
            )}

            <SetupStepCard active={setupProgress === 2}>
              <View style={setupStyles.cardHead}>
                <View style={setupStyles.cardIconWrap}>
                  <Ionicons name="mic-outline" size={15} color="#67e8f9" />
                </View>
                <Text style={setupStyles.cardTitle}>3. Your side of the bridge</Text>
              </View>
              <Text style={setupStyles.hint}>
                When you tap Start, allow microphone access so Anai can hear your side of the conversation. You can change this later in phone Settings.
              </Text>
            </SetupStepCard>

            {backendReachable === true ? (
              <Pressable
                onPress={() => (onDismiss || onContinue)?.()}
                style={({ pressed }) => [setupStyles.secondaryBtn, pressed && setupStyles.btnPressed]}
                accessibilityRole="button"
                accessibilityLabel="Skip setup for now"
              >
                <Text style={setupStyles.secondaryBtnText}>Skip for now</Text>
              </Pressable>
            ) : null}
            <Pressable
              onPress={onContinue}
              disabled={backendReachable !== true}
              style={({ pressed }) => [
                setupStyles.primaryBtn,
                setupStyles.continueBtn,
                pressed && setupStyles.btnPressed,
                backendReachable !== true && setupStyles.btnDisabled,
              ]}
              accessibilityRole="button"
              accessibilityLabel="Open the conversation bridge"
              accessibilityState={{ disabled: backendReachable !== true }}
            >
              <Text style={[setupStyles.primaryBtnText, backendReachable !== true && setupStyles.primaryBtnTextDisabled]}>
                {backendReachable === true ? "Open the bridge" : "Test bridge link first"}
              </Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}
