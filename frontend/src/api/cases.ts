import axios from 'axios';
import { getAuthHeaders } from './auth';

export type LegalCase = {
  id: number;
  title: string;
  summary: string;
  status: string;
  domain_code?: string | null;
  created_at: string;
  updated_at: string;
  note_count: number;
  chat_count: number;
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export async function fetchCases(): Promise<LegalCase[]> {
  try {
    const response = await api.get<LegalCase[]>('/cases', { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function createCase(title: string, domainCode?: string): Promise<LegalCase | null> {
  try {
    const response = await api.post<LegalCase>(
      '/cases',
      { title, domain_code: domainCode || null },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}
