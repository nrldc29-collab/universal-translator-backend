import { StyleSheet } from "react-native";

export default StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(2, 6, 23, 0.72)",
  },
  sheet: {
    maxHeight: "72%",
    backgroundColor: "#0a0f1d",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.2)",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  title: {
    color: "#f8fafc",
    fontSize: 18,
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
    paddingHorizontal: 14,
    paddingBottom: 24,
    gap: 6,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderRadius: 16,
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "rgba(148, 163, 184, 0.14)",
  },
  rowActive: {
    backgroundColor: "#0f2d2b",
    borderColor: "rgba(34, 211, 238, 0.45)",
  },
  rowPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.99 }],
  },
  flag: {
    fontSize: 22,
  },
  label: {
    flex: 1,
    color: "#e2e8f0",
    fontSize: 16,
    fontWeight: "700",
  },
  labelActive: {
    color: "#a5f3fc",
  },
});
