import axios from 'axios';

export type RagSource = {
  id: string;
  title?: string | null;
  domain_name?: string | null;
  source_type?: string | null;
  text: string;
  score?: number | null;
  metadata: Record<string, string | number | boolean>;
};

export type RagAnswer = {
  answer: string;
  sources: RagSource[];
  is_ready: boolean;
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export async function askLegalQuestion(question: string): Promise<RagAnswer> {
  if (!question.trim()) {
    return {
      answer: '질문을 입력하면 RAG 검색 결과와 생성 답변을 표시합니다.',
      sources: [],
      is_ready: false,
    };
  }

  try {
    const response = await api.post<RagAnswer>('/rag/ask', { question });
    return response.data;
  } catch {
    return {
      answer: 'RAG API에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.',
      sources: [],
      is_ready: false,
    };
  }
}
