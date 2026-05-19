import { useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import type { RefObject } from "react";

interface DuplexModeProps {
  isConnected: boolean;
  wsControlRef: RefObject<WebSocket | null>;
  sourceLanguage: string;
  targetLanguage: string;
}

export default function DuplexMode({
  isConnected,
  wsControlRef,
  sourceLanguage,
  targetLanguage
}: DuplexModeProps) {
  const [activeSpeaker, setActiveSpeaker] = useState<"A" | "B">("A");
  const [speakerA] = useState({
    active: false,
    transcript: "",
    translation: "",
    stage: "Idle"
  });
  const [speakerB] = useState({
    active: false,
    transcript: "",
    translation: "",
    stage: "Idle"
  });

  const toggleSpeaker = (speaker: "A" | "B") => {
    if (!isConnected) return;

    const otherState = speaker === "A" ? speakerB : speakerA;

    // If other speaker is active, stop it first
    if (otherState.active && wsControlRef.current) {
      wsControlRef.current.send(JSON.stringify({ type: "finalize" }));
    }

    setActiveSpeaker(speaker);

    // Send start message for this speaker
    if (wsControlRef.current) {
      const source = speaker === "A" ? sourceLanguage : targetLanguage;
      const target = speaker === "A" ? targetLanguage : sourceLanguage;

      wsControlRef.current.send(JSON.stringify({
        type: "start",
        speaker: speaker,
        speaker_label: `Speaker ${speaker}`,
        source_language: source,
        target_language: target,
      }));
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Duplex Conversation</Text>

      <View style={styles.speakerRow}>
        <Pressable
          style={[styles.speakerButton, activeSpeaker === "A" && styles.speakerActive]}
          onPress={() => toggleSpeaker("A")}
          disabled={!isConnected}
        >
          <Text style={[styles.speakerText, activeSpeaker === "A" && styles.speakerTextActive]}>
            Speaker A
          </Text>
          <Text style={styles.stage}>{speakerA.stage}</Text>
        </Pressable>

        <Pressable
          style={[styles.speakerButton, activeSpeaker === "B" && styles.speakerActive]}
          onPress={() => toggleSpeaker("B")}
          disabled={!isConnected}
        >
          <Text style={[styles.speakerText, activeSpeaker === "B" && styles.speakerTextActive]}>
            Speaker B
          </Text>
          <Text style={styles.stage}>{speakerB.stage}</Text>
        </Pressable>
      </View>

      <View style={styles.conversationView}>
        <View style={styles.speakerCard}>
          <Text style={styles.cardTitle}>Speaker A</Text>
          <Text style={styles.textLabel}>Source:</Text>
          <Text style={styles.text}>{speakerA.transcript || "-"}</Text>
          <Text style={styles.textLabel}>Translation:</Text>
          <Text style={styles.text}>{speakerA.translation || "-"}</Text>
        </View>

        <View style={styles.speakerCard}>
          <Text style={styles.cardTitle}>Speaker B</Text>
          <Text style={styles.textLabel}>Source:</Text>
          <Text style={styles.text}>{speakerB.transcript || "-"}</Text>
          <Text style={styles.textLabel}>Translation:</Text>
          <Text style={styles.text}>{speakerB.translation || "-"}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 15 },
  title: { fontSize: 18, fontWeight: "900", color: '#e5ecff', marginBottom: 10 },
  speakerRow: { flexDirection: "row", gap: 10, marginBottom: 15 },
  speakerButton: {
    flex: 1,
    padding: 15,
    backgroundColor: '#07111f',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.18)',
    alignItems: "center"
  },
  speakerActive: { borderColor: '#67e8f9', backgroundColor: 'rgba(8, 145, 178, 0.28)' },
  speakerText: { color: '#93a4bd', fontWeight: "900", fontSize: 16 },
  speakerTextActive: { color: '#e5ecff' },
  stage: { color: '#67e8f9', fontSize: 12, marginTop: 5 },
  conversationView: { flexDirection: "row", gap: 10 },
  speakerCard: {
    flex: 1,
    padding: 12,
    backgroundColor: '#07111f',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.16)'
  },
  cardTitle: { color: '#67e8f9', fontWeight: "900", fontSize: 14, marginBottom: 8 },
  textLabel: { color: '#93a4bd', fontSize: 12, marginTop: 8 },
  text: { color: '#e5ecff', fontSize: 14, marginTop: 4, lineHeight: 20 },
});
