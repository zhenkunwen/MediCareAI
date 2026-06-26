/** Conversation persistence API — 3-year medical record retention */

import { API_BASE, authHeaders, jsonHeaders } from './client';

export interface ConversationItem {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: string;
}

export async function listConversations(): Promise<ConversationItem[]> {
  const res = await fetch(`${API_BASE}/patient/conversations`, { headers: authHeaders() });
  if (!res.ok) return [];
  const data = await res.json();
  return data.items || [];
}

export async function getConversationMessages(id: string): Promise<StoredMessage[]> {
  const res = await fetch(`${API_BASE}/patient/conversations/${id}/messages`, { headers: authHeaders() });
  if (!res.ok) return [];
  return res.json();
}

export async function saveConversation(
  conversationId: string,
  title: string,
  messages: StoredMessage[],
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/patient/conversations/save`, {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ conversation_id: conversationId, title, messages }),
    });
    if (!res.ok) console.warn('[saveConversation]', res.status, await res.text().catch(() => ''));
  } catch (e) {
    console.warn('[saveConversation] failed:', e);
  }
}
