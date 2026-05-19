const { getConfig } = require("../services/config");

function decide({ confidence, ambiguity, intent }) {
  const cfg = getConfig();
  const confLimit = typeof cfg.confidenceThreshold === 'number' ? cfg.confidenceThreshold : 0.45;
  const ambiguityLimit = typeof cfg.ambiguityThreshold === 'number' ? cfg.ambiguityThreshold : 0.7;

  if (confidence < confLimit || ambiguity > ambiguityLimit) {
    return { type: "clarification", message: "Can you rephrase that?" };
  }
  if (intent === "emotional" || intent === "emotional_statement") {
    return { type: "supportive_response", message: "I understand how you feel." };
  }
  const mode = cfg.responseMode === 'fast' ? 'fast' : 'normal';
  return { type: "response", mode };
}

module.exports = { decide };
