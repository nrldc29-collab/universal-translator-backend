function confidenceScore({ stt, llm, contextMatch }) {
  const sttConf = (stt && stt.confidence) || 0.8;
  const ambig = (llm && typeof llm.ambiguity_score === 'number') ? llm.ambiguity_score : 0.3;
  const ctx = typeof contextMatch === 'number' ? contextMatch : 0.6;
  return (sttConf * 0.3) + ((1 - ambig) * 0.5) + (ctx * 0.2);
}

module.exports = { confidenceScore };
