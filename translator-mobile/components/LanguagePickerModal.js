import { useMemo, useState } from "react";
import { Modal, View, Text, TextInput, Pressable, ScrollView, SafeAreaView } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import pickerStyles from "./LanguagePickerModal.styles";
import LanguagePickerRow from "./LanguagePickerRow";

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

export default function LanguagePickerModal({ visible, title, selectedCode, onSelect, onClose, variant = "target" }) {
  const isSource = variant === "source";
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
        <SafeAreaView style={[pickerStyles.sheet, isSource ? pickerStyles.sheetSource : pickerStyles.sheetTarget]}>
          <LinearGradient
            colors={isSource
              ? ["rgba(148, 163, 184, 0.28)", "transparent"]
              : ["rgba(103, 232, 249, 0.35)", "transparent"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={pickerStyles.headerShine}
            pointerEvents="none"
          />
          <View style={pickerStyles.handle} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" />
          <View style={pickerStyles.header}>
            <View style={pickerStyles.titleWrap}>
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
              <View style={[pickerStyles.variantBadge, isSource ? pickerStyles.variantBadgeSource : pickerStyles.variantBadgeTarget]}>
                <Text style={[pickerStyles.variantBadgeText, !isSource && pickerStyles.variantBadgeTargetText]}>
                  {isSource ? "SPEAK" : "TRANSLATE"}
                </Text>
              </View>
            </View>
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
          <Text style={pickerStyles.resultCount}>
            {filteredLanguages.length} language{filteredLanguages.length === 1 ? "" : "s"}
            {query ? ` matching “${query.trim()}”` : ""}
          </Text>
          <ScrollView contentContainerStyle={pickerStyles.list} keyboardShouldPersistTaps="handled">
            {filteredLanguages.length === 0 ? (
              <View style={pickerStyles.emptyWrap}>
                <View style={pickerStyles.emptyIconRing}>
                  <Ionicons name="search-outline" size={24} color="#67e8f9" />
                </View>
                <Text style={pickerStyles.emptyText}>No languages match your search.</Text>
              </View>
            ) : (
              filteredLanguages.map((language, index) => (
                <LanguagePickerRow
                  key={language.code}
                  language={language}
                  index={index}
                  visible={visible}
                  active={language.code === selectedCode}
                  isSource={isSource}
                  onSelect={onSelect}
                />
              ))
            )}
          </ScrollView>
        </SafeAreaView>
        </Pressable>
      </View>
    </Modal>
  );
}
