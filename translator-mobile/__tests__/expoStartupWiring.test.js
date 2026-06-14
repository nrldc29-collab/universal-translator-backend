const fs = require("fs");
const path = require("path");

describe("Expo startup wiring", () => {
  const indexSource = fs.readFileSync(path.join(__dirname, "../index.js"), "utf8");
  const runtimeSource = fs.readFileSync(path.join(__dirname, "../configure-runtime.js"), "utf8");

  it("loads configure-runtime before App so console filters apply early", () => {
    const runtimeImport = indexSource.indexOf('import "./configure-runtime"');
    const appImport = indexSource.indexOf('import App from "./App"');
    expect(runtimeImport).toBeGreaterThan(-1);
    expect(appImport).toBeGreaterThan(runtimeImport);
    expect(indexSource).not.toMatch(/configureMobileRuntime\(\)/);
  });

  it("configure-runtime invokes configureMobileRuntime", () => {
    expect(runtimeSource).toMatch(/configureMobileRuntime\(\)/);
  });

  it("cloud bootstrap skips LAN discovery when cloud URL is configured", () => {
    expect(indexSource).toMatch(/setGate\(\{ phase: "ready", apiUrl: cloudUrl \}\)/);
  });
});
