import { type FormEvent, useState } from 'react';
import { askLegalQuestion } from './api/legalQa';

export function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('백엔드 RAG API가 연결되면 답변이 여기에 표시됩니다.');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAnswer(await askLegalQuestion(question));
  }

  return (
    <main className="app-shell">
      <section className="qa-panel">
        <div>
          <p className="eyebrow">Legal RAG Service</p>
          <h1>법률 질의응답</h1>
          <p className="description">AI Hub 법률 데이터를 검색하고 근거 기반 답변을 생성하는 업무형 웹 서비스 초기 화면입니다.</p>
        </div>

        <form className="question-form" onSubmit={handleSubmit}>
          <label htmlFor="question">질문</label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="예: 임대차 계약 해지 통보는 언제까지 해야 하나요?"
            rows={5}
          />
          <button type="submit">질문하기</button>
        </form>

        <section className="answer-box" aria-live="polite">
          <h2>답변</h2>
          <p>{answer}</p>
        </section>
      </section>
    </main>
  );
}
