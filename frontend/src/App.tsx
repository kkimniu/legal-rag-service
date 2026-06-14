import { type FormEvent, useEffect, useRef, useState } from 'react';
import { clearStoredToken, fetchCurrentUser, login, register, type User } from './api/auth';
import {
  createChatSession,
  deleteChatSession,
  fetchChatMessages,
  fetchChatSessions,
  sendChatMessage,
  type ChatMessage,
  type ChatSession,
} from './api/chat';

const domainOptions = [
  { value: '', label: '전체 분야' },
  { value: '01_civil_law', label: '민사법' },
  { value: '02_intellectual_property_law', label: '지식재산권법' },
  { value: '03_administrative_law', label: '행정법' },
  { value: '04_criminal_law', label: '형사법' },
];

export function App() {
  const [message, setMessage] = useState('');
  const [domainCode, setDomainCode] = useState('01_civil_law');
  const [isLoading, setIsLoading] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMessage, setAuthMessage] = useState('PostgreSQL과 마이그레이션 적용 후 로그인할 수 있습니다.');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatStatus, setChatStatus] = useState('로그인하면 대화형 RAG 챗봇을 사용할 수 있습니다.');
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetchCurrentUser().then(async (user) => {
      if (user) {
        setCurrentUser(user);
        setAuthMessage('저장된 토큰으로 로그인 상태를 복원했습니다.');
        await refreshSessions();
      }
    });
  }, []);

  useEffect(() => {
    if (typeof messageEndRef.current?.scrollIntoView === 'function') {
      messageEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages.length, isLoading]);

  async function refreshSessions() {
    const nextSessions = await fetchChatSessions();
    setSessions(nextSessions);
    if (nextSessions.length > 0 && !activeSession) {
      setActiveSession(nextSessions[0]);
      setMessages(await fetchChatMessages(nextSessions[0].id));
    }
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const authResult = authMode === 'login' ? await login(email, password) : await register(email, password);
    setAuthMessage(authResult.message);
    if (authResult.user) {
      setCurrentUser(authResult.user);
      const nextSessions = await fetchChatSessions();
      setSessions(nextSessions);
      if (nextSessions.length > 0) {
        setActiveSession(nextSessions[0]);
        setMessages(await fetchChatMessages(nextSessions[0].id));
      } else {
        setActiveSession(null);
        setMessages([]);
      }
      setChatStatus('대화방을 선택하거나 새 대화를 시작하세요.');
    }
  }

  function handleLogout() {
    clearStoredToken();
    setCurrentUser(null);
    setSessions([]);
    setActiveSession(null);
    setMessages([]);
    setAuthMessage('로그아웃되었습니다.');
    setChatStatus('로그인하면 대화형 RAG 챗봇을 사용할 수 있습니다.');
  }

  function handleCreateSession() {
    setActiveSession(null);
    setMessages([]);
    setMessage('');
    setChatStatus('새 채팅입니다. 첫 메시지를 보내면 대화가 저장됩니다.');
  }

  async function handleSelectSession(session: ChatSession) {
    setActiveSession(session);
    setMessages(await fetchChatMessages(session.id));
    setChatStatus('대화 이력을 불러왔습니다.');
  }

  async function handleDeleteSession(session: ChatSession) {
    const deleted = await deleteChatSession(session.id);
    if (!deleted) {
      setChatStatus('대화방을 삭제하지 못했습니다.');
      return;
    }
    const nextSessions = sessions.filter((item) => item.id !== session.id);
    setSessions(nextSessions);
    if (activeSession?.id === session.id) {
      setActiveSession(nextSessions[0] ?? null);
      setMessages(nextSessions[0] ? await fetchChatMessages(nextSessions[0].id) : []);
    }
    setChatStatus('대화방을 삭제했습니다.');
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }

    let session = activeSession;
    if (!session) {
      session = await createChatSession(message.trim().slice(0, 40));
      if (!session) {
        setChatStatus('대화방을 만들 수 없습니다. 로그인 또는 DB 상태를 확인해주세요.');
        return;
      }
      setActiveSession(session);
      setSessions([session, ...sessions]);
    }

    const content = message.trim();
    const optimisticUserMessage: ChatMessage = {
      id: -Date.now(),
      role: 'user',
      content,
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessage('');
    setMessages((items) => [...items, optimisticUserMessage]);
    setIsLoading(true);
    setChatStatus('검색 근거를 찾고 답변을 생성하는 중입니다.');

    const turn = await sendChatMessage(session.id, content, domainCode);
    if (!turn) {
      setChatStatus('챗봇 API에 연결할 수 없습니다. 백엔드 서버 상태를 확인해주세요.');
      setMessages((items) => items.filter((item) => item.id !== optimisticUserMessage.id));
      setIsLoading(false);
      return;
    }

    setMessages((items) => [
      ...items.filter((item) => item.id !== optimisticUserMessage.id),
      turn.user_message,
      turn.assistant_message,
    ]);
    setActiveSession(turn.session);
    setSessions((items) => [turn.session, ...items.filter((item) => item.id !== turn.session.id)]);
    setChatStatus(turn.is_ready ? 'RAG 답변이 생성되었습니다.' : 'RAG 준비가 필요합니다.');
    setIsLoading(false);
  }

  return (
    <main className="app-shell">
      <section className="chat-layout">
        <aside className="sidebar">
          <div className="brand-block">
            <p className="eyebrow">Legal RAG Service</p>
            <h1>법률 챗봇</h1>
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

          {currentUser && (
            <section className="session-panel">
              <div className="section-heading">
                <h2>대화 목록</h2>
                <button type="button" className="secondary-button" onClick={handleCreateSession}>
                  새 대화
                </button>
              </div>
              {sessions.length > 0 ? (
                <div className="session-list">
                  {sessions.map((session) => (
                    <article className="session-item" key={session.id}>
                      <button
                        type="button"
                        className={activeSession?.id === session.id ? 'session-open-button active-session' : 'session-open-button'}
                        onClick={() => handleSelectSession(session)}
                      >
                        <span>{session.title}</span>
                        <small>
                          메시지 {session.message_count}개
                          {session.last_message_preview ? ` · ${session.last_message_preview}` : ''}
                        </small>
                        <time>{new Date(session.updated_at).toLocaleString('ko-KR')}</time>
                      </button>
                      <button type="button" className="session-delete-button" onClick={() => handleDeleteSession(session)}>
                        삭제
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="empty-state">아직 저장된 대화가 없습니다.</p>
              )}
            </section>
          )}
        </aside>

        <section className="chat-panel" aria-label="챗봇">
          <header className="chat-header">
            <div>
              <h2>{activeSession?.title ?? '새 채팅'}</h2>
              <p>{chatStatus}</p>
            </div>
            <div className="domain-control">
              <label htmlFor="domain">법 분야</label>
              <select id="domain" value={domainCode} onChange={(event) => setDomainCode(event.target.value)}>
                {domainOptions.map((option) => (
                  <option key={option.value || 'all'} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </header>

          <div className="message-list" aria-live="polite">
            {messages.length > 0 ? (
              messages.map((item) => (
                <article className={`message-bubble ${item.role}`} key={item.id}>
                  <span>{item.role === 'user' ? '사용자' : 'AI'}</span>
                  <p>{item.content}</p>
                  {item.sources.length > 0 && (
                    <details>
                      <summary>검색 근거 {item.sources.length}개</summary>
                      <div className="sources-list">
                        {item.sources.map((source, index) => (
                          <section className="source-item" key={`${item.id}-${source.id}`}>
                            <div className="source-meta">
                              <span>근거 {index + 1}</span>
                              <span>{source.domain_name ?? '분야 미상'}</span>
                              {source.score !== null && source.score !== undefined && <span>거리 {source.score.toFixed(3)}</span>}
                            </div>
                            <h3>{source.title ?? '제목 없음'}</h3>
                            <p>{source.text}</p>
                          </section>
                        ))}
                      </div>
                    </details>
                  )}
                </article>
              ))
            ) : (
              <div className="empty-chat">
                <h2>{currentUser ? '새 질문으로 채팅을 시작하세요' : '로그인 후 채팅을 시작하세요'}</h2>
                <p>한 채팅 안에서는 이전 질문과 답변이 누적되고, 새 주제는 새 대화에서 다시 시작합니다.</p>
              </div>
            )}
            <div ref={messageEndRef} />
          </div>

          <form className="chat-form" onSubmit={handleMessageSubmit}>
            <label htmlFor="message">메시지</label>
            <textarea
              id="message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="예: 계약 불이행으로 손해가 발생한 경우 손해배상 책임은 어떻게 판단되나요?"
              rows={3}
              disabled={!currentUser || isLoading}
            />
            <button type="submit" disabled={!currentUser || isLoading}>
              {isLoading ? '답변 생성 중...' : '보내기'}
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}
