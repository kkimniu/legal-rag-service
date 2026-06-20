import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { fetchCurrentUser, login, register } from './api/auth';
import { createCase, createCaseNote, fetchCaseNotes, fetchCases, updateCaseStatus } from './api/cases';
import { createChatSession, fetchChatMessages, fetchChatSessions, sendChatMessage, updateChatSessionPin } from './api/chat';

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
  updateChatSessionPin: vi.fn(),
}));

vi.mock('./api/cases', () => ({
  createCase: vi.fn(),
  createCaseNote: vi.fn(),
  fetchCaseNotes: vi.fn(),
  fetchCases: vi.fn(),
  updateCaseStatus: vi.fn(),
}));

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);
const mockedLogin = vi.mocked(login);
const mockedRegister = vi.mocked(register);
const mockedCreateChatSession = vi.mocked(createChatSession);
const mockedFetchChatSessions = vi.mocked(fetchChatSessions);
const mockedFetchChatMessages = vi.mocked(fetchChatMessages);
const mockedSendChatMessage = vi.mocked(sendChatMessage);
const mockedUpdateChatSessionPin = vi.mocked(updateChatSessionPin);
const mockedCreateCase = vi.mocked(createCase);
const mockedCreateCaseNote = vi.mocked(createCaseNote);
const mockedFetchCaseNotes = vi.mocked(fetchCaseNotes);
const mockedFetchCases = vi.mocked(fetchCases);
const mockedUpdateCaseStatus = vi.mocked(updateCaseStatus);

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetchCurrentUser.mockResolvedValue(null);
    mockedFetchChatSessions.mockResolvedValue([]);
    mockedFetchChatMessages.mockResolvedValue([]);
    mockedFetchCases.mockResolvedValue([]);
    mockedFetchCaseNotes.mockResolvedValue([]);
    mockedUpdateCaseStatus.mockResolvedValue(null);
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
      case_id: 1,
      domain_code: '01_civil_law',
      is_pinned: false,
      created_at: '2026-06-14T10:00:00',
      updated_at: '2026-06-14T10:00:00',
      message_count: 2,
      last_message_preview: '검색 근거에 기반한 답변입니다.',
    };
    mockedLogin.mockResolvedValue({
      user: { id: 1, email: 'user@example.com', is_active: true },
      token: 'token',
      refreshToken: 'refresh-token',
      message: '로그인되었습니다.',
    });
    mockedFetchCases.mockResolvedValue([
      {
        id: 1,
        title: '계약 분쟁',
        summary: '',
        status: 'active',
        domain_code: '01_civil_law',
        created_at: '2026-06-14T09:00:00',
        updated_at: '2026-06-14T09:00:00',
        note_count: 0,
        chat_count: 0,
      },
    ]);
    mockedCreateChatSession.mockResolvedValue(session);
    mockedSendChatMessage.mockResolvedValue({
      session,
      is_ready: true,
      user_message: {
        id: 10,
        role: 'user',
        content: '계약 불이행 책임은 무엇인가요?',
        answer_mode: 'issue',
        evidence_status: null,
        evidence_warnings: [],
        sources: [],
        created_at: '2026-06-14T10:01:00',
      },
      assistant_message: {
        id: 11,
        role: 'assistant',
        content: '검색 근거에 기반한 답변입니다.',
        answer_mode: 'issue',
        evidence_status: 'partial',
        evidence_warnings: ['신뢰 가능한 법령 근거가 부족합니다.'],
        created_at: '2026-06-14T10:01:01',
        sources: [
          {
            id: 'chunk-1',
            title: '손해배상',
            domain_name: '민사법',
            source_type: 'qa',
            text: '손해배상 근거 본문입니다.',
            score: 0.2,
            metadata: { evidence_type: 'precedent', meta_case_number: '2024다12345' },
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
    await userEvent.selectOptions(screen.getByLabelText('답변 모드'), 'issue');
    await userEvent.type(screen.getByLabelText('메시지'), '계약 불이행 책임은 무엇인가요?');
    await userEvent.click(screen.getByRole('button', { name: '보내기' }));

    expect(screen.getByText('계약 불이행 책임은 무엇인가요?')).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedCreateChatSession).toHaveBeenCalledWith('계약 불이행 책임은 무엇인가요?', '01_civil_law', 1);
      expect(mockedSendChatMessage).toHaveBeenCalledWith(1, '계약 불이행 책임은 무엇인가요?', 'issue');
    });
    expect(await screen.findByText('검색 근거에 기반한 답변입니다.')).toBeInTheDocument();
    expect(screen.getAllByText('쟁점 정리').length).toBeGreaterThan(1);
    expect(screen.getByText('근거 일부 부족')).toBeInTheDocument();
    expect(screen.getByText('근거 품질 경고 1개')).toBeInTheDocument();
    expect(screen.getByText('검색 근거 1개')).toBeInTheDocument();
    expect(screen.getByText('판례 근거 1')).toBeInTheDocument();
    expect(screen.getByText('2024다12345')).toBeInTheDocument();
  });

  it('treats successful registration as an authenticated session', async () => {
    mockedRegister.mockResolvedValue({
      user: { id: 2, email: 'new@example.com', is_active: true },
      token: 'new-token',
      refreshToken: 'new-refresh-token',
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

  it('creates a legal case note from the sidebar', async () => {
    mockedFetchCurrentUser.mockResolvedValue({ id: 1, email: 'user@example.com', is_active: true });
    mockedCreateCase.mockResolvedValue({
      id: 3,
      title: '임대차 보증금 반환',
      summary: '',
      status: 'active',
      domain_code: '01_civil_law',
      created_at: '2026-06-14T12:00:00',
      updated_at: '2026-06-14T12:00:00',
      note_count: 0,
      chat_count: 0,
    });
    mockedCreateCaseNote.mockResolvedValue({
      id: 7,
      case_id: 3,
      title: '핵심 사실',
      content: '계약 종료 후 보증금을 받지 못함',
      created_at: '2026-06-14T12:10:00',
      updated_at: '2026-06-14T12:10:00',
    });

    render(<App />);

    expect(await screen.findByText('user@example.com')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('새 사건'), '임대차 보증금 반환');
    await userEvent.click(screen.getByRole('button', { name: '사건 만들기' }));

    expect(mockedCreateCase).toHaveBeenCalledWith('임대차 보증금 반환', '01_civil_law');
    expect((await screen.findAllByText('임대차 보증금 반환')).length).toBeGreaterThan(0);

    await userEvent.type(screen.getByLabelText('메모 제목'), '핵심 사실');
    await userEvent.type(screen.getByLabelText('메모 내용'), '계약 종료 후 보증금을 받지 못함');
    await userEvent.click(screen.getByRole('button', { name: '메모 저장' }));

    expect(mockedCreateCaseNote).toHaveBeenCalledWith(3, '핵심 사실', '계약 종료 후 보증금을 받지 못함');
    expect((await screen.findAllByText('계약 종료 후 보증금을 받지 못함')).length).toBeGreaterThan(0);
  });

  it('filters chat sessions by the selected legal case', async () => {
    mockedFetchCurrentUser.mockResolvedValue({ id: 1, email: 'user@example.com', is_active: true });
    mockedFetchCases.mockResolvedValue([
      {
        id: 1,
        title: '임대차 사건',
        summary: '',
        status: 'active',
        domain_code: '01_civil_law',
        created_at: '2026-06-14T09:00:00',
        updated_at: '2026-06-14T09:00:00',
        note_count: 0,
        chat_count: 1,
      },
      {
        id: 2,
        title: '상표 사건',
        summary: '',
        status: 'active',
        domain_code: '02_intellectual_property_law',
        created_at: '2026-06-14T09:10:00',
        updated_at: '2026-06-14T09:10:00',
        note_count: 0,
        chat_count: 1,
      },
    ]);
    mockedFetchChatSessions.mockResolvedValue([
      {
        id: 10,
        title: '임대차 상담',
        case_id: 1,
        domain_code: '01_civil_law',
        is_pinned: false,
        created_at: '2026-06-14T10:00:00',
        updated_at: '2026-06-14T10:00:00',
        message_count: 2,
        last_message_preview: '보증금 반환 검토',
      },
      {
        id: 11,
        title: '상표권 상담',
        case_id: 2,
        domain_code: '02_intellectual_property_law',
        is_pinned: false,
        created_at: '2026-06-14T11:00:00',
        updated_at: '2026-06-14T11:00:00',
        message_count: 1,
        last_message_preview: '상표 침해 검토',
      },
    ]);
    mockedFetchCaseNotes.mockResolvedValue([
      {
        id: 3,
        case_id: 1,
        title: '최근 쟁점',
        content: '임대차 보증금 반환 가능성을 확인해야 함',
        created_at: '2026-06-14T12:00:00',
        updated_at: '2026-06-14T12:00:00',
      },
    ]);
    mockedUpdateCaseStatus.mockResolvedValue({
      id: 1,
      title: '임대차 사건',
      summary: '',
      status: 'closed',
      domain_code: '01_civil_law',
      created_at: '2026-06-14T09:00:00',
      updated_at: '2026-06-14T13:00:00',
      note_count: 1,
      chat_count: 1,
    });

    render(<App />);

    expect((await screen.findAllByText('임대차 상담')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('최근 쟁점').length).toBeGreaterThan(0);
    expect(screen.getAllByText('임대차 보증금 반환 가능성을 확인해야 함').length).toBeGreaterThan(0);
    expect(screen.getAllByText('연결 대화').length).toBeGreaterThan(0);
    expect(screen.queryByText('상표권 상담')).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('사건 상태'), 'closed');

    expect(mockedUpdateCaseStatus).toHaveBeenCalledWith(1, 'closed');
    expect(await screen.findByText(/사건 상태를 종료 상태로 변경했습니다./)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '이 사건 새 대화' }));

    expect(screen.getByRole('heading', { name: '새 채팅' })).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('선택한 사건 대화만 보기'));

    expect(await screen.findByText('상표권 상담')).toBeInTheDocument();
  });

  it('filters and pins chat sessions', async () => {
    const sessions = [
      {
        id: 1,
        title: '임대차 보증금 상담',
        case_id: null,
        domain_code: '01_civil_law',
        is_pinned: false,
        created_at: '2026-06-14T10:00:00',
        updated_at: '2026-06-14T10:00:00',
        message_count: 2,
        last_message_preview: '보증금 반환 관련 답변',
      },
      {
        id: 2,
        title: '상표권 침해 검토',
        case_id: null,
        domain_code: '02_intellectual_property_law',
        is_pinned: false,
        created_at: '2026-06-14T11:00:00',
        updated_at: '2026-06-14T11:00:00',
        message_count: 1,
        last_message_preview: '상표권 침해 판단',
      },
    ];
    mockedFetchCurrentUser.mockResolvedValue({ id: 1, email: 'user@example.com', is_active: true });
    mockedFetchChatSessions.mockResolvedValue(sessions);
    mockedUpdateChatSessionPin.mockResolvedValue({ ...sessions[0], is_pinned: true });

    render(<App />);

    expect((await screen.findAllByText('임대차 보증금 상담')).length).toBeGreaterThan(0);
    expect(screen.getByText('상표권 침해 검토')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('대화 검색'), '보증금');

    expect(screen.getAllByText('임대차 보증금 상담').length).toBeGreaterThan(0);
    expect(screen.queryByText('상표권 침해 검토')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '고정' }));

    expect(mockedUpdateChatSessionPin).toHaveBeenCalledWith(1, true);
    expect(await screen.findByText('고정 · 임대차 보증금 상담')).toBeInTheDocument();
  });
});
