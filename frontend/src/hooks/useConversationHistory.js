/**
 * useConversationHistory -- keep a rolling window of conversation turns
 * (source + translated text per speaker) and persist them to
 * localStorage so a refresh restores the recent dialogue.
 *
 * Returns `[conversationTurns, setConversationTurns]` with the same
 * shape as `useState`. The persisted window is capped at `limit`
 * entries (default 50).
 */

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'translator_conversation_turns';

export const CONVERSATION_DISPLAY_LIMIT = 6;

export default function useConversationHistory(limit = 50, { normalizeConversationTurn } = {}) {
  const [conversationTurns, setConversationTurns] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.slice(-limit) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversationTurns.slice(-limit)));
    } catch {
      /* ignore quota errors */
    }
  }, [conversationTurns, limit]);

  function appendConversationTurn(turn) {
    const normalized = normalizeConversationTurn ? normalizeConversationTurn(turn) : turn;
    setConversationTurns((current) => {
      const nextKey = `${normalized.speaker}-${normalized.created_at}-${normalized.source_text}`;
      const withoutDuplicate = current.filter((item) => `${item.speaker}-${item.created_at}-${item.source_text}` !== nextKey);
      return [...withoutDuplicate, normalized].slice(-CONVERSATION_DISPLAY_LIMIT);
    });
  }

  return [conversationTurns, setConversationTurns, appendConversationTurn];
}
