import {
  CONSUMER_OPEN_AND_GO,
  getConsumerCloudApiUrl,
  getConsumerDemoCredentials,
  hasConsumerCloudBackend,
  isConsumerCloudUrl,
} from "../constants/consumerCloud";

describe("consumerCloud", () => {
  const originalCloud = process.env.EXPO_PUBLIC_CLOUD_API_URL;

  afterEach(() => {
    if (originalCloud === undefined) {
      delete process.env.EXPO_PUBLIC_CLOUD_API_URL;
    } else {
      process.env.EXPO_PUBLIC_CLOUD_API_URL = originalCloud;
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

  test("demo credentials default to demo", () => {
    delete process.env.EXPO_PUBLIC_CLOUD_DEMO_USER;
    delete process.env.EXPO_PUBLIC_CLOUD_DEMO_PASS;
    expect(getConsumerDemoCredentials()).toEqual({ username: "demo", password: "demo" });
  });
});
