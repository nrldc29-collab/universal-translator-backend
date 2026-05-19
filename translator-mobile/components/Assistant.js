/**
 * NAIA Assistant — mobile chat component.
 *
 * Renders a floating "Ask NAIA" pill at the bottom of the screen.
 * Tapping it opens a chat overlay that talks to POST /api/assistant/chat
 * on the backend. If `getTranslationContext` is provided, the latest
 * translation is attached to outgoing messages so the assistant can
 * answer follow-ups like "make that more formal."
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
  const inputRef = useRef(null);

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
          style={styles.fab}
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
              <View>
                <Text style={styles.title} accessibilityRole="header">
                  NAIA Assistant
                </Text>
                <Text style={styles.status}>
                  {available === false
                    ? "Unavailable"
                    : available === true
                    ? "Ready"
                    : "Connecting\u2026"}
                </Text>
              </View>
              <View style={{ flexDirection: "row" }}>
                <Pressable
                  onPress={() => setMessages([])}
                  style={styles.ghostBtn}
                  accessibilityLabel="Clear chat history"
                  accessibilityRole="button"
                >
                  <Text style={styles.ghostBtnText}>Clear</Text>
                </Pressable>
                <Pressable
                  onPress={() => setOpen(false)}
                  style={styles.ghostBtn}
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
                  style={styles.retryBtn}
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
                <Text style={styles.placeholder}>
                  Ask a question about your translation, request a rephrase, or get a language tip.
                </Text>
              )}
              {messages.map((msg, idx) => (
                <Bubble key={idx} role={msg.role} text={msg.text} />
              ))}
              {pending && (
                <View style={styles.pendingRow} accessibilityLabel="Assistant is thinking">
                  <ActivityIndicator color="#94a3b8" />
                </View>
              )}
            </ScrollView>

            <View style={styles.inputRow}>
              <TextInput
                ref={inputRef}
                value={draft}
                onChangeText={setDraft}
                placeholder="Ask the assistant\u2026"
                placeholderTextColor="#64748b"
                multiline
                editable={available !== false && !pending}
                style={styles.input}
                returnKeyType="send"
                onSubmitEditing={handleSubmitEditing}
                blurOnSubmit={false}
                accessibilityLabel="Type a message to the assistant"
              />
              <Pressable
                onPress={send}
                disabled={pending || available === false || !draft.trim()}
                style={[
                  styles.sendBtn,
                  (pending || available === false || !draft.trim()) && styles.sendBtnDisabled,
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
      style={[styles.bubbleWrap, { alignSelf: isUser ? "flex-end" : "flex-start" }]}
      accessibilityLabel={`${isUser ? "You" : isSystem ? "System" : "NAIA"}: ${text}`}
    >
      <View style={[styles.bubble, isUser && styles.bubbleUser, isSystem && styles.bubbleSystem]}>
        <Text style={styles.bubbleText}>{text}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: "absolute",
    right: 16,
    bottom: 24,
    backgroundColor: "#2563eb",
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 999,
    elevation: 6,
    shadowColor: "#000",
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  fabText: { color: "#f8fafc", fontWeight: "600" },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(2, 6, 23, 0.6)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#0f172a",
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    maxHeight: "85%",
    minHeight: 400,
    paddingBottom: 12,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#1e293b",
  },
  title: { color: "#f1f5f9", fontSize: 16, fontWeight: "700" },
  status: { color: "#94a3b8", fontSize: 11, marginTop: 2 },
  ghostBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginLeft: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#334155",
  },
  ghostBtnText: { color: "#cbd5e1", fontSize: 12 },
  errorBar: {
    padding: 10,
    backgroundColor: "#1f1212",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  errorText: { color: "#fca5a5", fontSize: 12, flex: 1 },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "#3f1d1d",
    borderRadius: 6,
    marginLeft: 8,
  },
  retryBtnText: { color: "#fca5a5", fontSize: 12, fontWeight: "600" },
  scroll: { flex: 1 },
  scrollContent: { padding: 12, gap: 8 },
  placeholder: { color: "#94a3b8", fontSize: 13 },
  pendingRow: { alignItems: "flex-start", paddingVertical: 6 },
  bubbleWrap: { maxWidth: "85%" },
  bubble: {
    backgroundColor: "#1e293b",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 10,
  },
  bubbleUser: { backgroundColor: "#2563eb" },
  bubbleSystem: { backgroundColor: "#3f1d1d" },
  bubbleText: { color: "#f8fafc", fontSize: 13 },
  inputRow: {
    flexDirection: "row",
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: "#1e293b",
    gap: 8,
    alignItems: "flex-end",
  },
  input: {
    flex: 1,
    backgroundColor: "#0b1220",
    color: "#f1f5f9",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#334155",
    padding: 10,
    fontSize: 13,
    minHeight: 44,
    maxHeight: 120,
  },
  sendBtn: {
    backgroundColor: "#2563eb",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 8,
    justifyContent: "center",
  },
  sendBtnDisabled: { opacity: 0.5 },
  sendBtnText: { color: "#f8fafc", fontWeight: "600" },
});
