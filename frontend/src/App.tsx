import { type FormEvent, useState } from 'react';
import { askLegalQuestion, type RagAnswer } from './api/legalQa';

const initialResult: RagAnswer = {
  answer: '질문을 입력하면 검색된 법률 근거와 생성 답변이 여기에 표시됩니다.',
  sources: [],
  is_ready: false,
};

export function App() {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<RagAnswer>(initialResult);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setResult(await askLegalQuestion(question));
    setIsLoading(false);
  }

  return (
    <main className="app-shell">
      <section className="qa-panel">
        <div>
          <p className="eyebrow">Legal RAG Service</p>
          <h1>법률 질의응답</h1>
          <p className="description">AI Hub 법률 데이터를 검색하고 근거 기반 답변을 생성하는 업무형 웹 서비스입니다.</p>
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
          <button type="submit" disabled={isLoading}>
            {isLoading ? '검색 중...' : '질문하기'}
          </button>
        </form>

        <section className="answer-box" aria-live="polite">
          <div className="answer-heading">
            <h2>답변</h2>
            <span className={result.is_ready ? 'status-ready' : 'status-waiting'}>
              {result.is_ready ? 'RAG 연결됨' : '준비 중'}
            </span>
          </div>
          <p>{result.answer}</p>
        </section>

        {result.sources.length > 0 && (
          <section className="sources-section">
            <h2>검색 근거</h2>
            <div className="sources-list">
              {result.sources.map((source, index) => (
                <article className="source-item" key={source.id}>
                  <div className="source-meta">
                    <span>근거 {index + 1}</span>
                    <span>{source.domain_name ?? '분야 미상'}</span>
                    {source.score !== null && source.score !== undefined && <span>거리 {source.score.toFixed(3)}</span>}
                  </div>
                  <h3>{source.title ?? '제목 없음'}</h3>
                  <p>{source.text}</p>
                </article>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
