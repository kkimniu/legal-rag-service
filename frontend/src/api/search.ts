import axios from 'axios';
import { getAuthHeaders } from './auth';


export type PersonalSearchResult = {
  result_type: 'case' | 'note' | 'task' | 'attachment' | 'chat';
  id: number;
  case_id?: number | null;
  session_id?: number | null;
  title: string;
  snippet: string;
  occurred_at: string;
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export async function searchPersonalWorkspace(query: string): Promise<PersonalSearchResult[]> {
  const normalized = query.trim();
  if (normalized.length < 2) return [];
  try {
    const response = await api.get<{ query: string; results: PersonalSearchResult[] }>('/search', {
      headers: await getAuthHeaders(),
      params: { q: normalized },
    });
    return response.data.results;
  } catch {
    return [];
  }
}
