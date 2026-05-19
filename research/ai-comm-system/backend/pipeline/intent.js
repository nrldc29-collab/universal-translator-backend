function getIntent(text) {
  text = (text || "").toLowerCase();
  if (text.includes("how much")) return "price";
  if (text.includes("where")) return "location";
  if (text.includes("why")) return "question";
  return "general";
}

module.exports = { getIntent };
