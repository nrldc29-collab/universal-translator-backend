import { useState, useEffect, useRef, useCallback } from "react";
import { View, Text, Pressable, StyleSheet, Animated } from "react-native";
import type { RefObject } from "react";

interface DuplexModeProps {
  isConnected: boolean;
  wsControlRef: RefObject<WebSocket | null>;
  sourceLanguage: string;
  targetLanguage: string;
  onTranscriptUpdate?: (speaker: string, text: string) => void;
  onTranslationUpdate?: (speaker: string, text: string) => void;
}

interface SpeakerState {
  active: boolean;
  transcript: string;
  translation: string;
  stage: "Idle" | "Listening" | "Transcribing" | "Translating" | "Translated" | "Speaking";
  lastActivityAt: number;
}

const INITIAL_SPEAKER: SpeakerState = {
  active: false,
  transcript: "",
  translation: "",
  stage: "Idle",
  lastActivityAt: 0,
};

/**
 * True duplex conversation mode.
 *
 * Both speakers can be active simultaneously — the ConversationBrain on the
 * backend arbitrates overlapping turns via soft-overlap and interruption grace
 * periods. The component sends separate `start` messages for each speaker with
 * swapped source/target languages so translations flow both directions.
 */
export default function DuplexMode({
  isConnected,
  wsControlRef,
  sourceLanguage,
  targetLanguage,
  onTranscriptUpdate,
  onTranslationUpdate,
}: DuplexModeProps) {
  const [speakerA, setSpeakerA] = useState<SpeakerState>({ ...INITIAL_SPEAKER });
  const [speakerB, setSpeakerB] = useState<SpeakerState>({ ...INITIAL_SPEAKER });
  const [conversationHistory, setConversationHistory] = useState<
    Array<{ speaker: string; source: string; translation: string; timestamp: number }>
  >([]);
  const pulseA = useRef(new Animated.Value(1)).current;
  const pulseB = useRef(new Animated.Value(1)).current;

  // Pulse animation for active speaker
  const startPulse = useCallback((anim: Animated.Value) => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1.08, duration: 600, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 1, duration: 600, useNativeDriver: true }),
      ])
    ).start();
  }, []);

  const stopPulse = useCallback((anim: Animated.Value) => {
    anim.stopAnimation();
    anim.setValue(1);
  }, []);

  useEffect(() => {
    if (speakerA.active) startPulse(pulseA); else stopPulse(pulseA);
  }, [speakerA.active]);

  useEffect(() => {
    if (speakerB.active) startPulse(pulseB); else stopPulse(pulseB);
  }, [speakerB.active]);

  const sendWs = useCallback(
    (payload: object) => {
      if (wsControlRef.current && wsControlRef.current.readyState === WebSocket.OPEN) {
        wsControlRef.current.send(JSON.stringify(payload));
      }
    },
    [wsControlRef]
  );

  const toggleSpeaker = useCallback(
    (speaker: "A" | "B") => {
      if (!isConnected) return;

      const setState = speaker === "A" ? setSpeakerA : setSpeakerB;
      const current = speaker === "A" ? speakerA : speakerB;
      const source = speaker === "A" ? sourceLanguage : targetLanguage;
      const target = speaker === "A" ? targetLanguage : sourceLanguage;

      if (current.active) {
        // Stop this speaker — finalize their current utterance
        sendWs({ type: "finalize" });
        setState((prev) => ({ ...prev, active: false, stage: "Idle" }));
      } else {
        // Start this speaker — ConversationBrain handles overlap
        sendWs({
          type: "start",
          speaker: speaker,
          speaker_label: `Speaker ${speaker}`,
          speaker_mode: "manual",
          source_language: source,
          target_language: target,
          duplex: true,
        });
        setState((prev) => ({
          ...prev,
          active: true,
          stage: "Listening",
          transcript: "",
          translation: "",
          lastActivityAt: Date.now(),
        }));
      }
    },
    [isConnected, speakerA, speakerB, sourceLanguage, targetLanguage, sendWs]
  );

  // Listen for WebSocket messages and route to correct speaker
  useEffect(() => {
    const ws = wsControlRef.current;
    if (!ws) return;

    const handler = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const msgSpeaker = data.speaker || data.speaker_label || "";
        const isA = msgSpeaker === "A" || msgSpeaker === "Speaker A";
        const isB = msgSpeaker === "B" || msgSpeaker === "Speaker B";
        const setter = isA ? setSpeakerA : isB ? setSpeakerB : null;

        switch (data.type) {
          case "partial_transcription":
            if (setter) {
              setter((prev) => ({
                ...prev,
                transcript: data.text || prev.transcript,
                stage: "Transcribing",
                lastActivityAt: Date.now(),
              }));
              if (onTranscriptUpdate) onTranscriptUpdate(msgSpeaker, data.text);
            }
            break;

          case "final_transcription":
            if (setter) {
              setter((prev) => ({
                ...prev,
                transcript: data.text || prev.transcript,
                stage: "Translating",
                lastActivityAt: Date.now(),
              }));
              if (onTranscriptUpdate) onTranscriptUpdate(msgSpeaker, data.text);
            }
            break;

          case "live_translation":
          case "partial_translation":
            if (setter) {
              setter((prev) => ({
                ...prev,
                translation: data.text || prev.translation,
                stage: "Translated",
                lastActivityAt: Date.now(),
              }));
              if (onTranslationUpdate) onTranslationUpdate(msgSpeaker, data.text);
            }
            break;

          case "final":
            if (setter) {
              const finalTranslation = data.translated_text || data.text || "";
              const finalSource = data.source_text || "";
              setter((prev) => ({
                ...prev,
                translation: finalTranslation || prev.translation,
                transcript: finalSource || prev.transcript,
                stage: "Idle",
                active: false,
                lastActivityAt: Date.now(),
              }));
              if (finalSource && finalTranslation) {
                setConversationHistory((prev) => [
                  ...prev.slice(-19),
                  {
                    speaker: msgSpeaker,
                    source: finalSource,
                    translation: finalTranslation,
                    timestamp: Date.now(),
                  },
                ]);
              }
            }
            break;

          case "tts_audio_chunk":
            if (setter) {
              setter((prev) => ({ ...prev, stage: "Speaking", lastActivityAt: Date.now() }));
            }
            break;

          case "tts_end":
            if (setter) {
              setter((prev) => ({ ...prev, stage: "Idle", lastActivityAt: Date.now() }));
            }
            break;

          case "turn":
            // ConversationBrain arbitration — update UI indicators
            if (data.behavior === "hold" && setter) {
              setter((prev) => ({ ...prev, stage: "Idle" }));
            }
            break;

          case "active_speaker":
            // Visual feedback for who's currently dominant
            break;
        }
      } catch {
        // Ignore non-JSON or malformed messages
      }
    };

    ws.addEventListener("message", handler);
    return () => ws.removeEventListener("message", handler);
  }, [wsControlRef.current, onTranscriptUpdate, onTranslationUpdate]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        Duplex <Text style={styles.titleAccent}>conversation</Text>
      </Text>
      <Text style={styles.subtitle}>Both speakers can talk simultaneously</Text>

      <View style={styles.speakerRow}>
        <Animated.View style={[styles.speakerWrapper, { transform: [{ scale: pulseA }] }]}>
          <Pressable
            style={({ pressed }) => [
              styles.speakerButton,
              speakerA.active && styles.speakerActive,
              !isConnected && styles.speakerDisabled,
              pressed && styles.speakerPressed,
            ]}
            onPress={() => toggleSpeaker("A")}
            disabled={!isConnected}
          >
            <Text style={[styles.speakerText, speakerA.active && styles.speakerTextActive]}>
              Speaker A
            </Text>
            <Text style={styles.langTag}>{sourceLanguage.toUpperCase()}</Text>
            <Text style={[
              styles.stage,
              speakerA.active && styles.stageActive,
              speakerA.stage === "Listening" && styles.stageListening,
              speakerA.stage === "Translating" && styles.stageTranslating,
              speakerA.stage === "Speaking" && styles.stageSpeaking,
            ]}>
              {speakerA.stage}
            </Text>
            <Text style={styles.tapHint}>{speakerA.active ? "Tap to stop" : "Tap to talk"}</Text>
          </Pressable>
        </Animated.View>

        <Animated.View style={[styles.speakerWrapper, { transform: [{ scale: pulseB }] }]}>
          <Pressable
            style={({ pressed }) => [
              styles.speakerButton,
              speakerB.active && styles.speakerActive,
              !isConnected && styles.speakerDisabled,
              pressed && styles.speakerPressed,
            ]}
            onPress={() => toggleSpeaker("B")}
            disabled={!isConnected}
          >
            <Text style={[styles.speakerText, speakerB.active && styles.speakerTextActive]}>
              Speaker B
            </Text>
            <Text style={styles.langTag}>{targetLanguage.toUpperCase()}</Text>
            <Text style={[
              styles.stage,
              speakerB.active && styles.stageActive,
              speakerB.stage === "Listening" && styles.stageListening,
              speakerB.stage === "Translating" && styles.stageTranslating,
              speakerB.stage === "Speaking" && styles.stageSpeaking,
            ]}>
              {speakerB.stage}
            </Text>
            <Text style={styles.tapHint}>{speakerB.active ? "Tap to stop" : "Tap to talk"}</Text>
          </Pressable>
        </Animated.View>
      </View>

      <View style={styles.conversationView}>
        <View style={[styles.speakerCard, (speakerA.transcript || speakerA.translation) && styles.speakerCardLive]}>
          <Text style={styles.cardTitle}>Speaker A ({sourceLanguage.toUpperCase()})</Text>
          <Text style={styles.textLabel}>Said:</Text>
          <Text style={styles.text}>{speakerA.transcript || "-"}</Text>
          <Text style={styles.textLabel}>Translation:</Text>
          <Text style={styles.translationText}>{speakerA.translation || "-"}</Text>
        </View>

        <View style={[styles.speakerCard, (speakerB.transcript || speakerB.translation) && styles.speakerCardLive]}>
          <Text style={styles.cardTitle}>Speaker B ({targetLanguage.toUpperCase()})</Text>
          <Text style={styles.textLabel}>Said:</Text>
          <Text style={styles.text}>{speakerB.transcript || "-"}</Text>
          <Text style={styles.textLabel}>Translation:</Text>
          <Text style={styles.translationText}>{speakerB.translation || "-"}</Text>
        </View>
      </View>

      {conversationHistory.length > 0 && (
        <View style={styles.historySection}>
          <Text style={styles.historyTitle}>Conversation</Text>
          {conversationHistory.slice(-5).map((turn, i, turns) => (
            <View
              key={i}
              style={[styles.historyTurn, i === turns.length - 1 && styles.historyTurnLatest]}
            >
              <Text style={styles.historySpeaker}>{turn.speaker}:</Text>
              <Text style={styles.historySource}>{turn.source}</Text>
              <Text style={styles.historyArrow}>→</Text>
              <Text style={styles.historyTranslation}>{turn.translation}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 15 },
  title: { fontSize: 18, fontWeight: "900", color: "#e5ecff", marginBottom: 2 },
  titleAccent: { color: "#67e8f9" },
  subtitle: { fontSize: 12, color: "#93a4bd", marginBottom: 12, lineHeight: 17 },
  speakerRow: { flexDirection: "row", gap: 10, marginBottom: 15 },
  speakerWrapper: { flex: 1 },
  speakerButton: {
    padding: 15,
    backgroundColor: "#07111f",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.18)",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 4,
  },
  speakerActive: {
    borderColor: "#67e8f9",
    backgroundColor: "rgba(8, 145, 178, 0.28)",
    shadowColor: "#22d3ee",
    shadowOpacity: 0.28,
  },
  speakerDisabled: { opacity: 0.55 },
  speakerPressed: { transform: [{ scale: 0.98 }], opacity: 0.92 },
  speakerText: { color: "#93a4bd", fontWeight: "900", fontSize: 16 },
  speakerTextActive: { color: "#e5ecff" },
  langTag: { color: "#67e8f9", fontSize: 11, fontWeight: "700", marginTop: 3 },
  stage: { color: "#93a4bd", fontSize: 12, marginTop: 5 },
  stageActive: { color: "#67e8f9" },
  stageListening: { color: "#6ee7b7" },
  stageTranslating: { color: "#fcd34d" },
  stageSpeaking: { color: "#d8b4fe" },
  tapHint: { color: "#4a5568", fontSize: 10, marginTop: 4 },
  conversationView: { flexDirection: "row", gap: 10, marginBottom: 10 },
  speakerCard: {
    flex: 1,
    padding: 12,
    backgroundColor: "#07111f",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.16)",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 3,
  },
  speakerCardLive: {
    borderColor: "rgba(103, 232, 249, 0.38)",
    backgroundColor: "rgba(8, 47, 73, 0.42)",
    shadowColor: "#22d3ee",
    shadowOpacity: 0.14,
    shadowRadius: 12,
  },
  cardTitle: { color: "#67e8f9", fontWeight: "900", fontSize: 14, marginBottom: 8 },
  textLabel: { color: "#93a4bd", fontSize: 12, marginTop: 8 },
  text: { color: "#e5ecff", fontSize: 14, marginTop: 4, lineHeight: 20 },
  translationText: { color: "#a5f3fc", fontSize: 14, marginTop: 4, lineHeight: 20, fontStyle: "italic" },
  historySection: {
    padding: 12,
    backgroundColor: "#07111f",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.10)",
    marginTop: 5,
  },
  historyTitle: { color: "#67e8f9", fontWeight: "900", fontSize: 14, marginBottom: 8 },
  historyTurn: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginBottom: 6,
    alignItems: "center",
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "transparent",
  },
  historyTurnLatest: {
    borderColor: "rgba(103, 232, 249, 0.28)",
    backgroundColor: "rgba(8, 47, 73, 0.35)",
  },
  historySpeaker: { color: "#67e8f9", fontWeight: "700", fontSize: 12, width: 20 },
  historySource: { color: "#e5ecff", fontSize: 12, flex: 1 },
  historyArrow: { color: "#4a5568", fontSize: 12 },
  historyTranslation: { color: "#a5f3fc", fontSize: 12, flex: 1, fontStyle: "italic" },
});
