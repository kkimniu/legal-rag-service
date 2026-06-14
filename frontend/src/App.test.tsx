import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { fetchCurrentUser, login, register } from './api/auth';
import { createChatSession, fetchChatMessages, fetchChatSessions, sendChatMessage } from './api/chat';

vi.mock('./api/auth', () => ({
  clearStoredToken: vi.fn(),
  fetchCurrentUser: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
}));

vi.mock('./api/chat', () => ({
  createChatSession: vi.fn(),
  deleteChatSession: vi.fn(),
  fetchChatMessages: vi.fn(),
  fetchChatSessions: vi.fn(),
  sendChatMessage: vi.fn(),
}));

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);
const mockedLogin = vi.mocked(login);
const mockedRegister = vi.mocked(register);
const mockedCreateChatSession = vi.mocked(createChatSession);
const mockedFetchChatSessions = vi.mocked(fetchChatSessions);
const mockedFetchChatMessages = vi.mocked(fetchChatMessages);
const mockedSendChatMessage = vi.mocked(sendChatMessage);

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetchCurrentUser.mockResolvedValue(null);
    mockedFetchChatSessions.mockResolvedValue([]);
    mockedFetchChatMessages.mockResolvedValue([]);
  });

  it('renders chatbot shell and disabled message box before login', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: '법률 챗봇' })).toBeInTheDocument();
    expect(screen.getByLabelText('법 분야')).toBeInTheDocument();
    expect(screen.getByLabelText('메시지')).toBeDisabled();
    expect(screen.getByText('로그인 후 채팅을 시작하세요')).toBeInTheDocument();
  });

  it('logs in, creates a chat session, sends a message, and renders sources', async () => {
    const session = {
      id: 1,
      title: '계약 불이행 책임',
      created_at: '2026-06-14T10:00:00',
      updated_at: '2026-06-14T10:00:00',
      message_count: 2,
      last_message_preview: '검색 근거에 기반한 답변입니다.',
    };
    mockedLogin.mockResolvedValue({
      user: { id: 1, email: 'user@example.com', is_active: true },
      token: 'token',
      message: '로그인되었습니다.',
    });
    mockedCreateChatSession.mockResolvedValue(session);
    mockedSendChatMessage.mockResolvedValue({
      session,
      is_ready: true,
      user_message: {
        id: 10,
        role: 'user',
        content: '계약 불이행 책임은 무엇인가요?',
        sources: [],
        created_at: '2026-06-14T10:01:00',
      },
      assistant_message: {
        id: 11,
        role: 'assistant',
        content: '검색 근거에 기반한 답변입니다.',
        created_at: '2026-06-14T10:01:01',
        sources: [
          {
            id: 'chunk-1',
            title: '손해배상',
            domain_name: '민사법',
            source_type: 'qa',
            text: '손해배상 근거 본문입니다.',
            score: 0.2,
            metadata: {},
          },
        ],
      },
    });

    render(<App />);

    await userEvent.type(screen.getByLabelText('이메일'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'Password123!');
    await userEvent.click(screen.getAllByRole('button', { name: '로그인' })[1]);

    expect(await screen.findByText('user@example.com')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '새 대화' }));
    expect(mockedCreateChatSession).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText('메시지'), '계약 불이행 책임은 무엇인가요?');
    await userEvent.click(screen.getByRole('button', { name: '보내기' }));

    expect(screen.getByText('계약 불이행 책임은 무엇인가요?')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedCreateChatSession).toHaveBeenCalledWith('계약 불이행 책임은 무엇인가요?');
      expect(mockedSendChatMessage).toHaveBeenCalledWith(1, '계약 불이행 책임은 무엇인가요?', '01_civil_law');
    });
    expect(await screen.findByText('검색 근거에 기반한 답변입니다.')).toBeInTheDocument();
    expect(screen.getByText('검색 근거 1개')).toBeInTheDocument();
  });

  it('treats successful registration as an authenticated session', async () => {
    mockedRegister.mockResolvedValue({
      user: { id: 2, email: 'new@example.com', is_active: true },
      token: 'new-token',
      message: '회원가입 후 로그인되었습니다.',
    });

    render(<App />);

    await userEvent.click(screen.getByRole('button', { name: '회원가입' }));
    await userEvent.type(screen.getByLabelText('이메일'), 'new@example.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'Password123!');
    await userEvent.click(screen.getByRole('button', { name: '가입하기' }));

    expect(await screen.findByText('new@example.com')).toBeInTheDocument();
    expect(screen.getByLabelText('메시지')).toBeEnabled();
    expect(mockedFetchChatSessions).toHaveBeenCalled();
  });
});
