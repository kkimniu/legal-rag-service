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

export type LegalSearchResult = {
  id: string;
  title?: string | null;
  domain_name?: string | null;
  evidence_type: string;
  snippet: string;
  score?: number | null;
};

export type SearchTypeFilter = 'all' | PersonalSearchResult['result_type'] | 'law';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export async function searchLegal(
  query: string,
  limit = 10,
): Promise<{ results: LegalSearchResult[]; totalCount: number }> {
  const normalized = query.trim();
  if (normalized.length < 2) return { results: [], totalCount: 0 };
  try {
    const response = await api.get<{ query: string; results: LegalSearchResult[]; total_count: number }>(
      '/search/legal',
      { headers: await getAuthHeaders(), params: { q: normalized, limit } },
    );
    return { results: response.data.results, totalCount: response.data.total_count };
  } catch {
    return { results: [], totalCount: 0 };
  }
}

export async function searchPersonalWorkspace(
  query: string,
  resultType?: SearchTypeFilter,
): Promise<{ results: PersonalSearchResult[]; totalCount: number }> {
  const normalized = query.trim();
  if (normalized.length < 2) return { results: [], totalCount: 0 };
  try {
    const params: Record<string, string | number> = { q: normalized, limit: 100 };
    if (resultType && resultType !== 'all') params.result_type = resultType;
    const response = await api.get<{
      query: string;
      results: PersonalSearchResult[];
      total_count: number;
    }>('/search', { headers: await getAuthHeaders(), params });
    return { results: response.data.results, totalCount: response.data.total_count };
  } catch {
    return { results: [], totalCount: 0 };
  }
}
