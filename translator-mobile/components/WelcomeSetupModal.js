import { useState } from "react";
import { Modal, View, Text, TextInput, Pressable, ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView } from "react-native";
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

  async function handleTest() {
    const ok = await onTestConnection?.();
    if (ok) setStep(1);
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => {}}>
      <KeyboardAvoidingView style={setupStyles.container} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={setupStyles.scroll} keyboardShouldPersistTaps="handled">
          <View style={setupStyles.hero}>
            <Ionicons name="language" size={42} color="#22d3ee" />
            <Text style={setupStyles.title}>Welcome to Anai</Text>
            <Text style={setupStyles.subtitle}>
              Real-time voice translation for conversations. Connect to your translator server, then tap Start and speak.
            </Text>
          </View>

          <View style={setupStyles.card}>
            <Text style={setupStyles.cardTitle}>1. Server address</Text>
            <Text style={setupStyles.hint}>
              Use your Railway URL or local network IP (same Wi‑Fi as this phone).
            </Text>
            <TextInput
              value={wsUrl}
              onChangeText={setWsUrl}
              placeholder="https://your-app.up.railway.app"
              placeholderTextColor="#64748b"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              style={setupStyles.input}
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
            {backendReachable === false && (
              <Text style={setupStyles.errorText}>Could not reach the server. Check the URL and try again.</Text>
            )}
          </View>

          {(step >= 1 || backendReachable) && (
            <View style={setupStyles.card}>
              <Text style={setupStyles.cardTitle}>2. Sign in (if required)</Text>
              <Text style={setupStyles.hint}>Leave as demo/demo if your server allows anonymous access.</Text>
              <TextInput
                value={username}
                onChangeText={setUsername}
                placeholder="Username"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
                style={setupStyles.input}
                accessibilityLabel="Username"
              />
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="Password"
                placeholderTextColor="#64748b"
                secureTextEntry
                style={setupStyles.input}
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

          <View style={setupStyles.card}>
            <Text style={setupStyles.cardTitle}>3. Microphone</Text>
            <Text style={setupStyles.hint}>
              When you tap Start, allow microphone access. You can change this later in phone Settings.
            </Text>
          </View>

          <Pressable
            onPress={onContinue}
            style={({ pressed }) => [setupStyles.primaryBtn, setupStyles.continueBtn, pressed && setupStyles.btnPressed]}
            accessibilityRole="button"
            accessibilityLabel="Continue to interpreter"
          >
            <Text style={setupStyles.primaryBtnText}>Get started</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}
