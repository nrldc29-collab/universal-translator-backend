import { StyleSheet } from "react-native";

export default StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#050711",
  },
  flex: {
    flex: 1,
  },
  scroll: {
    padding: 20,
    paddingBottom: 40,
    gap: 14,
  },
  hero: {
    alignItems: "center",
    gap: 10,
    marginBottom: 8,
    marginTop: 12,
  },
  title: {
    color: "#f8fafc",
    fontSize: 28,
    fontWeight: "900",
    textAlign: "center",
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
    maxWidth: 340,
  },
  card: {
    backgroundColor: "#0a0f1d",
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.2)",
    gap: 10,
  },
  cardTitle: {
    color: "#67e8f9",
    fontSize: 13,
    fontWeight: "900",
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  hint: {
    color: "#94a3b8",
    fontSize: 13,
    lineHeight: 19,
  },
  input: {
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.28)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: "#f8fafc",
    fontSize: 15,
  },
  primaryBtn: {
    backgroundColor: "#22d3ee",
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  continueBtn: {
    marginTop: 8,
  },
  secondaryBtn: {
    backgroundColor: "rgba(20, 184, 166, 0.2)",
    borderWidth: 1,
    borderColor: "rgba(45, 212, 191, 0.45)",
    borderRadius: 999,
    paddingVertical: 12,
    alignItems: "center",
  },
  primaryBtnText: {
    color: "#07131f",
    fontSize: 15,
    fontWeight: "900",
  },
  secondaryBtnText: {
    color: "#ccfbf1",
    fontSize: 14,
    fontWeight: "900",
  },
  btnPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.92,
  },
  btnDisabled: {
    opacity: 0.6,
  },
  errorText: {
    color: "#fca5a5",
    fontSize: 13,
    fontWeight: "700",
  },
});
