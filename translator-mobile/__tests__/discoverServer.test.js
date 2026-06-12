import {
  deriveApiUrlFromExpo,
  deriveBackendPortFromEnv,
  deriveExpoUrlFromInfo,
  deriveLanBackendUrl,
  deriveLanHostFromExpo,
  deriveMetroProbeUrls,
  fetchMobileConnectInfo,
  isOffLanBackendHost,
  probeMetroBundleReady,
  probeMetroBundleSignature,
  resolveServerUrl,
  tunnelFetchHeaders,
  waitForBackendReady,
} from '../utils/discoverServer';

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    expoGoConfig: { debuggerHost: '192.168.12.243:8082' },
    expoConfig: {},
    linkingUri: '',
    manifest2: {},
  },
}));

describe('discoverServer', () => {
  const originalEnv = process.env.EXPO_PUBLIC_API_URL;

  afterEach(() => {
    process.env.EXPO_PUBLIC_API_URL = originalEnv;
  });

  test('derives LAN host from Expo debuggerHost', () => {
    expect(deriveLanHostFromExpo()).toBe('192.168.12.243');
  });

  test('prefers env API URL when set', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:8000';
    expect(deriveApiUrlFromExpo()).toBe('http://192.168.12.243:8000');
  });

  test('prefers Expo session host when env URL points at a different LAN IP', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.100:8000';
    expect(deriveApiUrlFromExpo()).toBe('http://192.168.12.243:8000');
  });

  test('falls back to LAN host port 8000 when env is empty', () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(deriveApiUrlFromExpo()).toBe('http://192.168.12.243:8000');
  });

  test('deriveBackendPortFromEnv reads port from EXPO_PUBLIC_API_URL', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:9000';
    expect(deriveBackendPortFromEnv()).toBe('9000');
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(deriveBackendPortFromEnv()).toBe('8000');
  });

  test('deriveLanBackendUrl skips off-LAN Expo hosts', () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    delete process.env.EXPO_PUBLIC_TUNNEL_API_URL;
    expect(deriveLanBackendUrl('abc.trycloudflare.com')).toBe('');
    expect(deriveLanBackendUrl('192.168.12.243')).toBe('http://192.168.12.243:8000');
  });

  test('waitForBackendReady returns true when health reports ready', async () => {
    global.fetch = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ready: true, status: 'ok' }),
    }));
    await expect(waitForBackendReady('http://192.168.12.243:8000', { maxAttempts: 1 })).resolves.toBe(true);
  });

  test('waitForBackendReady aborts when shouldAbort returns true', async () => {
    global.fetch = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ready: false, status: 'warming' }),
    }));
    await expect(waitForBackendReady('http://192.168.12.243:8000', {
      maxAttempts: 4,
      delayMs: 100,
      shouldAbort: () => true,
    })).resolves.toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();

    let calls = 0;
    global.fetch = jest.fn(async () => {
      calls += 1;
      return {
        ok: true,
        json: async () => ({ ready: false, status: 'warming' }),
      };
    });
    await expect(waitForBackendReady('http://192.168.12.243:8000', {
      maxAttempts: 6,
      delayMs: 50,
      shouldAbort: () => calls >= 2,
    })).resolves.toBe(false);
    expect(calls).toBe(2);
  });

  test('waitForBackendReady waits until ready is true', async () => {
    let calls = 0;
    global.fetch = jest.fn(async () => {
      calls += 1;
      return {
        ok: true,
        json: async () => ({ ready: calls >= 2, status: 'ok' }),
      };
    });
    await expect(waitForBackendReady('http://192.168.12.243:8000', {
      maxAttempts: 3,
      delayMs: 10,
    })).resolves.toBe(true);
    expect(calls).toBeGreaterThanOrEqual(2);
  });

  test('tunnelFetchHeaders adds bypass headers for loca.lt and ngrok hosts', () => {
    expect(tunnelFetchHeaders('https://anai.example.loca.lt')).toMatchObject({
      'Bypass-Tunnel-Reminder': 'true',
    });
    expect(tunnelFetchHeaders('https://abc.ngrok-free.app')).toMatchObject({
      'ngrok-skip-browser-warning': 'true',
    });
    expect(tunnelFetchHeaders('http://192.168.12.243:8000')).toEqual({
      Accept: 'application/json',
    });
  });

  test('isOffLanBackendHost detects tunnel and public hosts', () => {
    expect(isOffLanBackendHost('abc.trycloudflare.com')).toBe(true);
    expect(isOffLanBackendHost('192.168.12.243')).toBe(false);
    expect(isOffLanBackendHost('localhost')).toBe(false);
  });

  test('preserves off-LAN tunnel URL over Expo session LAN host', () => {
    process.env.EXPO_PUBLIC_API_URL = 'https://anai.example.trycloudflare.com';
    expect(deriveApiUrlFromExpo()).toBe('https://anai.example.trycloudflare.com');
  });

  test('preserves HTTP tunnel URL over Expo session LAN host', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://anai-translator.example.loca.lt';
    expect(deriveApiUrlFromExpo()).toBe('http://anai-translator.example.loca.lt');
  });

  test('builds metro probe URLs for common ports', () => {
    expect(deriveMetroProbeUrls('192.168.12.243')).toEqual([
      'http://192.168.12.243:8082',
      'http://192.168.12.243:8081',
      'http://192.168.12.243:19000',
    ]);
  });

  test('prefers configured expo port when probing Metro', () => {
    expect(deriveMetroProbeUrls('192.168.12.243', 8081)).toEqual([
      'http://192.168.12.243:8081',
      'http://192.168.12.243:8082',
      'http://192.168.12.243:19000',
    ]);
  });

  test('derives Expo URL from mobile info', () => {
    expect(deriveExpoUrlFromInfo('192.168.12.243', { expo_port: 8082 })).toBe(
      'exp://192.168.12.243:8082',
    );
    expect(deriveExpoUrlFromInfo('', { expo_url: 'exp://10.0.0.5:8082' })).toBe(
      'exp://10.0.0.5:8082',
    );
  });

  test('skips dead tunnel URL from env', async () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:8000';
    process.env.EXPO_PUBLIC_TUNNEL_API_URL = 'https://dead-tunnel.example.loca.lt';
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('dead-tunnel')) {
        throw new Error('network error');
      }
      if (href.includes('/mobile/info')) {
        return {
          ok: true,
          json: async () => ({ backend_url: 'http://192.168.12.243:8000' }),
        };
      }
      if (href.includes('/health')) {
        return { ok: true };
      }
      throw new Error(`unexpected fetch ${href}`);
    });

    const resolved = await resolveServerUrl('http://192.168.12.243:8000');
    expect(resolved.apiUrl).toBe('http://192.168.12.243:8000');
    expect(resolved.healthy).toBe(true);
    delete process.env.EXPO_PUBLIC_TUNNEL_API_URL;
  });

  test('resolveServerUrl prefers off-LAN tunnel when preferOffLan is set', async () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:8000';
    process.env.EXPO_PUBLIC_TUNNEL_API_URL = 'https://live-tunnel.example.trycloudflare.com';
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('live-tunnel')) {
        return {
          ok: true,
          json: async () => ({
            backend_url: 'https://live-tunnel.example.trycloudflare.com',
            tunnel_backend_url: 'https://live-tunnel.example.trycloudflare.com',
          }),
        };
      }
      if (href.includes('/mobile/info')) {
        return {
          ok: true,
          json: async () => ({ backend_url: 'http://192.168.12.243:8000' }),
        };
      }
      if (href.includes('/health')) {
        return { ok: true };
      }
      throw new Error(`unexpected fetch ${href}`);
    });

    const resolved = await resolveServerUrl('http://192.168.12.243:8000', { preferOffLan: true });
    expect(resolved.apiUrl).toBe('https://live-tunnel.example.trycloudflare.com');
    expect(resolved.healthy).toBe(true);
    delete process.env.EXPO_PUBLIC_TUNNEL_API_URL;
  });

  test('fetchMobileConnectInfo falls back to tunnel env when LAN /mobile/info fails', async () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:8000';
    process.env.EXPO_PUBLIC_TUNNEL_API_URL = 'https://live-tunnel.example.trycloudflare.com';
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('192.168.12.243') && href.includes('/mobile/info')) {
        throw new Error('network error');
      }
      if (href.includes('live-tunnel') && href.includes('/mobile/info')) {
        return {
          ok: true,
          json: async () => ({
            backend_url: 'https://live-tunnel.example.trycloudflare.com',
            tunnel_backend_url: 'https://live-tunnel.example.trycloudflare.com',
          }),
        };
      }
      throw new Error(`unexpected fetch ${href}`);
    });

    const info = await fetchMobileConnectInfo('http://192.168.12.243:8000');
    expect(info?.tunnel_backend_url).toBe('https://live-tunnel.example.trycloudflare.com');
    delete process.env.EXPO_PUBLIC_TUNNEL_API_URL;
  });

  test('resolveServerUrl picks the first healthy backend candidate', async () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://192.168.12.243:8000';
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/mobile/info')) {
        return {
          ok: true,
          json: async () => ({ backend_url: 'http://192.168.12.243:8000', build_id: '2026-06-09-fix44' }),
        };
      }
      if (href.includes('/health')) {
        return { ok: true };
      }
      throw new Error(`unexpected fetch ${href}`);
    });

    const resolved = await resolveServerUrl('http://192.168.12.243:8000');
    expect(resolved.apiUrl).toBe('http://192.168.12.243:8000');
    expect(resolved.healthy).toBe(true);
    expect(resolved.hostname).toBe('192.168.12.243');
  });

  test('probeMetroBundleReady returns true when Metro reports bundle ready', async () => {
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/.anai/bundle-ready')) {
        return { ok: true, text: async () => '1:9095390' };
      }
      throw new Error(`unexpected fetch ${href}`);
    });
    await expect(probeMetroBundleReady('192.168.12.243', '8082')).resolves.toBe(true);
  });

  test('probeMetroBundleReady reports progress while polling', async () => {
    const progress = [];
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/.anai/bundle-ready')) {
        if (progress.length === 0) {
          return { ok: true, text: async () => '0' };
        }
        return { ok: true, text: async () => '1:9095390' };
      }
      throw new Error(`unexpected fetch ${href}`);
    });
    await expect(
      probeMetroBundleReady('192.168.12.243', '8082', {
        maxAttempts: 2,
        delayMs: 0,
        onProgress: (state) => progress.push(state),
      }),
    ).resolves.toBe(true);
    expect(progress.some((entry) => entry.ready === true && entry.bytes === 9095390)).toBe(true);
  });

  test('probeMetroBundleSignature returns true when Metro reports full bundle bytes', async () => {
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/.anai/bundle-ready')) {
        return { ok: true, text: async () => '1:9344289' };
      }
      throw new Error(`unexpected fetch ${href}`);
    });
    await expect(probeMetroBundleSignature('192.168.12.243', '8082')).resolves.toBe(true);
  });

  test('probeMetroBundleSignature rejects stub bundle-ready responses', async () => {
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/.anai/bundle-ready')) {
        return { ok: true, text: async () => '1:1200' };
      }
      throw new Error(`unexpected fetch ${href}`);
    });
    await expect(
      probeMetroBundleSignature('192.168.12.243', '8082', { maxAttempts: 1 }),
    ).resolves.toBe(false);
  });

  test('probeMetroBundleReady returns false when Metro is not ready', async () => {
    global.fetch = jest.fn(async (input) => {
      const href = typeof input === 'string' ? input : input?.url || String(input);
      if (href.includes('/.anai/bundle-ready')) {
        return { ok: true, text: async () => '0' };
      }
      throw new Error(`unexpected fetch ${href}`);
    });
    await expect(
      probeMetroBundleReady('192.168.12.243', '8082', { maxAttempts: 1 }),
    ).resolves.toBe(false);
  });

  test('resolveServerUrl aborts when shouldAbort returns true', async () => {
    global.fetch = jest.fn(async () => ({
      ok: true,
      json: async () => ({ ready: true }),
    }));
    const resolved = await resolveServerUrl('http://192.168.12.243:8000', {
      shouldAbort: () => true,
    });
    expect(resolved.healthy).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
