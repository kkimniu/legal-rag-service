import { type FormEvent, useEffect, useState } from 'react';
import { clearStoredToken, fetchCurrentUser, login, register, type User } from './api/auth';
import { askLegalQuestion, fetchRagHistory, type RagAnswer, type RagHistoryItem } from './api/legalQa';

const initialResult: RagAnswer = {
  answer: '질문을 입력하면 검색된 법률 근거와 생성 답변이 여기에 표시됩니다.',
  sources: [],
  is_ready: false,
};

const domainOptions = [
  { value: '', label: '전체 분야' },
  { value: '01_civil_law', label: '민사법' },
  { value: '02_intellectual_property_law', label: '지식재산권법' },
  { value: '03_administrative_law', label: '행정법' },
  { value: '04_criminal_law', label: '형사법' },
];

export function App() {
  const [question, setQuestion] = useState('');
  const [domainCode, setDomainCode] = useState('');
  const [result, setResult] = useState<RagAnswer>(initialResult);
  const [isLoading, setIsLoading] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMessage, setAuthMessage] = useState('PostgreSQL과 마이그레이션 적용 후 로그인할 수 있습니다.');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [history, setHistory] = useState<RagHistoryItem[]>([]);

  useEffect(() => {
    fetchCurrentUser().then(async (user) => {
      if (user) {
        setCurrentUser(user);
        setAuthMessage('저장된 토큰으로 로그인 상태를 복원했습니다.');
        setHistory(await fetchRagHistory());
      }
    });
  }, []);

  async function handleQuestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setResult(await askLegalQuestion(question, domainCode));
    if (currentUser) {
      setHistory(await fetchRagHistory());
    }
    setIsLoading(false);
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const authResult = authMode === 'login' ? await login(email, password) : await register(email, password);
    setAuthMessage(authResult.message);
    if (authResult.user) {
      setCurrentUser(authResult.user);
      setHistory(await fetchRagHistory());
    }
  }

  function handleLogout() {
    clearStoredToken();
    setCurrentUser(null);
    setHistory([]);
    setAuthMessage('로그아웃되었습니다.');
  }

  function handleHistorySelect(item: RagHistoryItem) {
    setQuestion(item.question);
    setResult({
      answer: item.answer,
      sources: item.sources,
      is_ready: true,
    });
  }

  return (
    <main className="app-shell">
      <section className="qa-panel">
        <header className="app-header">
          <div>
            <p className="eyebrow">Legal RAG Service</p>
            <h1>법률 질의응답</h1>
            <p className="description">AI Hub 법률 데이터를 검색하고 근거 기반 답변을 생성하는 업무형 웹 서비스입니다.</p>
          </div>
          <section className="auth-panel" aria-label="인증">
            {currentUser ? (
              <div className="user-summary">
                <span>{currentUser.email}</span>
                <button type="button" className="secondary-button" onClick={handleLogout}>
                  로그아웃
                </button>
              </div>
            ) : (
              <form className="auth-form" onSubmit={handleAuthSubmit}>
                <div className="auth-tabs" role="tablist" aria-label="인증 모드">
                  <button type="button" className={authMode === 'login' ? 'active-tab' : ''} onClick={() => setAuthMode('login')}>
                    로그인
                  </button>
                  <button type="button" className={authMode === 'register' ? 'active-tab' : ''} onClick={() => setAuthMode('register')}>
                    회원가입
                  </button>
                </div>
                <label htmlFor="email">이메일</label>
                <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
                <label htmlFor="password">비밀번호</label>
                <input id="password" type="password" minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} />
                <button type="submit">{authMode === 'login' ? '로그인' : '가입하기'}</button>
              </form>
            )}
            <p className="auth-message">{authMessage}</p>
          </section>
        </header>

        <form className="question-form" onSubmit={handleQuestionSubmit}>
          <div className="question-controls">
            <label htmlFor="domain">법 분야</label>
            <select id="domain" value={domainCode} onChange={(event) => setDomainCode(event.target.value)}>
              {domainOptions.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
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

        {currentUser && (
          <section className="history-section">
            <div className="section-heading">
              <h2>최근 질문 이력</h2>
              <button type="button" className="secondary-button" onClick={async () => setHistory(await fetchRagHistory())}>
                새로고침
              </button>
            </div>
            {history.length > 0 ? (
              <div className="history-list">
                {history.map((item) => (
                  <article className="history-item" key={item.id}>
                    <button type="button" onClick={() => handleHistorySelect(item)}>
                      <span>{item.question}</span>
                      <time>{new Date(item.created_at).toLocaleString('ko-KR')}</time>
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">로그인 상태에서 질문하면 이력이 저장됩니다.</p>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
