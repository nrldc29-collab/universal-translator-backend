import {
  CONSUMER_OPEN_AND_GO,
  getConsumerCloudApiUrl,
  getConsumerDemoCredentials,
  hasConsumerCloudBackend,
  hasConsumerDemoCredentials,
  isConsumerCloudUrl,
  rememberDiscoveredConsumerCloudUrl,
} from "../constants/consumerCloud";

describe("consumerCloud", () => {
  const originalCloud = process.env.EXPO_PUBLIC_CLOUD_API_URL;
  const originalApi = process.env.EXPO_PUBLIC_API_URL;

  afterEach(() => {
    if (originalCloud === undefined) {
      delete process.env.EXPO_PUBLIC_CLOUD_API_URL;
    } else {
      process.env.EXPO_PUBLIC_CLOUD_API_URL = originalCloud;
    }
    if (originalApi === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalApi;
    }
  });

  test("CONSUMER_OPEN_AND_GO is enabled", () => {
    expect(CONSUMER_OPEN_AND_GO).toBe(true);
  });

  test("getConsumerCloudApiUrl reads env", () => {
    process.env.EXPO_PUBLIC_CLOUD_API_URL = "https://anai.example.up.railway.app";
    expect(getConsumerCloudApiUrl()).toBe("https://anai.example.up.railway.app");
    expect(hasConsumerCloudBackend()).toBe(true);
    expect(isConsumerCloudUrl("https://anai.example.up.railway.app")).toBe(true);
    expect(isConsumerCloudUrl("http://192.168.1.1:8000")).toBe(false);
  });

  test("getConsumerCloudApiUrl falls back to https EXPO_PUBLIC_API_URL", () => {
    delete process.env.EXPO_PUBLIC_CLOUD_API_URL;
    process.env.EXPO_PUBLIC_API_URL = "https://prod.example.up.railway.app";
    expect(getConsumerCloudApiUrl()).toBe("https://prod.example.up.railway.app");
    delete process.env.EXPO_PUBLIC_API_URL;
  });

  test("getConsumerCloudApiUrl ignores http LAN EXPO_PUBLIC_API_URL", () => {
    delete process.env.EXPO_PUBLIC_CLOUD_API_URL;
    process.env.EXPO_PUBLIC_API_URL = "http://192.168.1.50:8000";
    expect(getConsumerCloudApiUrl()).toBe("");
    delete process.env.EXPO_PUBLIC_API_URL;
  });

  test("demo credentials default username only; password stays empty without env", () => {
    delete process.env.EXPO_PUBLIC_CLOUD_DEMO_USER;
    delete process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS;
    expect(getConsumerDemoCredentials()).toEqual({ username: "demo", password: "" });
    expect(hasConsumerDemoCredentials()).toBe(false);
  });

  test("hasConsumerDemoCredentials when password is set", () => {
    process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS = "secret";
    expect(hasConsumerDemoCredentials()).toBe(true);
    delete process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS;
  });

  test("rememberDiscoveredConsumerCloudUrl fills gap when env unset", () => {
    delete process.env.EXPO_PUBLIC_CLOUD_API_URL;
    rememberDiscoveredConsumerCloudUrl("https://discovered.up.railway.app");
    expect(getConsumerCloudApiUrl()).toBe("https://discovered.up.railway.app");
  });
});
