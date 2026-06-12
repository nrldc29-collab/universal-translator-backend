import { humanCertStep, shouldBlockTtsForCert } from "./humanCertification";

export function extractBrainPlan(payload = {}) {
  const plan = payload.cip_response_plan || payload.response_plan || null;
  const hints = payload.cip_client_hints || payload.client_hints || plan?.client_hints || {};
  const repairOptions = payload.cip_repair_options || plan?.repair_options || [];
  return {
    plan: plan && typeof plan === "object" ? plan : null,
    hints: hints && typeof hints === "object" ? hints : {},
    repairOptions: Array.isArray(repairOptions) ? repairOptions : [],
  };
}

export function compactRepairLabel(option = {}) {
  if (option.type === "auto_switch_source_language") {
    return `Using ${String(option.language || "").toUpperCase()}`;
  }
  if (option.type === "switch_source_language") {
    return `Switch to ${String(option.language || "").toUpperCase()}`;
  }
  if (option.type === "repeat_terms") return "Repeat exact terms";
  if (option.type === "confirm_exact") return "Confirm exact words";
  if (option.type === "choose_meaning") return `Meaning of ${option.word}`;
  if (option.type === "repeat_slowly") return "Repeat slowly";
  if (option.type === "preserve_code_switch") return "Keep mixed language";
  return option.label || "Repair";
}

export function shouldSkipBrainTts(payload = null, storedHints = {}) {
  if (payload) {
    const hints = extractBrainPlan(payload).hints;
    if (Boolean(hints?.skip_tts || hints?.tts_mode === "skip")) return true;
    if (payload?.stage === "translation_safety") return true;
    if (shouldBlockTtsForCert(humanCertStep(payload))) return true;
    return false;
  }
  if (Boolean(storedHints?.skip_tts || storedHints?.tts_mode === "skip")) return true;
  return false;
}

export function uniqueStrings(values = []) {
  return [...new Set(values.filter((value) => typeof value === "string" && value.trim()))];
}
