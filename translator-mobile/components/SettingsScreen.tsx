import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";

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
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
  { code: "pt", name: "Portuguese" },
  { code: "nl", name: "Dutch" },
  { code: "ru", name: "Russian" },
  { code: "zh", name: "Chinese" },
  { code: "ja", name: "Japanese" },
  { code: "ko", name: "Korean" },
  { code: "ar", name: "Arabic" },
  { code: "hi", name: "Hindi" },
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
        <View style={styles.settingRow}>
          <Text style={styles.label}>Target Language</Text>
          <Text style={styles.value}>{LANGUAGES.find(l => l.code === targetLanguage)?.name || targetLanguage}</Text>
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
          <Text style={styles.value}>Universal Translator Mobile</Text>
        </View>
      </View>
      
      <View style={styles.dangerZone}>
        <Text style={styles.dangerTitle}>Danger Zone</Text>
        <TouchableOpacity style={styles.button} onPress={onClearData}>
          <Text style={styles.buttonText}>Clear All Stored Data</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 24, fontWeight: "bold", color: '#e5ecff', marginBottom: 20 },
  section: { backgroundColor: '#0c1729', padding: 15, borderRadius: 12, marginBottom: 15, borderWidth: 1, borderColor: '#24344f' },
  sectionTitle: { color: '#60a5fa', fontSize: 14, fontWeight: 'bold', marginBottom: 10, textTransform: 'uppercase' },
  settingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1e293b' },
  label: { color: '#93a4bd', fontSize: 14 },
  value: { color: '#e5ecff', fontSize: 14, fontWeight: 'bold' },
  dangerZone: { backgroundColor: '#0c1729', padding: 15, borderRadius: 12, marginBottom: 15, borderWidth: 1, borderColor: '#dc2626' },
  dangerTitle: { color: '#dc2626', fontSize: 14, fontWeight: 'bold', marginBottom: 10, textTransform: 'uppercase' },
  button: { backgroundColor: '#dc2626', padding: 12, borderRadius: 8, alignItems: 'center', marginTop: 10 },
  buttonText: { color: '#fff', fontWeight: 'bold', fontSize: 14 },
});