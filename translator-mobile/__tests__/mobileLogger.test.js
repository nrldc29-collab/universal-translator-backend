import { isMobileVerbose, mobileDebug, mobileError, mobileWarn } from "../utils/mobileLogger";

describe("mobileLogger", () => {
  const original = process.env.EXPO_PUBLIC_DEBUG_LOGS;

  afterEach(() => {
    if (original === undefined) {
      delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    } else {
      process.env.EXPO_PUBLIC_DEBUG_LOGS = original;
    }
    jest.restoreAllMocks();
  });

  test("isMobileVerbose is false by default", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    expect(isMobileVerbose()).toBe(false);
  });

  test("expected errors stay quiet unless verbose", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
    mobileError("WebSocket error:", new Error("offline"), { expected: true });
    expect(errorSpy).not.toHaveBeenCalled();
    expect(debugSpy).not.toHaveBeenCalled();
  });

  test("expected errors log in verbose mode", () => {
    process.env.EXPO_PUBLIC_DEBUG_LOGS = "1";
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
    mobileError("WebSocket error:", new Error("offline"), { expected: true });
    expect(debugSpy).toHaveBeenCalled();
  });

  test("unexpected errors always log", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mobileError("Anai startup error:", new Error("boom"));
    expect(errorSpy).toHaveBeenCalled();
  });

  test("mobileDebug and mobileWarn honor verbose flag", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    const debugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    mobileDebug("trace");
    mobileWarn("heads up");
    expect(debugSpy).not.toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
    process.env.EXPO_PUBLIC_DEBUG_LOGS = "1";
    mobileDebug("trace");
    mobileWarn("heads up");
    expect(debugSpy).toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  test("configureMobileRuntime does not throw", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    global.__anaiQuietConsole = false;
    const { configureMobileRuntime } = require("../utils/mobileLogger");
    expect(() => configureMobileRuntime()).not.toThrow();
  });

  test("configureMobileRuntime filters known transient console.error", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    global.__anaiQuietConsole = false;
    const { configureMobileRuntime } = require("../utils/mobileLogger");
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    configureMobileRuntime();
    console.error("WebSocket error:", new Error("offline"));
    expect(errorSpy).not.toHaveBeenCalled();
    console.error("Fatal unexpected crash:", new Error("boom"));
    expect(errorSpy).toHaveBeenCalled();
  });

  test("configureMobileRuntime filters known third-party console.warn", () => {
    delete process.env.EXPO_PUBLIC_DEBUG_LOGS;
    global.__anaiQuietConsole = false;
    const { configureMobileRuntime } = require("../utils/mobileLogger");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    configureMobileRuntime();
    console.warn("SafeAreaView has been deprecated and will be removed in a future release.");
    expect(warnSpy).not.toHaveBeenCalled();
    console.warn("Unexpected custom warning");
    expect(warnSpy).toHaveBeenCalled();
  });
});
