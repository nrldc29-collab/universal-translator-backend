import {
  PRODUCT_TAGLINE,
  micHint,
  emptyStateCopy,
  routeCaptions,
  transcriptHeaderLabel,
  transcriptExchangeLabel,
  liveStatusLabel,
  connectionStripStatus,
  statusStripDetail,
  offlineConnectCopy,
  modeToggleToast,
  processingPillMessage,
  copyToasts,
  dockLabels,
  normalizeConnectionStatus,
  connectionLifecycleMessages,
  bridgeActionMessages,
  wsBridgeStatuses,
  loadingScreenMessage,
  reconnectFailureMessage,
  laneHeaderLabel,
  clearPanelCopy,
  turnRailHeader,
} from "../constants/productVoice";

describe("productVoice", () => {
  test("tagline reflects bridge + conversation", () => {
    expect(PRODUCT_TAGLINE.toLowerCase()).toMatch(/bridge/);
    expect(PRODUCT_TAGLINE.toLowerCase()).toMatch(/conversation/);
  });

  test("route captions change with two-way mode", () => {
    expect(routeCaptions(true).target).toBe("They hear");
    expect(routeCaptions(false).target).toBe("Bridged out");
  });

  test("transcript header uses conversation framing", () => {
    expect(transcriptHeaderLabel()).toMatch(/bridge conversation/i);
    expect(transcriptExchangeLabel(2)).toMatch(/2 bridge exchanges/);
  });

  test("mic hints mention bridge when live", () => {
    expect(micHint({ isInterpreterActive: true, twoWay: true })).toMatch(/bridge/i);
    expect(micHint({ needsServerLink: true })).toMatch(/link/i);
  });

  test("empty state copy is mission-led when offline", () => {
    const copy = emptyStateCopy({ isOffline: true });
    expect(copy.title.toLowerCase()).toMatch(/connect/);
    expect(copy.description.toLowerCase()).toMatch(/anai/);
  });

  test("live status uses bridge language", () => {
    expect(liveStatusLabel("speaking")).toMatch(/bridg/i);
    expect(liveStatusLabel("armed")).toMatch(/bridge/i);
  });

  test("connection strip reflects bridge states", () => {
    expect(connectionStripStatus({ isListening: true })).toMatch(/bridge live/i);
    expect(connectionStripStatus({ isSpeaking: true })).toMatch(/bridg/i);
  });

  test("status strip detail uses together framing", () => {
    const detail = statusStripDetail({ activeSource: "English", activeTarget: "French", twoWay: true, turnCount: 2 });
    expect(detail).toMatch(/Together/);
    expect(detail).toMatch(/2 bridge exchanges/);
  });

  test("offline connect copy names the bridge", () => {
    const copy = emptyStateCopy({ isOffline: true });
    expect(copy.title.toLowerCase()).toMatch(/connect/);
    expect(copy.description.toLowerCase()).toMatch(/anai/);
    expect(offlineConnectCopy().message.toLowerCase()).toMatch(/link bridge/);
  });

  test("mode toggle and dock use together framing", () => {
    expect(modeToggleToast(true)).toMatch(/together/i);
    expect(dockLabels({ isConnected: true, twoWay: true }).mode).toBe("Together");
    expect(dockLabels({ isConnected: true }).connect).toBe("Linked");
    expect(dockLabels({ isConnected: false }).connect).toMatch(/link bridge/i);
    expect(dockLabels({ isConnected: true }).replay.toLowerCase()).toMatch(/replay bridge/);
    expect(dockLabels({ isConnected: true }).clear.toLowerCase()).toMatch(/clear bridge/);
  });

  test("processing pill describes understanding not translating", () => {
    expect(processingPillMessage().toLowerCase()).toMatch(/understand/);
    expect(copyToasts().translationCopied.toLowerCase()).toMatch(/bridg/);
  });

  test("connection status normalizes to bridge language", () => {
    expect(normalizeConnectionStatus("Connected")).toMatch(/bridge linked/i);
    expect(normalizeConnectionStatus("Ready to listen")).toMatch(/bridge ready/i);
    expect(normalizeConnectionStatus("Translating")).toMatch(/understand/i);
    expect(normalizeConnectionStatus("Connection lost — reconnecting…")).toMatch(/reconnect/i);
    expect(loadingScreenMessage().toLowerCase()).toMatch(/bridge/);
    expect(reconnectFailureMessage().toLowerCase()).toMatch(/bridge dropped/);
    expect(connectionLifecycleMessages().linking.toLowerCase()).toMatch(/linking bridge/);
    expect(wsBridgeStatuses().disconnected.toLowerCase()).toMatch(/bridge dropped/);
    expect(bridgeActionMessages().routeSwapped.toLowerCase()).toMatch(/bridge/);
    expect(bridgeActionMessages().turnCancelled.toLowerCase()).toMatch(/bridge/);
    expect(bridgeActionMessages().waitingPlayback.toLowerCase()).toMatch(/bridged voice/);
  });

  test("lane headers and clear copy use bridge roles", () => {
    expect(laneHeaderLabel({ languageName: "English", side: "source" })).toMatch(/you speak/i);
    expect(laneHeaderLabel({ languageName: "French", side: "target", twoWay: true })).toMatch(/they hear/i);
    expect(clearPanelCopy().toast.toLowerCase()).toMatch(/bridge cleared/);
    expect(turnRailHeader().toLowerCase()).toMatch(/exchange/);
  });
});
