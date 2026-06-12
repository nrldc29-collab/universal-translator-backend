const fs = require("fs");
const path = require("path");

describe("App hook wiring", () => {
  const appSource = fs.readFileSync(path.join(__dirname, "../App.js"), "utf8");

  it("wires setIsPlayingTts from useMobileTts into useMobileRecording", () => {
    const ttsHookIndex = appSource.indexOf("} = useMobileTts(appStateRef);");
    const recordingHookIndex = appSource.indexOf("} = useMobileRecording({");
    expect(ttsHookIndex).toBeGreaterThan(-1);
    expect(recordingHookIndex).toBeGreaterThan(ttsHookIndex);
    expect(appSource.slice(0, ttsHookIndex)).toMatch(/setIsPlayingTts,/);
    const recordingBlock = appSource.slice(recordingHookIndex, recordingHookIndex + 600);
    expect(recordingBlock).toMatch(/setIsPlayingTts,/);
  });

  it("wires resumeAfterTtsRef from useMobileStreamState", () => {
    const streamHookIndex = appSource.indexOf("} = useMobileStreamState();");
    expect(streamHookIndex).toBeGreaterThan(-1);
    expect(appSource.slice(0, streamHookIndex)).toMatch(/resumeAfterTtsRef,/);
  });

  it("updates WS handlers via refs instead of rebinding every render", () => {
    expect(appSource).toMatch(/handleMessageRef/);
    expect(appSource).toMatch(/setStatusWithTypeRef/);
    expect(appSource).not.toMatch(/useEffect\(\(\) => \{\s*wsControlRef\.current\?\.updateHandlers\?\.\(handleMessage, setStatusWithType\)/);
  });

  it("does not reload on stale SecureStore build id alone", () => {
    expect(appSource).not.toMatch(/isRemoteBuildNewer\(MOBILE_BUILD_ID, seenBuild\)/);
    expect(appSource).toMatch(/Bundle in memory is already MOBILE_BUILD_ID/);
  });
});
