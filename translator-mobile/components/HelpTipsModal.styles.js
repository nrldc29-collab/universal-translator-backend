import { StyleSheet } from "react-native";

export default StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#050711",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
  },
  title: {
    color: "#f8fafc",
    fontSize: 22,
    fontWeight: "900",
  },
  closeBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111827",
  },
  list: {
    padding: 16,
    gap: 10,
    paddingBottom: 24,
  },
  card: {
    flexDirection: "row",
    gap: 12,
    padding: 14,
    borderRadius: 18,
    backgroundColor: "#0a0f1d",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.18)",
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(34, 211, 238, 0.12)",
  },
  cardBody: {
    flex: 1,
    gap: 4,
  },
  cardTitle: {
    color: "#e2e8f0",
    fontSize: 15,
    fontWeight: "900",
  },
  cardText: {
    color: "#94a3b8",
    fontSize: 13,
    lineHeight: 19,
  },
  doneBtn: {
    marginHorizontal: 20,
    marginBottom: 20,
    backgroundColor: "#22d3ee",
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
  },
  doneBtnText: {
    color: "#07131f",
    fontSize: 15,
    fontWeight: "900",
  },
});
