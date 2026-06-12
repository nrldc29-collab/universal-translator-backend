import * as SecureStore from 'expo-secure-store';
import { shouldAutoReloadForMetro } from '../utils/metroBuildReload';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
}));

describe('shouldAutoReloadForMetro', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('allows one reload when Metro is newer', async () => {
    SecureStore.getItemAsync.mockResolvedValue(null);
    await expect(shouldAutoReloadForMetro('2026-06-09-fix62', '2026-06-09-fix61')).resolves.toBe(true);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith('anai_metro_reload_2026-06-09-fix62', '1');
  });

  test('blocks repeat reload for the same Metro build', async () => {
    SecureStore.getItemAsync.mockResolvedValue('1');
    await expect(shouldAutoReloadForMetro('2026-06-09-fix62', '2026-06-09-fix61')).resolves.toBe(false);
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  });

  test('does not reload when phone bundle is newer than Metro', async () => {
    await expect(shouldAutoReloadForMetro('2026-06-09-fix61', '2026-06-09-fix62')).resolves.toBe(false);
    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
  });
});
