import { useEffect, useRef, useState } from 'react';

const TOKEN_STORAGE_KEY = 'translator_token';

export function useAuth({ apiUrl, onStatus }) {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) || '');
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');
  const loginPromiseRef = useRef(null);

  async function login() {
    const response = await fetch(`${apiUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      onStatus?.('Login failed');
      return '';
    }
    const data = await response.json();
    const token = data.access_token || '';
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
      setAuthToken(token);
      onStatus?.(`Logged in as ${username}`);
    }
    return token;
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuthToken('');
    onStatus?.('Logged out');
  }

  function clearAuthToken() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuthToken('');
  }

  async function ensureAuthToken({ force = false } = {}) {
    if (authToken && !force) return authToken;
    if (force) clearAuthToken();
    if (!username.trim() || !password.trim()) return '';
    if (!loginPromiseRef.current) {
      loginPromiseRef.current = login()
        .catch(() => '')
        .finally(() => {
          loginPromiseRef.current = null;
        });
    }
    return loginPromiseRef.current;
  }

  useEffect(() => {
    if (authToken || !username.trim() || !password.trim()) return;
    ensureAuthToken().catch(() => {});
  }, [apiUrl]);

  return {
    authToken,
    setAuthToken,
    username,
    setUsername,
    password,
    setPassword,
    login,
    logout,
    ensureAuthToken,
  };
}
