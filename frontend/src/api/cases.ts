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

export type CaseStatus = 'active' | 'watching' | 'closed';

export type CaseNote = {
  id: number;
  case_id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
};

export type CaseInsight = {
  case_id: number;
  summary: string;
  issues: string[];
  next_actions: string[];
  cautions: string[];
  is_ready: boolean;
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

export async function updateCaseStatus(caseId: number, status: CaseStatus): Promise<LegalCase | null> {
  try {
    const response = await api.patch<LegalCase>(
      `/cases/${caseId}`,
      { status },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function generateCaseInsight(caseId: number): Promise<CaseInsight | null> {
  try {
    const response = await api.post<CaseInsight>(`/cases/${caseId}/insight`, null, {
      headers: await getAuthHeaders(),
    });
    return response.data;
  } catch {
    return null;
  }
}

export async function fetchCaseNotes(caseId: number): Promise<CaseNote[]> {
  try {
    const response = await api.get<CaseNote[]>(`/cases/${caseId}/notes`, { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function createCaseNote(caseId: number, title: string, content: string): Promise<CaseNote | null> {
  try {
    const response = await api.post<CaseNote>(
      `/cases/${caseId}/notes`,
      { title: title || null, content },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}
