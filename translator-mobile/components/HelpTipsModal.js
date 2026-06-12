import { Modal, View, Text, Pressable, ScrollView, SafeAreaView } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import helpStyles from "./HelpTipsModal.styles";
import NeoBrandMark from "./NeoBrandMark";
import HelpTipCard from "./HelpTipCard";
import { helpTips } from "../constants/productVoice";

const TIPS = helpTips();

export default function HelpTipsModal({ visible, onClose, onOpenAssistant }) {
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView style={helpStyles.container}>
        <LinearGradient
          colors={["rgba(103, 232, 249, 0.35)", "transparent"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={helpStyles.headerShine}
          pointerEvents="none"
        />
        <View style={helpStyles.header}>
          <View style={helpStyles.headerTitleWrap}>
            <NeoBrandMark subline="HELP" compact />
            <Text style={helpStyles.title}>
              Quick <Text style={helpStyles.titleAccent}>tips</Text>
            </Text>
            <Text style={helpStyles.subtitle}>Bridge languages with confidence</Text>
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
            <HelpTipCard key={tip.title} tip={tip} index={index} visible={visible} />
          ))}
        </ScrollView>
        {onOpenAssistant ? (
          <Pressable
            onPress={onOpenAssistant}
            style={({ pressed }) => [helpStyles.assistantBtn, pressed && helpStyles.assistantBtnPressed]}
            accessibilityRole="button"
            accessibilityLabel="Open NAIA assistant"
          >
            <Ionicons name="sparkles-outline" size={16} color="#07131f" />
            <Text style={helpStyles.assistantBtnText}>Open NAIA assistant</Text>
          </Pressable>
        ) : null}
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
