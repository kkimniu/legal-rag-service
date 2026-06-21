import axios from 'axios';
import { getAuthHeaders } from './auth';

export type RagSource = {
  id: string;
  title?: string | null;
  domain_name?: string | null;
  source_type?: string | null;
  text: string;
  score?: number | null;
  metadata: Record<string, string | number | boolean>;
};

export type ChatSession = {
  id: number;
  title: string;
  case_id?: number | null;
  domain_code?: string | null;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
};

export type ChatMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  answer_mode?: string | null;
  sources: RagSource[];
  evidence_status?: string | null;
  evidence_warnings?: string[];
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

export async function createChatSession(title?: string, domainCode?: string, caseId?: number | null): Promise<ChatSession | null> {
  try {
    const response = await api.post<ChatSession>(
      '/chat/sessions',
      { title: title || null, domain_code: domainCode || null, case_id: caseId || null },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function fetchChatSessions(): Promise<ChatSession[]> {
  try {
    const response = await api.get<ChatSession[]>('/chat/sessions', { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function fetchChatMessages(sessionId: number): Promise<ChatMessage[]> {
  try {
    const response = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`, { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function sendChatMessage(sessionId: number, content: string, answerMode = 'general'): Promise<ChatTurn | null> {
  try {
    const response = await api.post<ChatTurn>(
      `/chat/sessions/${sessionId}/messages`,
      { content, answer_mode: answerMode },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

const _BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type StreamChatEvent =
  | { type: 'user_message'; message: ChatMessage }
  | { type: 'token'; content: string }
  | { type: 'done'; session: ChatSession; user_message: ChatMessage; assistant_message: ChatMessage; is_ready: boolean };

export async function streamChatMessage(
  sessionId: number,
  content: string,
  answerMode: string,
  onToken: (token: string) => void,
): Promise<ChatTurn | null> {
  try {
    const headers = await getAuthHeaders();
    const response = await fetch(`${_BASE_URL}/chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, answer_mode: answerMode }),
    });
    if (!response.ok || !response.body) return null;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result: ChatTurn | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const event = JSON.parse(line.slice(6)) as StreamChatEvent;
          if (event.type === 'token') {
            onToken(event.content);
          } else if (event.type === 'done') {
            result = { session: event.session, user_message: event.user_message, assistant_message: event.assistant_message, is_ready: event.is_ready };
          }
        } catch { /* skip malformed SSE line */ }
      }
    }
    return result;
  } catch {
    return null;
  }
}

export async function deleteChatSession(sessionId: number): Promise<boolean> {
  try {
    await api.delete(`/chat/sessions/${sessionId}`, { headers: await getAuthHeaders() });
    return true;
  } catch {
    return false;
  }
}

export async function fetchChatSession(sessionId: number): Promise<ChatSession | null> {
  try {
    const response = await api.get<ChatSession>(`/chat/sessions/${sessionId}`, { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return null;
  }
}

export async function updateChatSessionPin(sessionId: number, isPinned: boolean): Promise<ChatSession | null> {
  try {
    const response = await api.patch<ChatSession>(
      `/chat/sessions/${sessionId}/pin`,
      { is_pinned: isPinned },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}
