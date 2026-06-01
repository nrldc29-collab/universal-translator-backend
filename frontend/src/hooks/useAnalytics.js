import { useState } from 'react';
import { authHeaders } from '../utils';

export function useAnalytics({ apiUrl, authToken, onStatus }) {
  const [analytics, setAnalytics] = useState(null);

  async function loadAnalytics() {
    if (!authToken) {
      onStatus?.('Log in to view analytics');
      return;
    }
    const response = await fetch(`${apiUrl}/analytics`, { headers: authHeaders(authToken) });
    if (!response.ok) {
      onStatus?.('Analytics unavailable');
      return;
    }
    setAnalytics(await response.json());
    onStatus?.('Analytics refreshed');
  }

  return { analytics, setAnalytics, loadAnalytics };
}
