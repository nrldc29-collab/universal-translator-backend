import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";

interface SettingsScreenProps {
  wsUrl: string;
  setWsUrl: (url: string) => void;
  sourceLanguage: string;
  setSourceLanguage: (lang: string) => void;
  targetLanguage: string;
  setTargetLanguage: (lang: string) => void;
  onClearData: () => void;
}

const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "ht", name: "Haitian Creole" },
];

export default function SettingsScreen({
  wsUrl,
  setWsUrl,
  sourceLanguage,
  setSourceLanguage,
  targetLanguage,
  setTargetLanguage,
  onClearData,
}: SettingsScreenProps) {
  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.subtitle}>Tune Anai without leaving the interpreter flow.</Text>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Backend Configuration</Text>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Backend URL</Text>
          <Text style={styles.value}>{wsUrl}</Text>
        </View>
      </View>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Language Preferences</Text>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Source Language</Text>
          <Text style={styles.value}>{LANGUAGES.find(l => l.code === sourceLanguage)?.name || sourceLanguage}</Text>
        </View>
        <View style={styles.chipRow}>
          {LANGUAGES.map((language) => (
            <Pressable
              key={`source-${language.code}`}
              style={[styles.chip, sourceLanguage === language.code && styles.chipActive]}
              onPress={() => setSourceLanguage(language.code)}
            >
              <Text style={[styles.chipText, sourceLanguage === language.code && styles.chipTextActive]}>{language.name}</Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Target Language</Text>
          <Text style={styles.value}>{LANGUAGES.find(l => l.code === targetLanguage)?.name || targetLanguage}</Text>
        </View>
        <View style={styles.chipRow}>
          {LANGUAGES.map((language) => (
            <Pressable
              key={`target-${language.code}`}
              style={[styles.chip, targetLanguage === language.code && styles.chipActive]}
              onPress={() => setTargetLanguage(language.code)}
            >
              <Text style={[styles.chipText, targetLanguage === language.code && styles.chipTextActive]}>{language.name}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.settingRow}>
          <Text style={styles.label}>Version</Text>
          <Text style={styles.value}>1.0.0</Text>
        </View>
        <View style={styles.settingRow}>
          <Text style={styles.label}>App</Text>
          <Text style={styles.value}>Anai Translator Mobile</Text>
        </View>
      </View>
      
      <View style={styles.dangerZone}>
        <Text style={styles.dangerTitle}>Danger Zone</Text>
        <Pressable style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]} onPress={onClearData}>
          <Text style={styles.buttonText}>Clear All Stored Data</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 28, fontWeight: "900", color: '#f8fafc', marginBottom: 4 },
  subtitle: { color: '#94a3b8', fontSize: 13, marginBottom: 18 },
  section: { backgroundColor: '#07111f', padding: 15, borderRadius: 22, marginBottom: 15, borderWidth: 1, borderColor: 'rgba(103, 232, 249, 0.16)' },
  sectionTitle: { color: '#67e8f9', fontSize: 13, fontWeight: '900', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.7 },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: 'rgba(148, 163, 184, 0.12)' },
  label: { color: '#93a4bd', fontSize: 14 },
  value: { color: '#e5ecff', fontSize: 14, fontWeight: '900', flexShrink: 1, textAlign: 'right' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10, marginBottom: 6 },
  chip: { paddingVertical: 8, paddingHorizontal: 10, borderRadius: 999, backgroundColor: 'rgba(15, 23, 42, 0.78)', borderWidth: 1, borderColor: 'rgba(148, 163, 184, 0.16)' },
  chipActive: { backgroundColor: 'rgba(20, 184, 166, 0.26)', borderColor: 'rgba(45, 212, 191, 0.46)' },
  chipText: { color: '#94a3b8', fontSize: 12, fontWeight: '800' },
  chipTextActive: { color: '#ccfbf1' },
  dangerZone: { backgroundColor: '#160b13', padding: 15, borderRadius: 22, marginBottom: 15, borderWidth: 1, borderColor: 'rgba(248, 113, 113, 0.45)' },
  dangerTitle: { color: '#f87171', fontSize: 13, fontWeight: '900', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.7 },
  button: { backgroundColor: '#dc2626', padding: 13, borderRadius: 999, alignItems: 'center', marginTop: 10 },
  buttonPressed: { transform: [{ scale: 0.98 }] },
  buttonText: { color: '#fff', fontWeight: '900', fontSize: 14 },
});