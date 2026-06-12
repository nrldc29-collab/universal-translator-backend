import { mapSessionHistoryToTurns, latestSessionTurn } from "../utils/sessionRestore";

describe("mapSessionHistoryToTurns", () => {
  test("maps session history into turn chips", () => {
    const turns = mapSessionHistoryToTurns([
      {
        source_text: "Hello",
        translated_text: "Bonjour",
        speaker_label: "Person 1",
        human_certification_step: "advisory",
      },
      {
        source_text: "Thanks",
        translated_text: "Merci",
        needs_confirmation: true,
      },
    ]);
    expect(turns).toHaveLength(2);
    expect(turns[0].nativeListen).toBe(true);
    expect(turns[1].clarify).toBe(true);
  });
});

describe("latestSessionTurn", () => {
  test("returns last history item", () => {
    expect(latestSessionTurn({ history: [{ source_text: "a" }, { source_text: "b" }] })).toEqual({ source_text: "b" });
  });
});
