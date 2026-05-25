import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export async function askLegalQuestion(question: string): Promise<string> {
  // Placeholder keeps the UI usable before the backend RAG endpoint is implemented.
  if (!question.trim()) {
    return '질문을 입력하면 RAG 검색 결과와 생성 답변을 표시합니다.';
  }

  try {
    const response = await api.post<{ answer: string }>('/rag/ask', { question });
    return response.data.answer;
  } catch {
    return '현재 RAG API가 아직 준비되지 않았습니다. 백엔드 엔드포인트 추가 후 자동으로 연결됩니다.';
  }
}
