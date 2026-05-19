import { View, Text, StyleSheet } from "react-native";

interface SemanticContextProps {
  context: {
    last_intent?: string;
    conversation_mood?: string;
    topics?: string[];
  } | null;
}

export default function SemanticContext({ context }: SemanticContextProps) {
  if (!context) return null;

  const { last_intent, conversation_mood, topics } = context;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Conversation Brain</Text>
      
      <View style={styles.row}>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>Intent: {last_intent || "statement"}</Text>
        </View>
        <View style={[styles.badge, styles.moodBadge]}>
          <Text style={styles.badgeText}>Mood: {conversation_mood || "neutral"}</Text>
        </View>
      </View>
      
      {topics && topics.length > 0 && (
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
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 15,
    backgroundColor: '#07111f',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(103, 232, 249, 0.18)',
    marginBottom: 15,
  },
  title: {
    color: '#67e8f9',
    fontSize: 14,
    fontWeight: '900',
    marginBottom: 10,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  badge: {
    flex: 1,
    padding: 8,
    backgroundColor: 'rgba(8, 145, 178, 0.28)',
    borderRadius: 8,
    alignItems: 'center',
  },
  moodBadge: {
    backgroundColor: 'rgba(20, 184, 166, 0.24)',
  },
  badgeText: {
    color: '#e5ecff',
    fontSize: 12,
    fontWeight: '900',
  },
  topicsContainer: {
    marginTop: 5,
  },
  topicsLabel: {
    color: '#93a4bd',
    fontSize: 12,
    marginBottom: 6,
  },
  topicsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  topicChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: 'rgba(15, 23, 42, 0.78)',
    borderRadius: 12,
  },
  topicText: {
    color: '#93a4bd',
    fontSize: 11,
  },
});