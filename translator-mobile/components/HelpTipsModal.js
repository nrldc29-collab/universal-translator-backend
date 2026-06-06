import { Modal, View, Text, Pressable, ScrollView, SafeAreaView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import helpStyles from "./HelpTipsModal.styles";

const TIPS = [
  { icon: "mic", title: "Start interpreting", body: "Tap the big mic button to begin. Speak naturally — the app listens, translates, and speaks back automatically." },
  { icon: "swap-horizontal", title: "Change languages", body: "Tap Person 1 or Person 2 to pick a language. Use the center swap button to flip direction." },
  { icon: "people", title: "Two-way mode", body: "With Two-way on, either person can speak and the app routes translation to the other language." },
  { icon: "settings-outline", title: "Server & account", body: "Open Settings (gear icon) to change your server URL, sign in, or adjust voice volume and speed." },
  { icon: "copy-outline", title: "Copy translation", body: "Tap the copy icon on the translation card to copy the latest translated text." },
];

export default function HelpTipsModal({ visible, onClose }) {
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={helpStyles.container}>
        <View style={helpStyles.header}>
          <Text style={helpStyles.title}>Quick tips</Text>
          <Pressable onPress={onClose} style={helpStyles.closeBtn} accessibilityRole="button" accessibilityLabel="Close help">
            <Ionicons name="close" size={22} color="#e2e8f0" />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={helpStyles.list}>
          {TIPS.map((tip) => (
            <View key={tip.title} style={helpStyles.card}>
              <View style={helpStyles.iconWrap}>
                <Ionicons name={tip.icon} size={20} color="#22d3ee" />
              </View>
              <View style={helpStyles.cardBody}>
                <Text style={helpStyles.cardTitle}>{tip.title}</Text>
                <Text style={helpStyles.cardText}>{tip.body}</Text>
              </View>
            </View>
          ))}
        </ScrollView>
        <Pressable onPress={onClose} style={helpStyles.doneBtn} accessibilityRole="button" accessibilityLabel="Done">
          <Text style={helpStyles.doneBtnText}>Got it</Text>
        </Pressable>
      </SafeAreaView>
    </Modal>
  );
}
