import { useState } from "react";
import { View, Text, Button } from "react-native";
import { connectWS } from "./services/ws";

const WS_URL = "ws://192.168.12.243:8000/ws/audio";

export default function App() {
  const [status, setStatus] = useState("Idle");

  return (
    <View style={{ padding: 40 }}>
      <Text style={{ fontSize: 24 }}>Live Translator</Text>

      <Text style={{ marginVertical: 20 }}>
        Status: {status}
      </Text>

      <Button
        title="Connect"
        onPress={() => {
          setStatus("Connecting...");
          connectWS(WS_URL, (message) => {
            setStatus(message.type || "Message received");
          });
        }}
      />
    </View>
  );
}
