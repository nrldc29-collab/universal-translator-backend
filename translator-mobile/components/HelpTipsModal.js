import { Modal, View, Text, Pressable, ScrollView, SafeAreaView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import helpStyles from "./HelpTipsModal.styles";

const TIPS = [
  { icon: "mic", title: "Start interpreting", body: "Tap Start to connect, then speak naturally. The app listens, translates, and speaks back automatically." },
  { icon: "cloud-offline-outline", title: "Connect first", body: "If you see Offline, tap Connect in the dock or open Settings to check your server URL." },
  { icon: "swap-horizontal", title: "Change languages", body: "Tap Person 1 or Person 2 to pick a language. Use the center swap button to flip direction." },
  { icon: "people", title: "Two-way mode", body: "With Two-way on, either person can speak and the app routes translation to the other language." },
  { icon: "settings-outline", title: "Server & account", body: "Open Settings (gear icon) to change your server URL, sign in, or adjust voice volume and speed." },
  { icon: "share-outline", title: "Share or copy", body: "Use the share and copy icons on each card to send or save what was said and translated." },
  { icon: "help-circle-outline", title: "Status strip", body: "Tap the status bar at the bottom to switch between simple and detailed connection info." },
];

export default function HelpTipsModal({ visible, onClose }) {
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={helpStyles.container}>
        <View style={helpStyles.header}>
          <View style={helpStyles.headerTitleWrap}>
            <Text style={helpStyles.title}>
              Quick <Text style={helpStyles.titleAccent}>tips</Text>
            </Text>
            <Text style={helpStyles.subtitle}>Everything you need for smooth conversations</Text>
          </View>
          <Pressable
            onPress={onClose}
            style={({ pressed }) => [helpStyles.closeBtn, pressed && helpStyles.closeBtnPressed]}
            accessibilityRole="button"
            accessibilityLabel="Close help"
          >
            <Ionicons name="close" size={22} color="#e2e8f0" />
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={helpStyles.list}>
          {TIPS.map((tip, index) => (
            <Pressable
              key={tip.title}
              style={({ pressed }) => [helpStyles.card, pressed && helpStyles.cardPressed]}
            >
              <View style={helpStyles.tipNumberWrap}>
                <Text style={helpStyles.tipNumber}>{index + 1}</Text>
              </View>
              <View style={helpStyles.iconWrap}>
                <Ionicons name={tip.icon} size={20} color="#22d3ee" />
              </View>
              <View style={helpStyles.cardBody}>
                <Text style={helpStyles.cardTitle}>{tip.title}</Text>
                <Text style={helpStyles.cardText}>{tip.body}</Text>
              </View>
            </Pressable>
          ))}
        </ScrollView>
        <Pressable
          onPress={onClose}
          style={({ pressed }) => [helpStyles.doneBtn, pressed && helpStyles.doneBtnPressed]}
          accessibilityRole="button"
          accessibilityLabel="Done"
        >
          <Text style={helpStyles.doneBtnText}>Got it</Text>
        </Pressable>
      </SafeAreaView>
    </Modal>
  );
}
