import { View, Text, StyleSheet, Animated } from "react-native";
import { useAnimatedPresence } from "../hooks/useAnimatedPresence";
import { conversationContextTitle } from "../constants/productVoice";

interface SemanticContextProps {
  context: {
    last_intent?: string;
    conversation_mood?: string;
    topics?: string[];
  } | null;
}

export default function SemanticContext({ context }: SemanticContextProps) {
  const { mounted, style } = useAnimatedPresence(Boolean(context), { initialOffset: 8, duration: 220, exitDuration: 160 });

  if (!mounted || !context) return null;

  const { last_intent, conversation_mood, topics } = context;

  return (
    <Animated.View style={[styles.container, style]}>
      <Text style={styles.title}>{conversationContextTitle()}</Text>

      <View style={styles.row}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>Intent: {last_intent || "statement"}</Text>
        </View>
        <View style={[styles.badge, styles.moodBadge]}>
          <Text style={styles.badgeText}>Mood: {conversation_mood || "neutral"}</Text>
        </View>
      </View>

      {topics && topics.length > 0 ? (
        <View style={styles.topicsContainer}>
          <Text style={styles.topicsLabel}>Topics:</Text>
          <View style={styles.topicsRow}>
            {topics.slice(0, 5).map((topic, index) => (
              <View key={index} style={styles.topicChip}>
                <Text style={styles.topicText}>{topic}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 15,
    backgroundColor: "rgba(7, 17, 31, 0.95)",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.22)",
    marginBottom: 8,
    marginTop: 2,
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.1,
    shadowRadius: 14,
    elevation: 3,
  },
  title: {
    color: "#67e8f9",
    fontSize: 14,
    fontWeight: "900",
    marginBottom: 10,
    textTransform: "uppercase",
  },
  row: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 10,
  },
  badge: {
    flex: 1,
    padding: 8,
    backgroundColor: "rgba(8, 145, 178, 0.28)",
    borderRadius: 8,
    alignItems: "center",
  },
  moodBadge: {
    backgroundColor: "rgba(20, 184, 166, 0.24)",
  },
  badgeText: {
    color: "#e5ecff",
    fontSize: 12,
    fontWeight: "900",
  },
  topicsContainer: {
    marginTop: 5,
  },
  topicsLabel: {
    color: "#93a4bd",
    fontSize: 12,
    marginBottom: 6,
  },
  topicsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  topicChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: "rgba(15, 23, 42, 0.78)",
    borderRadius: 12,
  },
  topicText: {
    color: "#93a4bd",
    fontSize: 11,
  },
});
