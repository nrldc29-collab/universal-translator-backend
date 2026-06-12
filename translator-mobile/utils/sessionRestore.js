import { certTurnFlags } from "./humanCertification";

function asBool(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (value == null) return false;
  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
}

export function mapSessionHistoryToTurns(history = [], limit = 3) {
  if (!Array.isArray(history) || history.length === 0) return [];
  return history
    .map((turn, index) => {
      const sourceText = turn.source_text || turn.original_text || "";
      const translatedText = turn.translated_text || turn.text || "";
      if (!sourceText && !translatedText) return null;
      const speakerIndex = Number(turn.speaker_index || turn.speaker || 1);
      const flags = certTurnFlags(turn);
      return {
        id: turn.id || `restore-${index}-${speakerIndex}`,
        speakerLabel: turn.speaker_label || `Person ${speakerIndex}`,
        listenerLabel: turn.listener_label || (speakerIndex === 2 ? "Person 1" : "Person 2"),
        sourceText,
        translatedText,
        sourceLanguage: turn.source_language || "",
        targetLanguage: turn.target_language || "",
        routeConfidence: Number(turn.route_confidence ?? 1),
        clarify: flags.clarify || asBool(turn.needs_confirmation),
        certStep: flags.certStep,
        nativeListen: flags.nativeListen,
      };
    })
    .filter(Boolean)
    .slice(-limit);
}

export function latestSessionTurn(session) {
  const history = session?.turns
    || session?.history
    || session?.shared?.history
    || [];
  if (!history.length) return null;
  return history[history.length - 1];
}
