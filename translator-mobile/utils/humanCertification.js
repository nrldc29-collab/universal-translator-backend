export function asCertBool(value) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (value == null) return false;
  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
}

/** @returns {"none"|"advisory"|"required"} */
export function humanCertStep(message) {
  const step = String(message?.human_certification_step || "").toLowerCase();
  if (step === "required" || step === "advisory") return step;
  if (asCertBool(message?.needs_native_certification)) return "required";
  if (asCertBool(message?.native_speaker_listen_recommended)) return "advisory";
  return "none";
}

export function certificationBanner(message, step = humanCertStep(message)) {
  const text = String(
    message?.certification_message
    || message?.confidence_message
    || message?.clarify_message
    || message?.message
    || "",
  ).trim();
  if (text) return text;
  if (step === "required") {
    return "Have a fluent native speaker listen before you rely on the spoken bridge.";
  }
  if (step === "advisory") {
    return "Native speaker listen — confirm accent and cultural tone sound natural.";
  }
  return "";
}

export function shouldBlockTtsForCert(step) {
  return step === "required";
}

export function resolveConfidenceWarning(payload = {}) {
  const needsConfirm = asCertBool(payload.needs_confirmation);
  const needsNativeCert = asCertBool(payload.needs_native_certification);
  const nativeListen = asCertBool(payload.native_speaker_listen_recommended);
  const lowConfidence = asCertBool(payload.low_confidence);
  const certStep = humanCertStep(payload);
  if (certStep !== "none") return "";
  if (!needsConfirm && !lowConfidence && !needsNativeCert && !nativeListen) return "";
  return String(
    payload.confidence_message
    || payload.certification_message
    || (needsConfirm
      ? "High-stakes bridge — verify with a human interpreter before acting on this."
      : lowConfidence
        ? "Moderate confidence — double-check important details."
        : ""),
  ).trim();
}

export function certTurnFlags(message) {
  const step = humanCertStep(message);
  return {
    certStep: step,
    nativeListen: step === "advisory" || step === "required",
    clarify: asCertBool(message?.clarify)
      || asCertBool(message?.needs_confirmation)
      || step === "required"
      || asCertBool(message?.low_confidence),
  };
}
