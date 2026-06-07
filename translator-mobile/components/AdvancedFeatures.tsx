import { View, Text, StyleSheet, ScrollView } from "react-native";

interface AdvancedFeaturesProps {
  noiseLevel?: number;
  beamforming?: boolean;
  speakerDiarization?: boolean;
  contextMemory?: {
    technicalTerms?: string[];
    conversationTopics?: string[];
  };
  emotionalNuance?: {
    emotion?: string;
    tone?: string;
    prosodyScore?: number;
  };
  streamingStatus?: {
    sttPartial?: boolean;
    translationPartial?: boolean;
  };
}

export default function AdvancedFeatures({
  noiseLevel = 0,
  beamforming = false,
  speakerDiarization = false,
  contextMemory,
  emotionalNuance,
  streamingStatus,
}: AdvancedFeaturesProps) {
  const getNoiseLabel = () => {
    if (noiseLevel < 30) return { label: "Quiet", color: "#16a34a" };
    if (noiseLevel < 60) return { label: "Moderate", color: "#ca8a04" };
    return { label: "Loud", color: "#dc2626" };
  };

  const noise = getNoiseLabel();

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.container}>
      {/* Layer 1: Ultra-fast Speech */}
      <View style={[styles.card, styles.layer1]}>
        <Text style={styles.layerTitle}>Ultra-Fast Speech</Text>
        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: streamingStatus?.sttPartial ? "#16a34a" : "#6b7280" }]} />
          <Text style={styles.statusText}>STT Streaming</Text>
        </View>
        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: streamingStatus?.translationPartial ? "#16a34a" : "#6b7280" }]} />
          <Text style={styles.statusText}>Partial Translation</Text>
        </View>
      </View>

      {/* Layer 2: Chaotic Environments */}
      <View style={[styles.card, styles.layer2]}>
        <Text style={styles.layerTitle}>Chaotic Environments</Text>
        <View style={styles.statusRow}>
          <Text style={[styles.noiseLabel, { color: noise.color }]}>Noise: {noise.label}</Text>
        </View>
        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: beamforming ? "#16a34a" : "#6b7280" }]} />
          <Text style={styles.statusText}>Beamforming</Text>
        </View>
      </View>

      {/* Layer 3: Overlapping Crowds */}
      <View style={[styles.card, styles.layer3]}>
        <Text style={styles.layerTitle}>Overlapping Crowds</Text>
        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: speakerDiarization ? "#16a34a" : "#6b7280" }]} />
          <Text style={styles.statusText}>Speaker Diarization</Text>
        </View>
        <Text style={styles.hint}>Detects multiple speakers</Text>
      </View>

      {/* Layer 4: Technical Jargon */}
      <View style={[styles.card, styles.layer4]}>
        <Text style={styles.layerTitle}>Technical Jargon</Text>
        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: contextMemory?.technicalTerms?.length ? "#16a34a" : "#6b7280" }]} />
          <Text style={styles.statusText}>Context Memory</Text>
        </View>
        {contextMemory?.technicalTerms && (
          <Text style={styles.subtext}>
            Terms: {contextMemory.technicalTerms.slice(0, 3).join(", ")}
            {contextMemory.technicalTerms.length > 3 && "..."}
          </Text>
        )}
      </View>

      {/* Layer 5: Emotional Nuance */}
      <View style={[styles.card, styles.layer5]}>
        <Text style={styles.layerTitle}>Emotional Nuance</Text>
        <View style={styles.statusRow}>
          <Text style={styles.statusText}>Emotion: {emotionalNuance?.emotion || "neutral"}</Text>
        </View>
        <View style={styles.statusRow}>
          <Text style={styles.statusText}>Tone: {emotionalNuance?.tone || "normal"}</Text>
        </View>
        {emotionalNuance?.prosodyScore && (
          <View style={styles.prosodyBar}>
            <View style={[styles.prosodyFill, { width: `${emotionalNuance.prosodyScore}%` }]} />
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    marginBottom: 15,
    paddingHorizontal: 10,
  },
  card: {
    backgroundColor: 'rgba(7, 17, 31, 0.95)',
    padding: 12,
    borderRadius: 18,
    marginRight: 10,
    minWidth: 160,
    borderWidth: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 4,
  },
  layer1: { borderColor: '#67e8f9' },
  layer2: { borderColor: '#a78bfa' },
  layer3: { borderColor: '#2dd4bf' },
  layer4: { borderColor: '#facc15' },
  layer5: { borderColor: '#f472b6' },
  layerTitle: {
    color: '#e5ecff',
    fontSize: 13,
    fontWeight: '900',
    marginBottom: 8,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    color: '#93a4bd',
    fontSize: 12,
  },
  noiseLabel: {
    fontSize: 12,
    fontWeight: '900',
  },
  hint: {
    color: '#6b7280',
    fontSize: 11,
    fontStyle: 'italic',
  },
  subtext: {
    color: '#93a4bd',
    fontSize: 11,
    marginTop: 4,
  },
  prosodyBar: {
    height: 4,
    backgroundColor: '#1e293b',
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  prosodyFill: {
    height: '100%',
    backgroundColor: '#67e8f9',
    borderRadius: 2,
  },
});