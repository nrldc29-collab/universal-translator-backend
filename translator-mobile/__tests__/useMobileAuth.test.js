import { renderHook, act } from '@testing-library/react-native';
import * as SecureStore from 'expo-secure-store';
import { useMobileAuth } from '../hooks/useMobileAuth';

describe('useMobileAuth', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    SecureStore.getItemAsync.mockImplementation(async (key) => {
      if (key === 'translator_ws_url') return 'http://192.168.1.50:8000';
      if (key === 'translator_setup_complete') return '1';
      return null;
    });
  });

  test('prefers env URL over stale stored URL when LAN IP changes', async () => {
    const onStatus = jest.fn();
    const { result } = renderHook(() =>
      useMobileAuth({
        defaultUrl: 'http://192.168.12.243:8000',
        onStatus,
      }),
    );

    await act(async () => {
      await result.current.loadStoredData();
    });

    expect(result.current.wsUrl).toBe('http://192.168.12.243:8000');
    expect(result.current.setupComplete).toBe(false);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'translator_ws_url',
      'http://192.168.12.243:8000',
    );
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('translator_setup_complete');
  });

  test('rejects localhost health checks for phone use', async () => {
    global.fetch = jest.fn();
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));

    await act(async () => {
      result.current.setWsUrl('http://localhost:8000');
    });

    let ok = false;
    await act(async () => {
      ok = await result.current.checkBackendHealth('http://localhost:8000');
    });

    expect(ok).toBe(false);
    expect(result.current.backendReachable).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('login normalizes trailing slashes in server URL', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'test-token' }),
      });

    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));

    await act(async () => {
      result.current.setWsUrl('http://192.168.12.243:8000/');
    });

    await act(async () => {
      await result.current.login();
    });

    expect(global.fetch).toHaveBeenLastCalledWith(
      'http://192.168.12.243:8000/auth/login',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.current.token).toBe('test-token');
  });

  test('quiet health check updates reachability without status messages', async () => {
    const onStatus = jest.fn();
    global.fetch = jest.fn(async () => ({ ok: true, status: 200 }));
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '', onStatus }));

    await act(async () => {
      await result.current.checkBackendHealth('http://192.168.12.243:8000', { quiet: true });
    });

    expect(result.current.backendReachable).toBe(true);
    expect(result.current.isCheckingBackend).toBe(false);
    expect(onStatus).not.toHaveBeenCalled();
  });

  test('checkBackendHealth reports success when server responds OK', async () => {
    const onStatus = jest.fn();
    global.fetch = jest.fn(async () => ({ ok: true, status: 200 }));
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '', onStatus }));

    let ok = false;
    await act(async () => {
      ok = await result.current.checkBackendHealth('http://192.168.12.243:8000');
    });

    expect(ok).toBe(true);
    expect(result.current.backendReachable).toBe(true);
    expect(onStatus).toHaveBeenCalledWith('Server reachable', 'success');
  });

  test('editWsUrl clears stale backend reachability when URL changes', async () => {
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));

    await act(async () => {
      result.current.setWsUrl('http://192.168.12.243:8000');
    });

    await act(async () => {
      global.fetch = jest.fn(async () => ({ ok: true }));
      await result.current.checkBackendHealth('http://192.168.12.243:8000');
    });

    expect(result.current.backendReachable).toBe(true);

    act(() => {
      result.current.editWsUrl('http://192.168.1.99:8000');
    });

    expect(result.current.wsUrl).toBe('http://192.168.1.99:8000');
    expect(result.current.backendReachable).toBe(null);
  });

  test('saveRecentUrl reads from SecureStore instead of stale React state', async () => {
    SecureStore.getItemAsync.mockImplementation(async (key) => {
      if (key === 'recent_urls') return JSON.stringify(['http://192.168.1.10:8000']);
      return null;
    });

    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));

    await act(async () => {
      await result.current.saveRecentUrl('http://192.168.12.243:8000');
    });

    expect(result.current.recentUrls).toEqual([
      'http://192.168.12.243:8000',
      'http://192.168.1.10:8000',
    ]);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
      'recent_urls',
      JSON.stringify(['http://192.168.12.243:8000', 'http://192.168.1.10:8000']),
    );
  });

  test('recovers from corrupt recent_urls JSON without blocking setup', async () => {
    SecureStore.getItemAsync.mockImplementation(async (key) => {
      if (key === 'translator_ws_url') return 'http://192.168.12.243:8000';
      if (key === 'translator_setup_complete') return '1';
      if (key === 'recent_urls') return '{not-json';
      return null;
    });

    const { result } = renderHook(() =>
      useMobileAuth({ defaultUrl: 'http://192.168.12.243:8000' }),
    );

    await act(async () => {
      await result.current.loadStoredData();
    });

    expect(result.current.recentUrls).toEqual([]);
    expect(result.current.setupComplete).toBe(true);
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('recent_urls');
  });

  test('validateUrl rejects scheme-only URLs', () => {
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));
    expect(result.current.validateUrl('http://')).toBe(false);
    expect(result.current.validateUrl('https://')).toBe(false);
    expect(result.current.validateUrl('http://192.168.12.243:8000')).toBe(true);
  });

  test('login onSuccess receives access token before React state updates', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'fresh-token' }),
      });

    const onSuccess = jest.fn();
    const { result } = renderHook(() => useMobileAuth({ defaultUrl: '' }));

    await act(async () => {
      result.current.setWsUrl('http://192.168.12.243:8000');
    });

    await act(async () => {
      await result.current.login({ onSuccess });
    });

    expect(onSuccess).toHaveBeenCalledWith('fresh-token');
  });

  test('keeps stored URL when it matches env URL', async () => {
    SecureStore.getItemAsync.mockImplementation(async (key) => {
      if (key === 'translator_ws_url') return 'http://192.168.12.243:8000';
      if (key === 'translator_setup_complete') return '1';
      return null;
    });

    const { result } = renderHook(() =>
      useMobileAuth({ defaultUrl: 'http://192.168.12.243:8000' }),
    );

    await act(async () => {
      await result.current.loadStoredData();
    });

    expect(result.current.wsUrl).toBe('http://192.168.12.243:8000');
    expect(result.current.setupComplete).toBe(true);
    expect(SecureStore.deleteItemAsync).not.toHaveBeenCalledWith('translator_setup_complete');
  });
});
