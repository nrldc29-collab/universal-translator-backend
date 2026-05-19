function negotiate(agentA, agentB, messageA, messageB) {
  const clarityA = Number(messageA?.confidence || 0);
  const clarityB = Number(messageB?.confidence || 0);
  if (clarityA > clarityB + 0.2) return messageA;
  if (clarityB > clarityA + 0.2) return messageB;
  return {
    type: "merged_meaning",
    message: `Combined interpretation: ${messageA?.text || ""} + ${messageB?.text || ""}`,
    confidence: (clarityA + clarityB) / 2,
  };
}

module.exports = { negotiate };
