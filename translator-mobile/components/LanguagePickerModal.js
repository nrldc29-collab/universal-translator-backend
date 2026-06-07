import { useMemo, useState } from "react";
import { Modal, View, Text, TextInput, Pressable, ScrollView, SafeAreaView } from "react-native";
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
  const [query, setQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);

  const filteredLanguages = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return LANGUAGE_OPTIONS;
    return LANGUAGE_OPTIONS.filter(
      (language) =>
        language.label.toLowerCase().includes(needle) ||
        language.code.toLowerCase().includes(needle)
    );
  }, [query]);

  const titleParts = String(title || "Language").split(" ");
  const titleLead = titleParts.slice(0, -1).join(" ");
  const titleAccent = titleParts.length > 1 ? titleParts[titleParts.length - 1] : null;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
      onShow={() => setQuery("")}
    >
      <View style={pickerStyles.backdrop}>
        <Pressable style={pickerStyles.backdropTap} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close language picker" />
        <Pressable onPress={() => {}} style={pickerStyles.sheetWrap}>
        <SafeAreaView style={pickerStyles.sheet}>
          <View style={pickerStyles.handle} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />
          <View style={pickerStyles.header}>
            <Text style={pickerStyles.title}>
              {titleAccent ? (
                <>
                  {titleLead}{" "}
                  <Text style={pickerStyles.titleAccent}>{titleAccent}</Text>
                </>
              ) : (
                title
              )}
            </Text>
            <Pressable
              onPress={onClose}
              style={({ pressed }) => [pickerStyles.closeBtn, pressed && pickerStyles.closeBtnPressed]}
              accessibilityRole="button"
              accessibilityLabel="Close language picker"
            >
              <Ionicons name="close" size={22} color="#e2e8f0" />
            </Pressable>
          </View>
          <View style={[pickerStyles.searchRow, searchFocused && pickerStyles.searchRowFocused]}>
            <Ionicons name="search" size={16} color={searchFocused ? "#67e8f9" : "#64748b"} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search languages"
              placeholderTextColor="#64748b"
              autoCapitalize="none"
              autoCorrect={false}
              style={pickerStyles.searchInput}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              accessibilityLabel="Search languages"
            />
            {query ? (
              <Pressable onPress={() => setQuery("")} hitSlop={8} accessibilityRole="button" accessibilityLabel="Clear search">
                <Ionicons name="close-circle" size={18} color="#64748b" />
              </Pressable>
            ) : null}
          </View>
          <ScrollView contentContainerStyle={pickerStyles.list} keyboardShouldPersistTaps="handled">
            {filteredLanguages.length === 0 ? (
              <View style={pickerStyles.emptyWrap}>
                <View style={pickerStyles.emptyIconRing}>
                  <Ionicons name="search-outline" size={24} color="#67e8f9" />
                </View>
                <Text style={pickerStyles.emptyText}>No languages match your search.</Text>
              </View>
            ) : (
              filteredLanguages.map((language) => {
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
              })
            )}
          </ScrollView>
        </SafeAreaView>
        </Pressable>
      </View>
    </Modal>
  );
}
