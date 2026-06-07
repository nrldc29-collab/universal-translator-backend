/**
 * NAIA Assistant — mobile chat component.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  Pressable,
  StyleSheet,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

function buildAuthHeaders(token, extra = {}) {
  if (!token) return extra;
  return { ...extra, Authorization: `Bearer ${token}` };
}

export default function Assistant({ apiUrl = "", authToken = "", getTranslationContext }) {
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(null);
  const [unavailableReason, setUnavailableReason] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const sessionIdRef = useRef(null);
  const scrollRef = useRef(null);

  if (!sessionIdRef.current) {
    sessionIdRef.current = `m-${Math.random().toString(36).slice(2)}-${Date.now()}`;
  }

  const checkHealth = useCallback(() => {
    if (!apiUrl) return;
    setAvailable(null);
    setUnavailableReason("");
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/api/assistant/health`, {
          headers: buildAuthHeaders(authToken),
        });
        const body = await res.json().catch(() => ({}));
        setAvailable(Boolean(body.available));
        setUnavailableReason(body.error || "");
      } catch (err) {
        setAvailable(false);
        setUnavailableReason(String(err?.message || err));
      }
    })();
  }, [apiUrl, authToken]);

  useEffect(() => {
    if (open && available === null) checkHealth();
  }, [open, available, checkHealth]);

  useEffect(() => {
    if (scrollRef.current) {
      setTimeout(() => scrollRef.current?.scrollToEnd?.({ animated: true }), 50);
    }
  }, [messages, pending, open]);

  async function send() {
    const text = draft.trim();
    if (!text || pending || !apiUrl) return;
    setDraft("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setPending(true);

    const ctx = typeof getTranslationContext === "function" ? getTranslationContext() : null;

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      const res = await fetch(`${apiUrl}/api/assistant/chat`, {
        method: "POST",
        headers: buildAuthHeaders(authToken, { "Content-Type": "application/json" }),
        body: JSON.stringify({
          message: text,
          session_id: sessionIdRef.current,
          translation_context: ctx || undefined,
        }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          body?.detail ||
          (res.status === 503
            ? "Assistant is not available right now."
            : res.status === 429
            ? "Too many requests. Please wait a moment."
            : `Request failed (HTTP ${res.status}).`);
        setMessages((prev) => [...prev, { role: "system", text: detail }]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: body.response || "(no response)" },
        ]);
      }
    } catch (err) {
      const msg =
        err?.name === "AbortError"
          ? "Request timed out. Try again."
          : `Network error: ${err?.message || err}`;
      setMessages((prev) => [...prev, { role: "system", text: msg }]);
    } finally {
      setPending(false);
    }
  }

  function handleSubmitEditing() {
    if (!pending && available !== false && draft.trim()) send();
  }

  return (
    <>
      {!open && (
        <Pressable
          style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}
          onPress={() => setOpen(true)}
          accessibilityLabel="Open NAIA assistant"
          accessibilityRole="button"
        >
          <Text style={styles.fabText}>Ask NAIA</Text>
        </Pressable>
      )}

      <Modal visible={open} animationType="slide" transparent onRequestClose={() => setOpen(false)}>
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <View style={styles.modalCard}>
            <View style={styles.header}>
              <View style={styles.headerText}>
                <Text style={styles.title} accessibilityRole="header">
                  NAIA Assistant
                </Text>
                <Text style={[styles.status, available === true && styles.statusReady, available === false && styles.statusBad]}>
                  {available === false
                    ? "Unavailable"
                    : available === true
                    ? "Ready"
                    : "Connecting\u2026"}
                </Text>
              </View>
              <View style={styles.headerActions}>
                <Pressable
                  onPress={() => setMessages([])}
                  style={({ pressed }) => [styles.ghostBtn, pressed && styles.ghostBtnPressed]}
                  accessibilityLabel="Clear chat history"
                  accessibilityRole="button"
                >
                  <Text style={styles.ghostBtnText}>Clear</Text>
                </Pressable>
                <Pressable
                  onPress={() => setOpen(false)}
                  style={({ pressed }) => [styles.ghostBtn, pressed && styles.ghostBtnPressed]}
                  accessibilityLabel="Close assistant"
                  accessibilityRole="button"
                >
                  <Text style={styles.ghostBtnText}>Close</Text>
                </Pressable>
              </View>
            </View>

            {available === false && (
              <View style={styles.errorBar}>
                <Text style={styles.errorText}>
                  Assistant is unavailable.{unavailableReason ? ` ${unavailableReason}` : ""}
                </Text>
                <Pressable
                  onPress={checkHealth}
                  style={({ pressed }) => [styles.retryBtn, pressed && styles.retryBtnPressed]}
                  accessibilityLabel="Retry connection"
                  accessibilityRole="button"
                >
                  <Text style={styles.retryBtnText}>Retry</Text>
                </Pressable>
              </View>
            )}

            <ScrollView
              ref={scrollRef}
              style={styles.scroll}
              contentContainerStyle={styles.scrollContent}
              keyboardShouldPersistTaps="handled"
            >
              {messages.length === 0 && (
                <View style={styles.placeholderWrap}>
                  <View style={styles.placeholderIcon} accessibilityElementsHidden>
                    <Ionicons name="sparkles-outline" size={22} color="#67e8f9" />
                  </View>
                  <Text style={styles.placeholder}>
                    Ask a question about your translation, request a rephrase, or get a language tip.
                  </Text>
                </View>
              )}
              {messages.map((msg, idx) => (
                <Bubble key={idx} role={msg.role} text={msg.text} />
              ))}
              {pending && (
                <View style={styles.pendingRow} accessibilityLabel="Assistant is thinking">
                  <ActivityIndicator color="#67e8f9" />
                  <Text style={styles.pendingText}>Thinking…</Text>
                </View>
              )}
            </ScrollView>

            <View style={styles.inputRow}>
              <TextInput
                value={draft}
                onChangeText={setDraft}
                placeholder="Ask the assistant…"
                placeholderTextColor="#64748b"
                multiline
                editable={available !== false && !pending}
                style={[styles.input, draft.trim() && styles.inputFilled]}
                returnKeyType="send"
                onSubmitEditing={handleSubmitEditing}
                blurOnSubmit={false}
                accessibilityLabel="Type a message to the assistant"
              />
              <Pressable
                onPress={send}
                disabled={pending || available === false || !draft.trim()}
                style={({ pressed }) => [
                  styles.sendBtn,
                  (pending || available === false || !draft.trim()) && styles.sendBtnDisabled,
                  pressed && !pending && draft.trim() && styles.sendBtnPressed,
                ]}
                accessibilityLabel="Send message"
                accessibilityRole="button"
              >
                <Text style={styles.sendBtnText}>Send</Text>
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

function Bubble({ role, text }) {
  const isUser = role === "user";
  const isSystem = role === "system";
  return (
    <View
      style={[styles.bubbleWrap, isUser ? styles.bubbleWrapUser : styles.bubbleWrapOther]}
      accessibilityLabel={`${isUser ? "You" : isSystem ? "System" : "NAIA"}: ${text}`}
    >
      <View style={[styles.bubble, isUser && styles.bubbleUser, isSystem && styles.bubbleSystem]}>
        <Text style={[styles.bubbleText, isUser && styles.bubbleTextUser]}>{text}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 999,
    backgroundColor: "#0891b2",
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.38)",
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 8,
  },
  fabPressed: {
    transform: [{ scale: 0.97 }],
    opacity: 0.92,
  },
  fabText: { color: "#f8fafc", fontWeight: "900", fontSize: 14 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(2, 6, 23, 0.72)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#0a0f1d",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.22)",
    borderBottomWidth: 0,
    maxHeight: "85%",
    minHeight: 400,
    paddingBottom: 12,
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 16,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(148, 163, 184, 0.14)",
  },
  headerText: { flex: 1, minWidth: 0 },
  headerActions: { flexDirection: "row" },
  title: { color: "#f8fafc", fontSize: 17, fontWeight: "900" },
  status: { color: "#94a3b8", fontSize: 11, fontWeight: "800", marginTop: 2 },
  statusReady: { color: "#6ee7b7" },
  statusBad: { color: "#fca5a5" },
  ghostBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginLeft: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.22)",
    backgroundColor: "rgba(15, 23, 42, 0.65)",
  },
  ghostBtnPressed: {
    backgroundColor: "rgba(30, 41, 59, 0.9)",
    borderColor: "rgba(103, 232, 249, 0.28)",
    transform: [{ scale: 0.97 }],
  },
  ghostBtnText: { color: "#cbd5e1", fontSize: 12, fontWeight: "800" },
  errorBar: {
    padding: 10,
    backgroundColor: "rgba(31, 18, 21, 0.95)",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(248, 113, 113, 0.22)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  errorText: { color: "#fca5a5", fontSize: 12, flex: 1, fontWeight: "700", lineHeight: 17 },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "rgba(248, 113, 113, 0.12)",
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(248, 113, 113, 0.28)",
    marginLeft: 8,
  },
  retryBtnPressed: { opacity: 0.88, transform: [{ scale: 0.97 }] },
  retryBtnText: { color: "#fca5a5", fontSize: 12, fontWeight: "900" },
  scroll: { flex: 1 },
  scrollContent: { padding: 12, gap: 8, paddingBottom: 16 },
  placeholderWrap: {
    padding: 16,
    borderRadius: 14,
    backgroundColor: "rgba(15, 23, 42, 0.55)",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.12)",
    alignItems: "center",
    gap: 10,
  },
  placeholderIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(34, 211, 238, 0.1)",
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.28)",
  },
  placeholder: { color: "#94a3b8", fontSize: 13, lineHeight: 19, textAlign: "center" },
  pendingRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
  pendingText: { color: "#67e8f9", fontSize: 12, fontWeight: "800" },
  bubbleWrap: { maxWidth: "85%" },
  bubbleWrapUser: { alignSelf: "flex-end" },
  bubbleWrapOther: { alignSelf: "flex-start" },
  bubble: {
    backgroundColor: "rgba(17, 24, 39, 0.95)",
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.16)",
  },
  bubbleUser: {
    backgroundColor: "rgba(8, 145, 178, 0.35)",
    borderColor: "rgba(103, 232, 249, 0.35)",
    borderBottomRightRadius: 4,
  },
  bubbleSystem: {
    backgroundColor: "rgba(40, 28, 8, 0.85)",
    borderColor: "rgba(251, 191, 36, 0.28)",
  },
  bubbleText: { color: "#e2e8f0", fontSize: 13, lineHeight: 19 },
  bubbleTextUser: { color: "#f8fafc" },
  inputRow: {
    flexDirection: "row",
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: "rgba(148, 163, 184, 0.14)",
    gap: 8,
    alignItems: "flex-end",
  },
  input: {
    flex: 1,
    backgroundColor: "#111827",
    color: "#f1f5f9",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.22)",
    padding: 10,
    fontSize: 13,
    minHeight: 44,
    maxHeight: 120,
  },
  inputFilled: {
    borderColor: "rgba(103, 232, 249, 0.35)",
    backgroundColor: "#0f172a",
  },
  sendBtn: {
    backgroundColor: "#22d3ee",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 14,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(103, 232, 249, 0.45)",
    shadowColor: "#22d3ee",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.28,
    shadowRadius: 8,
    elevation: 4,
  },
  sendBtnPressed: { transform: [{ scale: 0.97 }], opacity: 0.92 },
  sendBtnDisabled: { opacity: 0.45, shadowOpacity: 0 },
  sendBtnText: { color: "#07131f", fontWeight: "900", fontSize: 13 },
});
