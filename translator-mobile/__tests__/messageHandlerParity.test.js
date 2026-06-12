import {
  BACKEND_AUDIO_WS_TYPES,
  HANDLED_MOBILE_WS_TYPES,
  isHandledMobileWsType,
  resolvePipelineStageLabel,
} from "../utils/wsMessageTypes";

describe("mobile WebSocket handler parity", () => {
  test("handles every backend audio stream message type", () => {
    for (const type of BACKEND_AUDIO_WS_TYPES) {
      expect(isHandledMobileWsType(type)).toBe(true);
    }
  });

  test("mobile handled list matches backend audio types", () => {
    expect(HANDLED_MOBILE_WS_TYPES.sort()).toEqual([...BACKEND_AUDIO_WS_TYPES].sort());
  });

  test("pong is handled at transport layer", () => {
    expect(isHandledMobileWsType("pong")).toBe(true);
  });
});

describe("resolvePipelineStageLabel", () => {
  test("maps pipeline stages to user-facing labels", () => {
    expect(resolvePipelineStageLabel("queued")).toMatch(/queued/i);
    expect(resolvePipelineStageLabel("stt")).toMatch(/transcrib/i);
    expect(resolvePipelineStageLabel("translation")).toMatch(/understand/i);
    expect(resolvePipelineStageLabel("tts_skipped")).toMatch(/skipped/i);
    expect(resolvePipelineStageLabel("weak_audio")).toMatch(/mic/i);
  });
});
