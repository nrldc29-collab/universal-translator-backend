import { useEffect, useState } from "react";
import { Modal, View, Text, TextInput, Pressable, ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, SafeAreaView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import setupStyles from "./WelcomeSetupModal.styles";

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
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => {}}>
      <SafeAreaView style={setupStyles.container}>
        <KeyboardAvoidingView style={setupStyles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <ScrollView contentContainerStyle={setupStyles.scroll} keyboardShouldPersistTaps="handled">
            <View style={setupStyles.hero}>
              <View style={setupStyles.heroIconRing}>
                <Ionicons name="language" size={42} color="#22d3ee" />
              </View>
              <Text style={setupStyles.title}>
                Welcome to <Text style={setupStyles.titleAccent}>Anai</Text>
              </Text>
              <Text style={setupStyles.subtitle}>
                Real-time voice translation for conversations. Connect to your translator server, then tap Start and speak.
              </Text>
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

            <View style={[setupStyles.card, setupProgress === 0 && setupStyles.cardActive]}>
              <Text style={setupStyles.cardTitle}>1. Server address</Text>
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
                accessibilityLabel="Backend server URL"
              />
              <Pressable
                onPress={handleTest}
                disabled={isChecking}
                style={({ pressed }) => [setupStyles.primaryBtn, pressed && setupStyles.btnPressed, isChecking && setupStyles.btnDisabled]}
                accessibilityRole="button"
                accessibilityLabel="Test server connection"
              >
                {isChecking ? (
                  <ActivityIndicator color="#07131f" />
                ) : (
                  <Text style={setupStyles.primaryBtnText}>
                    {backendReachable === true ? "Connected — continue" : "Test connection"}
                  </Text>
                )}
              </Pressable>
              {backendReachable === true && (
                <View style={setupStyles.successRow}>
                  <Ionicons name="checkmark-circle" size={16} color="#34d399" />
                  <Text style={setupStyles.successText}>Server reachable</Text>
                </View>
              )}
              {backendReachable === false && (
                <Text style={setupStyles.errorText}>Could not reach the server. Check the URL and try again.</Text>
              )}
            </View>

            {(step >= 1 || backendReachable) && (
              <View style={[setupStyles.card, setupProgress === 1 && setupStyles.cardActive]}>
                <Text style={setupStyles.cardTitle}>2. Sign in (if required)</Text>
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
                  accessibilityLabel="Sign in to translator"
                >
                  <Text style={setupStyles.secondaryBtnText}>Sign in</Text>
                </Pressable>
              </View>
            )}

            <View style={[setupStyles.card, setupProgress === 2 && setupStyles.cardActive]}>
              <Text style={setupStyles.cardTitle}>3. Microphone</Text>
              <Text style={setupStyles.hint}>
                When you tap Start, allow microphone access. You can change this later in phone Settings.
              </Text>
            </View>

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
              accessibilityLabel="Continue to interpreter"
              accessibilityState={{ disabled: backendReachable !== true }}
            >
              <Text style={[setupStyles.primaryBtnText, backendReachable !== true && setupStyles.primaryBtnTextDisabled]}>
                {backendReachable === true ? "Get started" : "Test connection first"}
              </Text>
            </Pressable>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}
