import "react-native-gesture-handler";
import { registerRootComponent } from "expo";
import { Component } from "react";
import { ScrollView, Text, View } from "react-native";

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

  render() {
    if (this.state.error) {
      return (
        <View style={{ flex: 1, backgroundColor: "#03050a", padding: 24, justifyContent: "center" }}>
          <Text style={{ color: "#f87171", fontSize: 18, fontWeight: "700", marginBottom: 12 }}>
            Anai Translator failed to start
          </Text>
          <ScrollView>
            <Text style={{ color: "#e2e8f0", fontSize: 14, lineHeight: 20 }}>
              {String(this.state.error?.message || this.state.error)}
            </Text>
          </ScrollView>
        </View>
      );
    }
    return this.props.children;
  }
}

registerRootComponent(() => (
  <RootErrorBoundary>
    <App />
  </RootErrorBoundary>
));
