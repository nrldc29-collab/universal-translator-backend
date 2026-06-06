import { Modal, View, Text, Pressable, ScrollView, SafeAreaView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import pickerStyles from "./LanguagePickerModal.styles";

const LANGUAGE_OPTIONS = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "es", label: "Spanish", flag: "🇪🇸" },
  { code: "ht", label: "Haitian Creole", flag: "🇭🇹" },
  { code: "fr", label: "French", flag: "🇫🇷" },
  { code: "de", label: "German", flag: "🇩🇪" },
  { code: "it", label: "Italian", flag: "🇮🇹" },
  { code: "pt", label: "Portuguese", flag: "🇧🇷" },
  { code: "nl", label: "Dutch", flag: "🇳🇱" },
  { code: "ru", label: "Russian", flag: "🇷🇺" },
  { code: "zh", label: "Chinese", flag: "🇨🇳" },
  { code: "ja", label: "Japanese", flag: "🇯🇵" },
  { code: "ko", label: "Korean", flag: "🇰🇷" },
  { code: "ar", label: "Arabic", flag: "🇸🇦" },
  { code: "hi", label: "Hindi", flag: "🇮🇳" },
];

export { LANGUAGE_OPTIONS };

export default function LanguagePickerModal({ visible, title, selectedCode, onSelect, onClose }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={pickerStyles.backdrop}>
        <SafeAreaView style={pickerStyles.sheet}>
          <View style={pickerStyles.header}>
            <Text style={pickerStyles.title}>{title}</Text>
            <Pressable onPress={onClose} style={pickerStyles.closeBtn} accessibilityRole="button" accessibilityLabel="Close language picker">
              <Ionicons name="close" size={22} color="#e2e8f0" />
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={pickerStyles.list}>
            {LANGUAGE_OPTIONS.map((language) => {
              const active = language.code === selectedCode;
              return (
                <Pressable
                  key={language.code}
                  onPress={() => onSelect(language.code)}
                  style={({ pressed }) => [
                    pickerStyles.row,
                    active && pickerStyles.rowActive,
                    pressed && pickerStyles.rowPressed,
                  ]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  accessibilityLabel={language.label}
                >
                  <Text style={pickerStyles.flag}>{language.flag}</Text>
                  <Text style={[pickerStyles.label, active && pickerStyles.labelActive]}>{language.label}</Text>
                  {active ? <Ionicons name="checkmark-circle" size={20} color="#22d3ee" /> : null}
                </Pressable>
              );
            })}
          </ScrollView>
        </SafeAreaView>
      </View>
    </Modal>
  );
}
