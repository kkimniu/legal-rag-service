import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { fetchCurrentUser, login } from './api/auth';
import { askLegalQuestion, deleteRagHistoryItem, fetchRagHistory } from './api/legalQa';

vi.mock('./api/auth', () => ({
  clearStoredToken: vi.fn(),
  fetchCurrentUser: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
}));

vi.mock('./api/legalQa', () => ({
  askLegalQuestion: vi.fn(),
  deleteRagHistoryItem: vi.fn(),
  fetchRagHistory: vi.fn(),
}));

const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);
const mockedLogin = vi.mocked(login);
const mockedAskLegalQuestion = vi.mocked(askLegalQuestion);
const mockedFetchRagHistory = vi.mocked(fetchRagHistory);
const mockedDeleteRagHistoryItem = vi.mocked(deleteRagHistoryItem);

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedFetchCurrentUser.mockResolvedValue(null);
    mockedFetchRagHistory.mockResolvedValue([]);
  });

  it('renders the question form and initial answer state', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: '법률 질의응답' })).toBeInTheDocument();
    expect(screen.getByLabelText('법 분야')).toBeInTheDocument();
    expect(screen.getByLabelText('질문')).toBeInTheDocument();
    expect(screen.getByText('질문을 입력하면 검색된 법률 근거와 생성 답변이 여기에 표시됩니다.')).toBeInTheDocument();
  });

  it('submits a question with the selected domain and renders answer sources', async () => {
    mockedAskLegalQuestion.mockResolvedValue({
      answer: '행정처분 취소소송 답변입니다.',
      is_ready: true,
      sources: [
        {
          id: 'chunk-1',
          title: '행정처분취소',
          domain_name: '행정법',
          source_type: 'qa',
          text: '행정처분 취소소송의 근거 본문입니다.',
          score: 0.12,
          metadata: {},
        },
      ],
    });

    render(<App />);

    await userEvent.selectOptions(screen.getByLabelText('법 분야'), '03_administrative_law');
    await userEvent.type(screen.getByLabelText('질문'), '행정처분 취소소송에서 무엇을 확인해야 하나요?');
    await userEvent.click(screen.getByRole('button', { name: '질문하기' }));

    await waitFor(() => {
      expect(mockedAskLegalQuestion).toHaveBeenCalledWith('행정처분 취소소송에서 무엇을 확인해야 하나요?', '03_administrative_law');
    });
    expect(await screen.findByText('행정처분 취소소송 답변입니다.')).toBeInTheDocument();
    expect(screen.getByText('행정처분취소')).toBeInTheDocument();
    expect(screen.getByText('RAG 연결됨')).toBeInTheDocument();
  });

  it('logs in, shows history, opens saved answers, and deletes an item', async () => {
    mockedLogin.mockResolvedValue({
      user: { id: 1, email: 'user@example.com', is_active: true },
      token: 'token',
      message: '로그인되었습니다.',
    });
    mockedFetchRagHistory.mockResolvedValue([
      {
        id: 10,
        question: '저장된 질문입니다.',
        answer: '저장된 답변입니다.',
        created_at: '2026-06-07T10:00:00',
        sources: [
          {
            id: 'history-source',
            title: '저장된 근거',
            domain_name: '민사법',
            source_type: 'qa',
            text: '저장된 근거 본문입니다.',
            score: 0.3,
            metadata: {},
          },
        ],
      },
    ]);
    mockedDeleteRagHistoryItem.mockResolvedValue(true);

    render(<App />);

    await userEvent.type(screen.getByLabelText('이메일'), 'user@example.com');
    await userEvent.type(screen.getByLabelText('비밀번호'), 'Password123!');
    await userEvent.click(screen.getAllByRole('button', { name: '로그인' })[1]);

    expect(await screen.findByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('저장된 질문입니다.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /저장된 질문입니다./ }));
    expect(screen.getByText('저장된 답변입니다.')).toBeInTheDocument();
    expect(screen.getByText('저장된 근거')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '삭제' }));
    await waitFor(() => {
      expect(mockedDeleteRagHistoryItem).toHaveBeenCalledWith(10);
    });
    expect(screen.getByText('로그인 상태에서 질문하면 이력이 저장됩니다.')).toBeInTheDocument();
  });
});
