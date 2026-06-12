import {
  humanCertStep,
  certificationBanner,
  shouldBlockTtsForCert,
  certTurnFlags,
  asCertBool,
  resolveConfidenceWarning,
} from "../utils/humanCertification";

describe("humanCertStep", () => {
  test("reads explicit human_certification_step", () => {
    expect(humanCertStep({ human_certification_step: "advisory" })).toBe("advisory");
    expect(humanCertStep({ human_certification_step: "required" })).toBe("required");
    expect(humanCertStep({ human_certification_step: "none" })).toBe("none");
  });

  test("falls back to legacy boolean flags", () => {
    expect(humanCertStep({ needs_native_certification: true })).toBe("required");
    expect(humanCertStep({ native_speaker_listen_recommended: true })).toBe("advisory");
  });

  test("required wins over advisory booleans", () => {
    expect(humanCertStep({
      needs_native_certification: true,
      native_speaker_listen_recommended: true,
    })).toBe("required");
  });
});

describe("certificationBanner", () => {
  test("prefers certification_message", () => {
    expect(certificationBanner({
      human_certification_step: "advisory",
      certification_message: "Listen for Haitian Creole tone.",
    })).toBe("Listen for Haitian Creole tone.");
  });

  test("uses defaults when message missing", () => {
    expect(certificationBanner({ human_certification_step: "required" }))
      .toMatch(/native speaker/i);
    expect(certificationBanner({ human_certification_step: "advisory" }))
      .toMatch(/accent/i);
  });
});

describe("shouldBlockTtsForCert", () => {
  test("blocks only required certification", () => {
    expect(shouldBlockTtsForCert("required")).toBe(true);
    expect(shouldBlockTtsForCert("advisory")).toBe(false);
    expect(shouldBlockTtsForCert("none")).toBe(false);
  });
});

describe("certTurnFlags", () => {
  test("marks native listen turns", () => {
    expect(certTurnFlags({ human_certification_step: "advisory" })).toEqual({
      certStep: "advisory",
      nativeListen: true,
      clarify: false,
    });
    expect(certTurnFlags({ human_certification_step: "required" })).toEqual({
      certStep: "required",
      nativeListen: true,
      clarify: true,
    });
  });
});

describe("resolveConfidenceWarning", () => {
  test("skips when native certification handles the warning", () => {
    expect(resolveConfidenceWarning({ human_certification_step: "required", needs_confirmation: true })).toBe("");
  });

  test("returns confirmation copy for high-stakes turns", () => {
    expect(resolveConfidenceWarning({ needs_confirmation: true })).toMatch(/human interpreter/i);
  });
});

describe("asCertBool", () => {
  test("normalizes common truthy values", () => {
    expect(asCertBool("true")).toBe(true);
    expect(asCertBool(1)).toBe(true);
    expect(asCertBool("off")).toBe(false);
    expect(asCertBool(null)).toBe(false);
  });
});
