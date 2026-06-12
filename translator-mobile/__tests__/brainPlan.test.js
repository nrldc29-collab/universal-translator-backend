import {
  extractBrainPlan,
  compactRepairLabel,
  shouldSkipBrainTts,
  uniqueStrings,
} from "../utils/brainPlan";

describe("extractBrainPlan", () => {
  test("extracts cip_response_plan and hints", () => {
    const payload = {
      cip_response_plan: { strategy: "direct" },
      cip_client_hints: { skip_tts: true },
      cip_repair_options: [{ type: "repeat_terms", terms: ["Anaï"] }],
    };
    const result = extractBrainPlan(payload);
    expect(result.plan).toEqual({ strategy: "direct" });
    expect(result.hints).toEqual({ skip_tts: true });
    expect(result.repairOptions).toHaveLength(1);
  });
});

describe("compactRepairLabel", () => {
  test("labels language switch repairs", () => {
    expect(compactRepairLabel({ type: "switch_source_language", language: "ht" }))
      .toBe("Switch to HT");
  });
});

describe("shouldSkipBrainTts", () => {
  test("honors skip_tts hints and safety gates only", () => {
    expect(shouldSkipBrainTts({ cip_client_hints: { skip_tts: true } })).toBe(true);
    expect(shouldSkipBrainTts({ stage: "translation_safety" })).toBe(true);
    expect(shouldSkipBrainTts({ human_certification_step: "required" })).toBe(true);
    expect(shouldSkipBrainTts({ low_confidence: true })).toBe(false);
    expect(shouldSkipBrainTts({ clarify: true })).toBe(false);
    expect(shouldSkipBrainTts({})).toBe(false);
    expect(shouldSkipBrainTts(null, { skip_tts: true })).toBe(true);
    expect(shouldSkipBrainTts()).toBe(false);
  });
});

describe("uniqueStrings", () => {
  test("deduplicates trimmed strings", () => {
    expect(uniqueStrings(["a", "a", "", "b"])).toEqual(["a", "b"]);
  });
});
