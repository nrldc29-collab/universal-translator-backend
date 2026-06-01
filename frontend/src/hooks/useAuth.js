import { useState } from 'react';
import { authHeaders } from '../utils';

const TOKEN_STORAGE_KEY = 'translator_token';

export function useAuth({ apiUrl, onStatus }) {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) || '');
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo');

  async function login() {
    const response = await fetch(`${apiUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      onStatus?.('Login failed');
      return;
    }
    const data = await response.json();
    localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
    setAuthToken(data.access_token);
    onStatus?.(`Logged in as ${username}`);
  }

  function logout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuthToken('');
    onStatus?.('Logged out');
  }

  async function ensureAuthToken() {
    return authToken || '';
  }

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
