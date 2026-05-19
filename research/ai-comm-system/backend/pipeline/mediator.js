const { transcribe } = require("./stt");
const { analyze } = require("./llmAnalysis");
const { confidenceScore } = require("./confidence");
const { decide } = require("./brain");
const { translate } = require("./translator");
const { saveMemory } = require("./memory");
const { detectAmbiguity } = require("./ambiguity");

async function processPipeline(input) {
  // 1. STT (if audio path)
  const stt = input && input.audio
    ? await transcribe(input.audio)
    : { text: (input && input.text) || "", confidence: 0.9 };

  // 2. LLM analysis
  const analysis = await analyze(stt.text, { sessionId: input?.sessionId });
  // Local ambiguity detection (word-boundary based) for robustness
  const localAmb = detectAmbiguity(stt.text);
  const combinedAmbiguity = Math.max(
    typeof analysis.ambiguity_score === 'number' ? analysis.ambiguity_score : 0,
    typeof localAmb.score === 'number' ? localAmb.score : 0
  );

  // 3. Confidence (multi-signal)
  const confidence = confidenceScore({
    stt,
    llm: analysis,
    contextMatch: 0.8,
  });

  // 4. Decision engine
  const decision = decide({
    confidence,
    ambiguity: combinedAmbiguity,
    intent: analysis.intent,
  });

  // 5. Memory update
  saveMemory(input?.sessionId || "default", {
    text: stt.text,
    analysis,
    confidence,
  });

  // 6. Translation always attempts; use safe fallback on error
  let translated = stt.text;
  try {
    translated = await translate(stt.text, input?.targetLanguage || 'es');
  } catch (e) {
    // keep original text if translation fails; log later
  }

  return {
    text: stt.text,
    translated,
    targetLanguage: input?.targetLanguage || 'es',
    analysis: { ...analysis, local_ambiguity: localAmb },
    confidence,
    decision,
  };
}

module.exports = { processPipeline };
