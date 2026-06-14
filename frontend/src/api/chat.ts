import axios from 'axios';
import { getStoredToken } from './auth';
import type { RagSource } from './legalQa';

export type ChatSession = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  sources: RagSource[];
  created_at: string;
};

export type ChatTurn = {
  session: ChatSession;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  is_ready: boolean;
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

function authHeaders() {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : undefined;
}

export async function createChatSession(title?: string): Promise<ChatSession | null> {
  try {
    const response = await api.post<ChatSession>('/chat/sessions', { title: title || null }, { headers: authHeaders() });
    return response.data;
  } catch {
    return null;
  }
}

export async function fetchChatSessions(): Promise<ChatSession[]> {
  try {
    const response = await api.get<ChatSession[]>('/chat/sessions', { headers: authHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function fetchChatMessages(sessionId: number): Promise<ChatMessage[]> {
  try {
    const response = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, { headers: authHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function sendChatMessage(sessionId: number, content: string, domainCode?: string): Promise<ChatTurn | null> {
  try {
    const response = await api.post<ChatTurn>(
      `/chat/sessions/${sessionId}/messages`,
      { content, domain_code: domainCode || null },
      { headers: authHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function deleteChatSession(sessionId: number): Promise<boolean> {
  try {
    await api.delete(`/chat/sessions/${sessionId}`, { headers: authHeaders() });
    return true;
  } catch {
    return false;
  }
}
