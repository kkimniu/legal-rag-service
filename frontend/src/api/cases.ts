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

export type CaseAttachment = {
  id: number;
  case_id: number;
  original_filename: string;
  content_type?: string | null;
  size_bytes: number;
  extraction_status: string;
  extracted_text_chars: number;
  vector_status: string;
  vector_chunk_count: number;
  created_at: string;
};

export type CaseTask = {
  id: number;
  case_id: number;
  title: string;
  due_date?: string | null;
  is_completed: boolean;
  created_at: string;
  updated_at: string;
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

export async function updateCaseNote(caseId: number, noteId: number, title: string, content: string): Promise<CaseNote | null> {
  try {
    const response = await api.patch<CaseNote>(
      `/cases/${caseId}/notes/${noteId}`,
      { title: title || null, content },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function deleteCaseNote(caseId: number, noteId: number): Promise<boolean> {
  try {
    await api.delete(`/cases/${caseId}/notes/${noteId}`, { headers: await getAuthHeaders() });
    return true;
  } catch {
    return false;
  }
}

export async function fetchCaseAttachments(caseId: number): Promise<CaseAttachment[]> {
  try {
    const response = await api.get<CaseAttachment[]>(`/cases/${caseId}/attachments`, { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function fetchCaseTasks(caseId: number): Promise<CaseTask[]> {
  try {
    const response = await api.get<CaseTask[]>(`/cases/${caseId}/tasks`, { headers: await getAuthHeaders() });
    return response.data;
  } catch {
    return [];
  }
}

export async function createCaseTask(caseId: number, title: string, dueDate?: string): Promise<CaseTask | null> {
  try {
    const response = await api.post<CaseTask>(
      `/cases/${caseId}/tasks`,
      { title, due_date: dueDate || null },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function updateCaseTask(caseId: number, task: CaseTask): Promise<CaseTask | null> {
  try {
    const response = await api.put<CaseTask>(
      `/cases/${caseId}/tasks/${task.id}`,
      { title: task.title, due_date: task.due_date || null, is_completed: task.is_completed },
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function deleteCaseTask(caseId: number, taskId: number): Promise<boolean> {
  try {
    await api.delete(`/cases/${caseId}/tasks/${taskId}`, { headers: await getAuthHeaders() });
    return true;
  } catch {
    return false;
  }
}

export async function uploadCaseAttachment(caseId: number, file: File): Promise<CaseAttachment | null> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<CaseAttachment>(`/cases/${caseId}/attachments`, formData, {
      headers: await getAuthHeaders(),
    });
    return (await indexCaseAttachment(caseId, response.data.id)) ?? response.data;
  } catch {
    return null;
  }
}

export async function indexCaseAttachment(caseId: number, attachmentId: number): Promise<CaseAttachment | null> {
  try {
    const response = await api.post<CaseAttachment>(
      `/cases/${caseId}/attachments/${attachmentId}/index`,
      null,
      { headers: await getAuthHeaders() },
    );
    return response.data;
  } catch {
    return null;
  }
}

export async function downloadCaseAttachment(
  caseId: number,
  attachmentId: number,
  filename: string,
): Promise<boolean> {
  try {
    const response = await api.get<Blob>(`/cases/${caseId}/attachments/${attachmentId}/download`, {
      headers: await getAuthHeaders(),
      responseType: 'blob',
    });
    const objectUrl = URL.createObjectURL(response.data);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
    return true;
  } catch {
    return false;
  }
}

export async function deleteCaseAttachment(caseId: number, attachmentId: number): Promise<boolean> {
  try {
    await api.delete(`/cases/${caseId}/attachments/${attachmentId}`, { headers: await getAuthHeaders() });
    return true;
  } catch {
    return false;
  }
}
