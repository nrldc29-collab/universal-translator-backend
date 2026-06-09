import "react-native-gesture-handler";
import "react-native-reanimated";
import { registerRootComponent } from "expo";
import { Component } from "react";
import { DevSettings, ScrollView, Text, View, Pressable } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import App from "./App";

class RootErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error("Anai Translator startup error:", error);
  }

  handleRetry = () => {
    this.setState({ error: null });
    try {
      DevSettings.reload();
    } catch {
      // DevSettings may be unavailable outside Expo Go.
    }
  };

  render() {
    if (this.state.error) {
      const message = String(this.state.error?.message || this.state.error || "Unknown startup error");
      return (
        <View style={{ flex: 1, backgroundColor: "#03050a", padding: 24, justifyContent: "center" }}>
          <Text style={{ color: "#f87171", fontSize: 18, fontWeight: "700", marginBottom: 8 }}>
            Anai Translator could not start
          </Text>
          <Text style={{ color: "#94a3b8", fontSize: 14, lineHeight: 20, marginBottom: 16 }}>
            Wait for Metro to finish bundling on your PC, then tap Try again. If this keeps happening, close other Expo Go tabs and reopen the project.
          </Text>
          <ScrollView style={{ maxHeight: 180, marginBottom: 20 }}>
            <Text style={{ color: "#e2e8f0", fontSize: 13, lineHeight: 18 }} selectable>
              {message}
            </Text>
          </ScrollView>
          <Pressable
            onPress={this.handleRetry}
            style={{
              backgroundColor: "#22d3ee",
              borderRadius: 12,
              paddingVertical: 14,
              alignItems: "center",
            }}
          >
            <Text style={{ color: "#07131f", fontSize: 16, fontWeight: "700" }}>Try again</Text>
          </Pressable>
        </View>
      );
    }
    return this.props.children;
  }
}

function Root() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <RootErrorBoundary>
          <App />
        </RootErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

registerRootComponent(Root);
