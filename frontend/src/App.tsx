import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from 'react';
import { clearStoredToken, fetchCurrentUser, login, register, type User } from './api/auth';
import {
  createCase,
  createCaseNote,
  createCaseTask,
  deleteCase,
  deleteCaseAttachment,
  deleteCaseNote,
  deleteCaseTask,
  downloadCaseAttachment,
  fetchCaseAttachments,
  fetchCaseNotes,
  fetchCaseTasks,
  fetchCaseTimeline,
  fetchCases,
  fetchUpcomingCaseTasks,
  generateCaseInsight,
  indexCaseAttachment,
  updateCase,
  updateCaseStatus,
  updateCaseNote,
  updateCaseTask,
  uploadCaseAttachment,
  type CaseAttachment,
  type CaseInsight,
  type CaseNote,
  type CaseStatus,
  type CaseTask,
  type CaseTimelineItem,
  type LegalCase,
  type UpcomingCaseTask,
} from './api/cases';
import {
  createChatSession,
  deleteChatSession,
  fetchChatMessages,
  fetchChatSession,
  fetchChatSessions,
  sendChatMessage,
  updateChatSessionPin,
  type ChatMessage,
  type ChatSession,
} from './api/chat';
import { searchPersonalWorkspace, type PersonalSearchResult, type SearchTypeFilter } from './api/search';

const domainOptions = [
  { value: '', label: '전체 분야' },
  { value: '01_civil_law', label: '민사법' },
  { value: '02_intellectual_property_law', label: '지식재산권법' },
  { value: '03_administrative_law', label: '행정법' },
  { value: '04_criminal_law', label: '형사법' },
];

const answerModeOptions = [
  { value: 'general', label: '기본 답변' },
  { value: 'brief', label: '간단 답변' },
  { value: 'detailed', label: '상세 검토' },
  { value: 'issue', label: '쟁점 정리' },
  { value: 'consultation', label: '상담 준비' },
];

const caseStatusOptions: { value: CaseStatus; label: string }[] = [
  { value: 'active', label: '진행중' },
  { value: 'watching', label: '관찰중' },
  { value: 'closed', label: '종료' },
];

function domainLabel(domainCode?: string | null) {
  return domainOptions.find((option) => option.value === (domainCode ?? ''))?.label ?? '전체 분야';
}

function caseStatusLabel(status?: string | null) {
  return caseStatusOptions.find((option) => option.value === status)?.label ?? '진행중';
}

function answerModeLabel(answerMode?: string | null) {
  return answerModeOptions.find((option) => option.value === (answerMode ?? 'general'))?.label ?? '기본 답변';
}

function evidenceStatusLabel(status?: string | null) {
  if (status === 'sufficient') return '근거 충분';
  if (status === 'partial') return '근거 일부 부족';
  if (status === 'insufficient') return '근거 부족';
  if (status === 'none') return '근거 없음';
  return null;
}

function evidenceLabel(source: ChatMessage['sources'][number]) {
  if (source.metadata.evidence_type === 'case_attachment') return '첨부자료';
  return source.metadata.evidence_type === 'precedent' ? '판례' : '법률';
}

function evidenceBadgeClass(source: ChatMessage['sources'][number]) {
  if (source.metadata.evidence_type === 'precedent') return 'precedent-badge';
  if (source.metadata.evidence_type === 'case_attachment') return 'attachment-badge';
  return 'statute-badge';
}

function caseNumber(source: ChatMessage['sources'][number]) {
  const value = source.metadata.meta_case_number ?? source.metadata.case_number;
  return typeof value === 'string' && value.trim() ? value : null;
}

function attachmentReference(source: ChatMessage['sources'][number]) {
  if (source.metadata.evidence_type !== 'case_attachment') return null;
  const caseId = Number(source.metadata.case_id);
  const attachmentId = Number(source.metadata.attachment_id);
  if (!Number.isInteger(caseId) || !Number.isInteger(attachmentId)) return null;
  return {
    caseId,
    attachmentId,
    filename: source.title ?? `attachment-${attachmentId}`,
  };
}

function sortCaseTasks(tasks: CaseTask[]) {
  return [...tasks].sort((left, right) => {
    if (left.is_completed !== right.is_completed) return left.is_completed ? 1 : -1;
    if (!left.due_date && right.due_date) return 1;
    if (left.due_date && !right.due_date) return -1;
    return (left.due_date ?? left.created_at).localeCompare(right.due_date ?? right.created_at);
  });
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function isTaskOverdue(task: CaseTask) {
  if (!task.due_date || task.is_completed) return false;
  return task.due_date < todayString();
}

function isTaskDueToday(task: CaseTask) {
  if (!task.due_date || task.is_completed) return false;
  return task.due_date === todayString();
}

function isTaskImminent(task: CaseTask) {
  if (!task.due_date || task.is_completed) return false;
  const today = todayString();
  const sevenDaysLater = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  return task.due_date > today && task.due_date <= sevenDaysLater;
}

const SEARCH_TYPE_LABELS: Record<PersonalSearchResult['result_type'], string> = {
  case: '사건',
  note: '메모',
  task: '할 일',
  attachment: '첨부자료',
  chat: '채팅',
};

const SEARCH_TYPE_FILTERS: Array<{ value: SearchTypeFilter; label: string }> = [
  { value: 'all', label: '전체' },
  { value: 'case', label: '사건' },
  { value: 'note', label: '메모' },
  { value: 'task', label: '할 일' },
  { value: 'attachment', label: '첨부' },
  { value: 'chat', label: '채팅' },
];

function searchResultTypeLabel(resultType: PersonalSearchResult['result_type']) {
  return SEARCH_TYPE_LABELS[resultType];
}

const SEARCH_PAGE_SIZE = 8;

function highlightQuery(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase()
      ? <mark key={i}>{part}</mark>
      : part
  );
}

function timelineTypeLabel(activityType: CaseTimelineItem['activity_type']) {
  return {
    case: '사건',
    note: '메모',
    task: '할 일',
    attachment: '첨부자료',
    chat: '채팅',
  }[activityType];
}

export function App() {
  const [message, setMessage] = useState('');
  const [domainCode, setDomainCode] = useState('01_civil_law');
  const [answerMode, setAnswerMode] = useState('general');
  const [isLoading, setIsLoading] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authMessage, setAuthMessage] = useState('PostgreSQL과 마이그레이션 적용 후 로그인할 수 있습니다.');
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [cases, setCases] = useState<LegalCase[]>([]);
  const [activeCase, setActiveCase] = useState<LegalCase | null>(null);
  const [caseNotes, setCaseNotes] = useState<CaseNote[]>([]);
  const [caseAttachments, setCaseAttachments] = useState<CaseAttachment[]>([]);
  const [caseTasks, setCaseTasks] = useState<CaseTask[]>([]);
  const [caseTimeline, setCaseTimeline] = useState<CaseTimelineItem[]>([]);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [upcomingTasks, setUpcomingTasks] = useState<UpcomingCaseTask[]>([]);
  const [deadlineAlertDismissed, setDeadlineAlertDismissed] = useState(false);
  const [caseTitle, setCaseTitle] = useState('');
  const [caseSearch, setCaseSearch] = useState('');
  const [caseStatusFilter, setCaseStatusFilter] = useState<'all' | CaseStatus>('all');
  const [hideClosedCases, setHideClosedCases] = useState(false);
  const [caseInsight, setCaseInsight] = useState<CaseInsight | null>(null);
  const [isGeneratingCaseInsight, setIsGeneratingCaseInsight] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingCase, setEditingCase] = useState<LegalCase | null>(null);
  const [editCaseTitle, setEditCaseTitle] = useState('');
  const [editCaseSummary, setEditCaseSummary] = useState('');
  const [deletingCaseId, setDeletingCaseId] = useState<number | null>(null);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [indexingAttachmentId, setIndexingAttachmentId] = useState<number | null>(null);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDueDate, setTaskDueDate] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionSearch, setSessionSearch] = useState('');
  const [filterSessionsByCase, setFilterSessionsByCase] = useState(true);
  const [chatStatus, setChatStatus] = useState('로그인하면 대화형 RAG 챗봇을 사용할 수 있습니다.');
  const [workspaceSearch, setWorkspaceSearch] = useState('');
  const [workspaceSearchResults, setWorkspaceSearchResults] = useState<PersonalSearchResult[]>([]);
  const [workspaceSearchTotalCount, setWorkspaceSearchTotalCount] = useState(0);
  const [searchTypeFilter, setSearchTypeFilter] = useState<SearchTypeFilter>('all');
  const [searchVisibleCount, setSearchVisibleCount] = useState(SEARCH_PAGE_SIZE);
  const [isWorkspaceSearching, setIsWorkspaceSearching] = useState(false);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const filteredSessions = sessions.filter((session) => {
    if (activeCase && filterSessionsByCase && session.case_id !== activeCase.id) return false;
    const query = sessionSearch.trim().toLowerCase();
    if (!query) return true;
    return [session.title, domainLabel(session.domain_code), session.last_message_preview ?? '']
      .join(' ')
      .toLowerCase()
      .includes(query);
  });
  const filteredCases = cases.filter((legalCase) => {
    if (caseStatusFilter !== 'all' && legalCase.status !== caseStatusFilter) return false;
    if (caseStatusFilter === 'all' && hideClosedCases && legalCase.status === 'closed') return false;
    const query = caseSearch.trim().toLowerCase();
    if (!query) return true;
    return [legalCase.title, legalCase.summary, caseStatusLabel(legalCase.status), domainLabel(legalCase.domain_code)]
      .join(' ')
      .toLowerCase()
      .includes(query);
  });
  const activeCaseSessions = activeCase ? sessions.filter((session) => session.case_id === activeCase.id) : [];
  const recentCaseNote = caseNotes.reduce<CaseNote | null>((latest, note) => {
    if (!latest) return note;
    return new Date(note.updated_at).getTime() > new Date(latest.updated_at).getTime() ? note : latest;
  }, null);
  const activeCaseActivityAt = activeCase
    ? [activeCase.updated_at, ...activeCaseSessions.map((session) => session.updated_at), ...caseNotes.map((note) => note.updated_at)]
        .filter(Boolean)
        .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0]
    : null;

  function toggleSource(key: string) {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function caseTitleForSession(caseId?: number | null) {
    if (!caseId) return null;
    return cases.find((legalCase) => legalCase.id === caseId)?.title ?? null;
  }

  useEffect(() => {
    fetchCurrentUser().then(async (user) => {
      if (user) {
        setCurrentUser(user);
        setAuthMessage('저장된 토큰으로 로그인 상태를 복원했습니다.');
        await refreshCases();
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

  async function refreshCases() {
    const nextCases = await fetchCases();
    setUpcomingTasks(await fetchUpcomingCaseTasks());
    setCases(nextCases);
    if (nextCases.length > 0 && !activeCase) {
      setActiveCase(nextCases[0]);
      setCaseNotes(await fetchCaseNotes(nextCases[0].id));
      setCaseAttachments(await fetchCaseAttachments(nextCases[0].id));
      setCaseTasks(await fetchCaseTasks(nextCases[0].id));
      setCaseTimeline(await fetchCaseTimeline(nextCases[0].id));
    }
  }

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const authResult = authMode === 'login' ? await login(email, password) : await register(email, password);
    setAuthMessage(authResult.message);
    if (authResult.user) {
      setCurrentUser(authResult.user);
      const nextCases = await fetchCases();
      const nextSessions = await fetchChatSessions();
      setUpcomingTasks(await fetchUpcomingCaseTasks());
      setDeadlineAlertDismissed(false);
      setCases(nextCases);
      setActiveCase(nextCases[0] ?? null);
      setCaseInsight(null);
      setCaseNotes(nextCases[0] ? await fetchCaseNotes(nextCases[0].id) : []);
      setCaseAttachments(nextCases[0] ? await fetchCaseAttachments(nextCases[0].id) : []);
      setCaseTasks(nextCases[0] ? await fetchCaseTasks(nextCases[0].id) : []);
      setCaseTimeline(nextCases[0] ? await fetchCaseTimeline(nextCases[0].id) : []);
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
    setWorkspaceSearch('');
    setWorkspaceSearchResults([]);
    clearStoredToken();
    setCurrentUser(null);
    setSessions([]);
    setCases([]);
    setActiveCase(null);
    setCaseNotes([]);
    setCaseAttachments([]);
    setCaseTasks([]);
    setCaseTimeline([]);
    setUpcomingTasks([]);
    setCaseInsight(null);
    setNoteTitle('');
    setNoteContent('');
    setEditingNoteId(null);
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

  async function handleWorkspaceSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = workspaceSearch.trim();
    if (query.length < 2) {
      setWorkspaceSearchResults([]);
      setWorkspaceSearchTotalCount(0);
      return;
    }
    setIsWorkspaceSearching(true);
    setSearchVisibleCount(SEARCH_PAGE_SIZE);
    const { results, totalCount } = await searchPersonalWorkspace(query, searchTypeFilter);
    setWorkspaceSearchResults(results);
    setWorkspaceSearchTotalCount(totalCount);
    setIsWorkspaceSearching(false);
  }

  async function handleSearchTypeChange(type: SearchTypeFilter) {
    setSearchTypeFilter(type);
    setSearchVisibleCount(SEARCH_PAGE_SIZE);
    if (workspaceSearch.trim().length < 2) return;
    setIsWorkspaceSearching(true);
    const { results, totalCount } = await searchPersonalWorkspace(workspaceSearch.trim(), type);
    setWorkspaceSearchResults(results);
    setWorkspaceSearchTotalCount(totalCount);
    setIsWorkspaceSearching(false);
  }

  async function handleSelectSearchResult(result: PersonalSearchResult) {
    if (result.case_id) {
      const legalCase = cases.find((item) => item.id === result.case_id);
      if (legalCase) await handleSelectCase(legalCase);
    }

    if (result.session_id) {
      const session = sessions.find((item) => item.id === result.session_id)
        ?? await fetchChatSession(result.session_id);
      if (session) {
        setSessions((items) => items.some((item) => item.id === session.id) ? items : [session, ...items]);
        await handleSelectSession(session);
      }
    }

    setWorkspaceSearchResults([]);
    setChatStatus('통합 검색 결과를 열었습니다.');
  }

  async function handleSelectTimelineItem(item: CaseTimelineItem) {
    if (!item.session_id) return;
    const session = sessions.find((candidate) => candidate.id === item.session_id)
      ?? await fetchChatSession(item.session_id);
    if (!session) return;
    setSessions((current) => current.some((candidate) => candidate.id === session.id) ? current : [session, ...current]);
    await handleSelectSession(session);
  }

  function handleStartCaseChat() {
    if (!activeCase) return;
    setActiveSession(null);
    setMessages([]);
    setFilterSessionsByCase(true);
    setChatStatus(`${activeCase.title} 사건에 연결된 새 대화입니다. 첫 메시지를 보내면 대화가 저장됩니다.`);
  }

  async function handleGenerateCaseInsight() {
    if (!activeCase || isGeneratingCaseInsight) return;
    setIsGeneratingCaseInsight(true);
    setChatStatus('사건 정리를 생성하고 있습니다.');
    const insight = await generateCaseInsight(activeCase.id);
    setIsGeneratingCaseInsight(false);
    if (!insight) {
      setChatStatus('사건 정리를 생성하지 못했습니다.');
      return;
    }
    setCaseInsight(insight);
    const updatedCase = { ...activeCase, summary: insight.summary };
    setActiveCase(updatedCase);
    setCases((items) => items.map((item) => (item.id === updatedCase.id ? updatedCase : item)));
    setChatStatus(insight.is_ready ? 'AI 사건 정리를 생성했습니다.' : '기본 사건 정리를 생성했습니다. OpenAI 설정을 확인하면 더 정교하게 정리됩니다.');
  }

  async function handleUpdateCaseStatus(status: CaseStatus) {
    if (!activeCase) return;
    const updatedCase = await updateCaseStatus(activeCase.id, status);
    if (!updatedCase) {
      setChatStatus('사건 상태를 변경하지 못했습니다.');
      return;
    }
    setActiveCase(updatedCase);
    setCases((items) => items.map((item) => (item.id === updatedCase.id ? updatedCase : item)));
    await refreshCaseTimeline(updatedCase.id);
    setChatStatus(`사건 상태를 ${caseStatusLabel(updatedCase.status)} 상태로 변경했습니다.`);
  }

  function handleOpenEditCase(legalCase: LegalCase) {
    setEditingCase(legalCase);
    setEditCaseTitle(legalCase.title);
    setEditCaseSummary(legalCase.summary);
  }

  async function handleSaveEditCase(event: FormEvent) {
    event.preventDefault();
    if (!editingCase || !editCaseTitle.trim()) return;
    const updated = await updateCase(editingCase.id, {
      title: editCaseTitle.trim(),
      summary: editCaseSummary.trim(),
    });
    if (!updated) {
      setChatStatus('사건 정보를 수정하지 못했습니다.');
      return;
    }
    setCases((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    if (activeCase?.id === updated.id) setActiveCase(updated);
    setEditingCase(null);
    setChatStatus('사건 정보를 수정했습니다.');
  }

  async function handleConfirmDeleteCase() {
    if (deletingCaseId === null) return;
    const ok = await deleteCase(deletingCaseId);
    if (!ok) {
      setChatStatus('사건을 삭제하지 못했습니다.');
      setDeletingCaseId(null);
      return;
    }
    setCases((items) => items.filter((item) => item.id !== deletingCaseId));
    if (activeCase?.id === deletingCaseId) {
      setActiveCase(null);
      setCaseNotes([]);
      setCaseAttachments([]);
      setCaseTasks([]);
      setCaseTimeline([]);
      setCaseInsight(null);
    }
    setDeletingCaseId(null);
    setChatStatus('사건을 삭제했습니다.');
  }

  async function refreshCaseTimeline(caseId: number) {
    setIsTimelineLoading(true);
    setCaseTimeline(await fetchCaseTimeline(caseId));
    setIsTimelineLoading(false);
  }

  async function handleSelectCase(legalCase: LegalCase) {
    setActiveCase(legalCase);
    setCaseInsight(null);
    setEditingNoteId(null);
    setNoteTitle('');
    setNoteContent('');
    setFilterSessionsByCase(true);
    const [notes, attachments, tasks, timeline] = await Promise.all([
      fetchCaseNotes(legalCase.id),
      fetchCaseAttachments(legalCase.id),
      fetchCaseTasks(legalCase.id),
      fetchCaseTimeline(legalCase.id),
    ]);
    setCaseNotes(notes);
    setCaseAttachments(attachments);
    setCaseTasks(tasks);
    setCaseTimeline(timeline);
    setChatStatus('사건 노트를 불러왔습니다. 새 채팅은 선택된 사건에 연결됩니다.');
  }

  async function handleSelectUpcomingTask(task: UpcomingCaseTask) {
    const legalCase = cases.find((item) => item.id === task.case_id);
    if (legalCase) await handleSelectCase(legalCase);
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

  async function handleTogglePin(session: ChatSession) {
    const updatedSession = await updateChatSessionPin(session.id, !session.is_pinned);
    if (!updatedSession) {
      setChatStatus('대화방 고정 상태를 바꾸지 못했습니다.');
      return;
    }
    setSessions((items) =>
      [updatedSession, ...items.filter((item) => item.id !== updatedSession.id)].sort((a, b) => {
        if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      }),
    );
    if (activeSession?.id === updatedSession.id) {
      setActiveSession(updatedSession);
    }
    setChatStatus(updatedSession.is_pinned ? '대화방을 상단에 고정했습니다.' : '대화방 고정을 해제했습니다.');
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!caseTitle.trim()) return;
    const legalCase = await createCase(caseTitle.trim(), domainCode);
    if (!legalCase) {
      setChatStatus('사건 노트를 만들지 못했습니다.');
      return;
    }
    setCases((items) => [legalCase, ...items]);
    setActiveCase(legalCase);
    setCaseInsight(null);
    setEditingNoteId(null);
    setFilterSessionsByCase(true);
    setCaseNotes([]);
    setCaseAttachments([]);
    setCaseTasks([]);
    setCaseTimeline([
      {
        activity_type: 'case',
        entity_id: legalCase.id,
        session_id: null,
        title: '사건 생성',
        description: legalCase.title,
        occurred_at: legalCase.created_at,
      },
    ]);
    setCaseTitle('');
    setChatStatus('사건 노트를 만들었습니다. 새 채팅은 선택된 사건에 연결됩니다.');
  }

  async function handleCreateCaseNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCase || !noteContent.trim()) return;
    const note = editingNoteId
      ? await updateCaseNote(activeCase.id, editingNoteId, noteTitle.trim(), noteContent.trim())
      : await createCaseNote(activeCase.id, noteTitle.trim(), noteContent.trim());
    if (!note) {
      setChatStatus(editingNoteId ? '사건 메모를 수정하지 못했습니다.' : '사건 메모를 저장하지 못했습니다.');
      return;
    }
    setCaseNotes((items) => (editingNoteId ? items.map((item) => (item.id === note.id ? note : item)) : [...items, note]));
    const noteCountDelta = editingNoteId ? 0 : 1;
    setCases((items) =>
      items.map((item) =>
        item.id === activeCase.id
          ? { ...item, note_count: item.note_count + noteCountDelta, updated_at: note.updated_at }
          : item,
      ),
    );
    setActiveCase((item) =>
      item && item.id === activeCase.id
        ? { ...item, note_count: item.note_count + noteCountDelta, updated_at: note.updated_at }
        : item,
    );
    setNoteTitle('');
    setNoteContent('');
    setEditingNoteId(null);
    setCaseInsight(null);
    await refreshCaseTimeline(activeCase.id);
    setChatStatus(editingNoteId ? '사건 메모를 수정했습니다.' : '사건 메모를 저장했습니다.');
  }

  async function handleCreateCaseTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCase || !taskTitle.trim()) return;
    const task = await createCaseTask(activeCase.id, taskTitle.trim(), taskDueDate);
    if (!task) {
      setChatStatus('사건 할 일을 저장하지 못했습니다.');
      return;
    }
    setCaseTasks((items) => sortCaseTasks([...items, task]));
    setUpcomingTasks(await fetchUpcomingCaseTasks());
    await refreshCaseTimeline(activeCase.id);
    setTaskTitle('');
    setTaskDueDate('');
    setChatStatus('사건 할 일을 추가했습니다.');
  }

  async function handleToggleCaseTask(task: CaseTask) {
    if (!activeCase) return;
    const updated = await updateCaseTask(activeCase.id, { ...task, is_completed: !task.is_completed });
    if (!updated) {
      setChatStatus('사건 할 일 상태를 변경하지 못했습니다.');
      return;
    }
    setCaseTasks((items) => sortCaseTasks(items.map((item) => (item.id === updated.id ? updated : item))));
    setUpcomingTasks(await fetchUpcomingCaseTasks());
    await refreshCaseTimeline(activeCase.id);
    setChatStatus(updated.is_completed ? '사건 할 일을 완료 처리했습니다.' : '사건 할 일을 다시 진행 상태로 변경했습니다.');
  }

  async function handleDeleteCaseTask(task: CaseTask) {
    if (!activeCase) return;
    const deleted = await deleteCaseTask(activeCase.id, task.id);
    if (!deleted) {
      setChatStatus('사건 할 일을 삭제하지 못했습니다.');
      return;
    }
    setCaseTasks((items) => items.filter((item) => item.id !== task.id));
    setUpcomingTasks(await fetchUpcomingCaseTasks());
    await refreshCaseTimeline(activeCase.id);
    setChatStatus('사건 할 일을 삭제했습니다.');
  }

  function handleEditCaseNote(note: CaseNote) {
    setEditingNoteId(note.id);
    setNoteTitle(note.title);
    setNoteContent(note.content);
    setChatStatus('메모를 편집 중입니다.');
  }

  function handleCancelNoteEdit() {
    setEditingNoteId(null);
    setNoteTitle('');
    setNoteContent('');
    setChatStatus('메모 편집을 취소했습니다.');
  }

  async function handleDeleteCaseNote(note: CaseNote) {
    if (!activeCase) return;
    const deleted = await deleteCaseNote(activeCase.id, note.id);
    if (!deleted) {
      setChatStatus('사건 메모를 삭제하지 못했습니다.');
      return;
    }
    setCaseNotes((items) => items.filter((item) => item.id !== note.id));
    setCases((items) =>
      items.map((item) =>
        item.id === activeCase.id
          ? { ...item, note_count: Math.max(0, item.note_count - 1), updated_at: new Date().toISOString() }
          : item,
      ),
    );
    setActiveCase((item) =>
      item && item.id === activeCase.id
        ? { ...item, note_count: Math.max(0, item.note_count - 1), updated_at: new Date().toISOString() }
        : item,
    );
    if (editingNoteId === note.id) {
      setEditingNoteId(null);
      setNoteTitle('');
      setNoteContent('');
    }
    setCaseInsight(null);
    await refreshCaseTimeline(activeCase.id);
    setChatStatus('사건 메모를 삭제했습니다.');
  }

  function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function attachmentStatusLabel(status: string) {
    if (status === 'completed') return '텍스트 추출 완료';
    if (status === 'empty') return '추출 텍스트 없음';
    if (status === 'unsupported') return '텍스트 추출 미지원';
    if (status === 'failed') return '텍스트 추출 실패';
    return '추출 대기';
  }

  function vectorStatusLabel(status: string) {
    if (status === 'completed') return 'AI 색인 완료';
    if (status === 'skipped') return 'AI 색인 제외';
    if (status === 'failed') return 'AI 색인 실패';
    return 'AI 색인 대기';
  }

  async function handleUploadCaseAttachment(event: ChangeEvent<HTMLInputElement>) {
    if (!activeCase || !event.target.files?.[0]) return;
    const file = event.target.files[0];
    setIsUploadingAttachment(true);
    const attachment = await uploadCaseAttachment(activeCase.id, file);
    event.target.value = '';
    setIsUploadingAttachment(false);
    if (!attachment) {
      setChatStatus('첨부자료를 업로드하지 못했습니다.');
      return;
    }
    const now = attachment.created_at;
    setCaseAttachments((items) => [attachment, ...items]);
    setCases((items) => items.map((item) => (item.id === activeCase.id ? { ...item, updated_at: now } : item)));
    setActiveCase((item) => (item && item.id === activeCase.id ? { ...item, updated_at: now } : item));
    setCaseInsight(null);
    await refreshCaseTimeline(activeCase.id);
    setChatStatus('첨부자료를 추가했습니다.');
  }

  async function handleDeleteCaseAttachment(attachment: CaseAttachment) {
    if (!activeCase) return;
    const deleted = await deleteCaseAttachment(activeCase.id, attachment.id);
    if (!deleted) {
      setChatStatus('첨부자료를 삭제하지 못했습니다.');
      return;
    }
    setCaseAttachments((items) => items.filter((item) => item.id !== attachment.id));
    setCaseInsight(null);
    await refreshCaseTimeline(activeCase.id);
    setChatStatus('첨부자료를 삭제했습니다.');
  }

  async function handleDownloadCaseAttachment(caseId: number, attachmentId: number, filename: string) {
    const downloaded = await downloadCaseAttachment(caseId, attachmentId, filename);
    setChatStatus(downloaded ? '첨부자료 다운로드를 시작했습니다.' : '첨부자료를 다운로드하지 못했습니다.');
  }

  async function handleIndexCaseAttachment(attachment: CaseAttachment) {
    if (!activeCase || indexingAttachmentId !== null) return;
    setIndexingAttachmentId(attachment.id);
    const indexed = await indexCaseAttachment(activeCase.id, attachment.id);
    setIndexingAttachmentId(null);
    if (!indexed) {
      setChatStatus('첨부자료 AI 색인을 완료하지 못했습니다.');
      return;
    }
    setCaseAttachments((items) => items.map((item) => (item.id === indexed.id ? indexed : item)));
    setChatStatus(indexed.vector_status === 'completed' ? '첨부자료 AI 색인을 완료했습니다.' : '첨부자료 AI 색인이 대기 상태입니다.');
  }

  async function handleRegenerate() {
    if (!activeSession || isLoading) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;

    setIsLoading(true);
    setChatStatus('답변을 재생성하는 중입니다.');
    const turn = await sendChatMessage(activeSession.id, lastUserMsg.content, answerMode);
    if (!turn) {
      setChatStatus('재생성에 실패했습니다. 백엔드 서버 상태를 확인해주세요.');
      setIsLoading(false);
      return;
    }
    setMessages((items) => [...items, turn.user_message, turn.assistant_message]);
    setActiveSession(turn.session);
    setSessions((items) => [turn.session, ...items.filter((item) => item.id !== turn.session.id)]);
    setChatStatus('답변을 재생성했습니다.');
    setIsLoading(false);
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }

    let session = activeSession;
    if (!session) {
      session = await createChatSession(message.trim().slice(0, 40), domainCode, activeCase?.id);
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
      answer_mode: answerMode,
      evidence_status: null,
      evidence_warnings: [],
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessage('');
    setMessages((items) => [...items, optimisticUserMessage]);
    setIsLoading(true);
    setChatStatus('검색 근거를 찾고 답변을 생성하는 중입니다.');

    const turn = await sendChatMessage(session.id, content, answerMode);
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
    if (turn.session.case_id) await refreshCaseTimeline(turn.session.case_id);
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
            <>
            {!deadlineAlertDismissed && (() => {
              const overdueCount = upcomingTasks.filter(isTaskOverdue).length;
              const todayCount = upcomingTasks.filter(isTaskDueToday).length;
              if (overdueCount === 0 && todayCount === 0) return null;
              const parts = [];
              if (overdueCount > 0) parts.push(`기한 초과 ${overdueCount}건`);
              if (todayCount > 0) parts.push(`오늘 마감 ${todayCount}건`);
              return (
                <div className="deadline-alert" role="alert">
                  <span>⚠️ {parts.join(' · ')}</span>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="알림 닫기"
                    onClick={() => setDeadlineAlertDismissed(true)}
                  >✕</button>
                </div>
              );
            })()}
            <section className="workspace-search-panel">
              <form className="workspace-search-form" onSubmit={handleWorkspaceSearch}>
                <label htmlFor="workspace-search">통합 검색</label>
                <div>
                  <input
                    id="workspace-search"
                    type="search"
                    value={workspaceSearch}
                    onChange={(event) => setWorkspaceSearch(event.target.value)}
                    placeholder="사건, 메모, 채팅, 첨부자료"
                  />
                  <button type="submit" disabled={isWorkspaceSearching || workspaceSearch.trim().length < 2}>
                    {isWorkspaceSearching ? '검색 중' : '검색'}
                  </button>
                </div>
              </form>
              {(workspaceSearchResults.length > 0 || workspaceSearchTotalCount > 0) && (
                <div className="workspace-search-results" aria-label="통합 검색 결과">
                  <div className="search-filter-chips" role="group" aria-label="유형 필터">
                    {SEARCH_TYPE_FILTERS.map(({ value, label }) => (
                      <button
                        key={value}
                        type="button"
                        className={searchTypeFilter === value ? 'search-chip active' : 'search-chip'}
                        onClick={() => handleSearchTypeChange(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <p className="search-count">
                    총 {workspaceSearchTotalCount}건
                    {workspaceSearchTotalCount > searchVisibleCount && ` (${searchVisibleCount}건 표시 중)`}
                  </p>
                  {workspaceSearchResults.slice(0, searchVisibleCount).map((result) => (
                    <button
                      type="button"
                      key={`${result.result_type}-${result.id}`}
                      onClick={() => handleSelectSearchResult(result)}
                    >
                      <span>{searchResultTypeLabel(result.result_type)}</span>
                      <strong>{highlightQuery(result.title, workspaceSearch)}</strong>
                      <p>{highlightQuery(result.snippet, workspaceSearch)}</p>
                    </button>
                  ))}
                  {searchVisibleCount < workspaceSearchResults.length && (
                    <button
                      type="button"
                      className="search-load-more"
                      onClick={() => setSearchVisibleCount((n) => n + SEARCH_PAGE_SIZE)}
                    >
                      더 보기 ({workspaceSearchResults.length - searchVisibleCount}건 남음)
                    </button>
                  )}
                  {workspaceSearchResults.length === 0 && (
                    <p className="empty-state">검색 결과가 없습니다.</p>
                  )}
                </div>
              )}
            </section>
            <section className="case-panel">
              <div className="section-heading">
                <h2>사건 노트</h2>
                <button type="button" className="secondary-button" onClick={() => {
                  setActiveCase(null);
                  setCaseNotes([]);
                  setCaseAttachments([]);
                  setCaseTasks([]);
                  setCaseInsight(null);
                  setFilterSessionsByCase(true);
                }}>
                  선택 해제
                </button>
              </div>
              {(() => {
                const overdueTasks = upcomingTasks.filter(isTaskOverdue);
                const todayTasks = upcomingTasks.filter(isTaskDueToday);
                const imminentTasks = upcomingTasks.filter(isTaskImminent);
                const laterTasks = upcomingTasks.filter(
                  (t) => !isTaskOverdue(t) && !isTaskDueToday(t) && !isTaskImminent(t),
                );
                const urgentCount = overdueTasks.length + todayTasks.length;
                return (
                  <section className="deadline-dashboard">
                    <div className="deadline-dashboard-heading">
                      <h3>기한 알림 센터</h3>
                      {urgentCount > 0 && (
                        <span className="deadline-urgent-badge">{urgentCount}</span>
                      )}
                    </div>
                    {upcomingTasks.length === 0 ? (
                      <p className="empty-state">30일 이내 예정된 기한이 없습니다.</p>
                    ) : (
                      <div className="deadline-groups">
                        {overdueTasks.length > 0 && (
                          <div className="deadline-group">
                            <div className="deadline-group-label overdue">기한 초과 {overdueTasks.length}건</div>
                            {overdueTasks.map((task) => (
                              <button
                                type="button"
                                className="deadline-item overdue"
                                key={task.id}
                                onClick={() => handleSelectUpcomingTask(task)}
                              >
                                <strong>{task.title}</strong>
                                <span>{task.case_title}</span>
                                <time>{task.due_date}</time>
                              </button>
                            ))}
                          </div>
                        )}
                        {todayTasks.length > 0 && (
                          <div className="deadline-group">
                            <div className="deadline-group-label today">오늘 마감 {todayTasks.length}건</div>
                            {todayTasks.map((task) => (
                              <button
                                type="button"
                                className="deadline-item today"
                                key={task.id}
                                onClick={() => handleSelectUpcomingTask(task)}
                              >
                                <strong>{task.title}</strong>
                                <span>{task.case_title}</span>
                                <time>오늘</time>
                              </button>
                            ))}
                          </div>
                        )}
                        {imminentTasks.length > 0 && (
                          <div className="deadline-group">
                            <div className="deadline-group-label imminent">7일 이내 {imminentTasks.length}건</div>
                            {imminentTasks.map((task) => (
                              <button
                                type="button"
                                className="deadline-item imminent"
                                key={task.id}
                                onClick={() => handleSelectUpcomingTask(task)}
                              >
                                <strong>{task.title}</strong>
                                <span>{task.case_title}</span>
                                <time>{task.due_date}</time>
                              </button>
                            ))}
                          </div>
                        )}
                        {laterTasks.length > 0 && (
                          <div className="deadline-group">
                            <div className="deadline-group-label later">이후 예정 {laterTasks.length}건</div>
                            {laterTasks.map((task) => (
                              <button
                                type="button"
                                className="deadline-item"
                                key={task.id}
                                onClick={() => handleSelectUpcomingTask(task)}
                              >
                                <strong>{task.title}</strong>
                                <span>{task.case_title}</span>
                                <time>{task.due_date}</time>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </section>
                );
              })()}
              <form className="case-form" onSubmit={handleCreateCase}>
                <label htmlFor="case-title">새 사건</label>
                <input
                  id="case-title"
                  value={caseTitle}
                  onChange={(event) => setCaseTitle(event.target.value)}
                  placeholder="예: 임대차 보증금 반환"
                />
                <button type="submit">사건 만들기</button>
              </form>
              {cases.length > 0 && (
                <div className="case-filter-panel">
                  <label className="case-search" htmlFor="case-search">
                    <span>사건 검색</span>
                    <input
                      id="case-search"
                      type="search"
                      value={caseSearch}
                      onChange={(event) => setCaseSearch(event.target.value)}
                      placeholder="사건명, 분야, 상태"
                    />
                  </label>
                  <label className="case-status-filter" htmlFor="case-status-filter">
                    <span>상태 필터</span>
                    <select
                      id="case-status-filter"
                      value={caseStatusFilter}
                      onChange={(event) => setCaseStatusFilter(event.target.value as 'all' | CaseStatus)}
                    >
                      <option value="all">전체 상태</option>
                      {caseStatusOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="case-filter-toggle">
                    <input
                      type="checkbox"
                      checked={hideClosedCases}
                      onChange={(event) => setHideClosedCases(event.target.checked)}
                      disabled={caseStatusFilter === 'closed'}
                    />
                    <span>종료 사건 숨기기</span>
                  </label>
                </div>
              )}
              {cases.length > 0 ? (
                <div className="case-list">
                  {filteredCases.map((legalCase) => (
                    <div
                      className={activeCase?.id === legalCase.id ? 'case-item active-case' : 'case-item'}
                      key={legalCase.id}
                    >
                      <button
                        type="button"
                        className="case-item-body"
                        onClick={() => handleSelectCase(legalCase)}
                      >
                        <span>{legalCase.title}</span>
                        <small>
                          {caseStatusLabel(legalCase.status)} · {domainLabel(legalCase.domain_code)} · 채팅 {legalCase.chat_count}개 · 메모 {legalCase.note_count}개
                        </small>
                      </button>
                      <div className="case-item-actions">
                        <button
                          type="button"
                          className="icon-button"
                          title="사건 수정"
                          onClick={(e) => { e.stopPropagation(); handleOpenEditCase(legalCase); }}
                        >✏️</button>
                        <button
                          type="button"
                          className="icon-button danger"
                          title="사건 삭제"
                          onClick={(e) => { e.stopPropagation(); setDeletingCaseId(legalCase.id); }}
                        >🗑️</button>
                      </div>
                    </div>
                  ))}
                  {filteredCases.length === 0 && (
                    <p className="empty-state">조건에 맞는 사건이 없습니다.</p>
                  )}
                </div>
              ) : (
                <p className="empty-state">아직 사건 노트가 없습니다.</p>
              )}
              {activeCase && (
                <section className="case-detail">
                  <div className="case-detail-heading">
                    <h3>{activeCase.title}</h3>
                    <div className="case-detail-actions">
                      <button type="button" className="secondary-button" onClick={handleGenerateCaseInsight} disabled={isGeneratingCaseInsight}>
                        {isGeneratingCaseInsight ? '정리 중' : 'AI 사건 정리'}
                      </button>
                      <button type="button" className="secondary-button" onClick={handleStartCaseChat}>
                        이 사건 새 대화
                      </button>
                    </div>
                  </div>
                  <dl className="case-overview">
                    <div>
                      <dt>분야</dt>
                      <dd>{domainLabel(activeCase.domain_code)}</dd>
                    </div>
                    <div>
                      <dt>상태</dt>
                      <dd>
                        <select
                          className="case-status-select"
                          aria-label="사건 상태"
                          value={activeCase.status}
                          onChange={(event) => handleUpdateCaseStatus(event.target.value as CaseStatus)}
                        >
                          {caseStatusOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </dd>
                    </div>
                    <div>
                      <dt>연결 대화</dt>
                      <dd>{activeCaseSessions.length}개</dd>
                    </div>
                    <div>
                      <dt>메모</dt>
                      <dd>{caseNotes.length}개</dd>
                    </div>
                    <div>
                      <dt>할 일</dt>
                      <dd>{caseTasks.filter((task) => !task.is_completed).length}개 진행중</dd>
                    </div>
                    <div className="case-overview-wide">
                      <dt>최근 활동</dt>
                      <dd>{activeCaseActivityAt ? new Date(activeCaseActivityAt).toLocaleString('ko-KR') : '-'}</dd>
                    </div>
                  </dl>
                  {activeCase.summary && <p className="case-summary">{activeCase.summary}</p>}
                  <section className="case-timeline">
                    <div className="case-timeline-heading">
                      <h4>최근 활동</h4>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => refreshCaseTimeline(activeCase.id)}
                        disabled={isTimelineLoading}
                      >
                        {isTimelineLoading ? '불러오는 중' : '새로고침'}
                      </button>
                    </div>
                    {caseTimeline.length > 0 ? (
                      <div className="case-timeline-list">
                        {caseTimeline.slice(0, 12).map((item) => (
                          <button
                            type="button"
                            key={`${item.activity_type}-${item.entity_id}`}
                            onClick={() => handleSelectTimelineItem(item)}
                            disabled={!item.session_id}
                          >
                            <span>{timelineTypeLabel(item.activity_type)}</span>
                            <strong>{item.title}</strong>
                            <p>{item.description}</p>
                            <time>{new Date(item.occurred_at).toLocaleString('ko-KR')}</time>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">아직 기록된 활동이 없습니다.</p>
                    )}
                  </section>
                  {caseInsight && (
                    <section className="case-insight">
                      <h4>AI 사건 정리</h4>
                      <p>{caseInsight.summary}</p>
                      <div className="case-insight-grid">
                        <div>
                          <strong>핵심 쟁점</strong>
                          <ul>
                            {caseInsight.issues.map((issue) => (
                              <li key={issue}>{issue}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <strong>다음 할 일</strong>
                          <ul>
                            {caseInsight.next_actions.map((action) => (
                              <li key={action}>{action}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                      {caseInsight.cautions.length > 0 && (
                        <small>{caseInsight.cautions.join(' ')}</small>
                      )}
                    </section>
                  )}
                  <section className="case-linked-sessions">
                    <h4>연결 대화</h4>
                    {activeCaseSessions.length > 0 ? (
                      <div className="case-linked-session-list">
                        {activeCaseSessions.slice(0, 3).map((session) => (
                          <button type="button" key={session.id} onClick={() => handleSelectSession(session)}>
                            <span>{session.title}</span>
                            <small>{new Date(session.updated_at).toLocaleString('ko-KR')}</small>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">이 사건에 연결된 대화가 없습니다.</p>
                    )}
                  </section>
                  <section className="case-tasks">
                    <div className="case-task-heading">
                      <h4>할 일과 기한</h4>
                      <span>{caseTasks.filter((task) => !task.is_completed).length}개 남음</span>
                    </div>
                    <form className="case-task-form" onSubmit={handleCreateCaseTask}>
                      <label htmlFor="case-task-title">할 일</label>
                      <input
                        id="case-task-title"
                        value={taskTitle}
                        onChange={(event) => setTaskTitle(event.target.value)}
                        placeholder="예: 내용증명 발송"
                      />
                      <label htmlFor="case-task-due-date">기한</label>
                      <input
                        id="case-task-due-date"
                        type="date"
                        value={taskDueDate}
                        onChange={(event) => setTaskDueDate(event.target.value)}
                      />
                      <button type="submit">추가</button>
                    </form>
                    {caseTasks.length > 0 ? (
                      <div className="case-task-list">
                        {caseTasks.map((task) => (
                          <article
                            className={`case-task-item${task.is_completed ? ' completed' : ''}${isTaskOverdue(task) ? ' overdue' : ''}`}
                            key={task.id}
                          >
                            <label>
                              <input
                                type="checkbox"
                                checked={task.is_completed}
                                onChange={() => handleToggleCaseTask(task)}
                              />
                              <span>{task.title}</span>
                            </label>
                            <small>
                              {task.due_date ? `기한 ${task.due_date}` : '기한 없음'}
                              {isTaskOverdue(task) ? ' · 기한 초과' : ''}
                            </small>
                            <button
                              type="button"
                              className="danger-button"
                              aria-label={`${task.title} 할 일 삭제`}
                              onClick={() => handleDeleteCaseTask(task)}
                            >
                              삭제
                            </button>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">등록된 할 일이 없습니다.</p>
                    )}
                  </section>
                  <section className="case-attachments">
                    <div className="case-attachment-heading">
                      <h4>첨부자료</h4>
                      <label className="case-attachment-upload">
                        <input
                          type="file"
                          aria-label="첨부 파일"
                          onChange={handleUploadCaseAttachment}
                          disabled={isUploadingAttachment}
                        />
                        <span>{isUploadingAttachment ? '업로드 중' : '파일 추가'}</span>
                      </label>
                    </div>
                    {caseAttachments.length > 0 ? (
                      <div className="case-attachment-list">
                        {caseAttachments.map((attachment) => (
                          <article className="case-attachment-item" key={attachment.id}>
                            <div>
                              <strong>{attachment.original_filename}</strong>
                              <small>
                                {formatFileSize(attachment.size_bytes)} · {attachment.content_type ?? '파일'} ·{' '}
                                {attachmentStatusLabel(attachment.extraction_status)} 쨌 {attachment.extracted_text_chars}자 쨌{' '}
                                {vectorStatusLabel(attachment.vector_status)} · {attachment.vector_chunk_count}청크 ·{' '}
                                {new Date(attachment.created_at).toLocaleString('ko-KR')}
                              </small>
                            </div>
                            <div className="case-attachment-actions">
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => handleDownloadCaseAttachment(activeCase.id, attachment.id, attachment.original_filename)}
                              >
                                다운로드
                              </button>
                              {attachment.extraction_status === 'completed' && attachment.vector_status !== 'completed' && (
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() => handleIndexCaseAttachment(attachment)}
                                  disabled={indexingAttachmentId !== null}
                                >
                                  {indexingAttachmentId === attachment.id ? '색인 중' : '색인 재시도'}
                                </button>
                              )}
                              <button
                                type="button"
                                className="danger-button"
                                aria-label={`${attachment.original_filename} 첨부 삭제`}
                                onClick={() => handleDeleteCaseAttachment(attachment)}
                              >
                                삭제
                              </button>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">이 사건에 첨부된 자료가 없습니다.</p>
                    )}
                  </section>
                  {recentCaseNote && (
                    <section className="case-recent-note">
                      <h4>최근 메모</h4>
                      <strong>{recentCaseNote.title}</strong>
                      <p>{recentCaseNote.content}</p>
                    </section>
                  )}
                  <form className="case-note-form" onSubmit={handleCreateCaseNote}>
                    <label htmlFor="note-title">메모 제목</label>
                    <input
                      id="note-title"
                      value={noteTitle}
                      onChange={(event) => setNoteTitle(event.target.value)}
                      placeholder="예: 사실관계"
                    />
                    <label htmlFor="note-content">메모 내용</label>
                    <textarea
                      id="note-content"
                      value={noteContent}
                      onChange={(event) => setNoteContent(event.target.value)}
                      placeholder="사실관계, 쟁점, 확인할 자료를 적어두세요."
                      rows={4}
                    />
                    <div className="case-note-form-actions">
                      <button type="submit">{editingNoteId ? '메모 수정' : '메모 저장'}</button>
                      {editingNoteId && (
                        <button type="button" className="secondary-button" onClick={handleCancelNoteEdit}>
                          취소
                        </button>
                      )}
                    </div>
                  </form>
                  {caseNotes.length > 0 ? (
                    <div className="case-note-list">
                      {caseNotes.map((note) => (
                        <article className="case-note-item" key={note.id}>
                          <strong>{note.title}</strong>
                          <p>{note.content}</p>
                          <time>{new Date(note.updated_at).toLocaleString('ko-KR')}</time>
                          <div className="case-note-actions">
                            <button type="button" className="secondary-button" onClick={() => handleEditCaseNote(note)}>
                              수정
                            </button>
                            <button type="button" className="danger-button" onClick={() => handleDeleteCaseNote(note)}>
                              삭제
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-state">이 사건에 저장된 메모가 없습니다.</p>
                  )}
                </section>
              )}
            </section>

            <section className="session-panel">
              <div className="section-heading">
                <h2>대화 목록</h2>
                <button type="button" className="secondary-button" onClick={handleCreateSession}>
                  새 대화
                </button>
              </div>
              <label className="session-search" htmlFor="session-search">
                <span>대화 검색</span>
                <input
                  id="session-search"
                  type="search"
                  value={sessionSearch}
                  onChange={(event) => setSessionSearch(event.target.value)}
                  placeholder="제목, 분야, 최근 메시지"
                />
              </label>
              {activeCase && (
                <label className="case-filter-toggle">
                  <input
                    type="checkbox"
                    checked={filterSessionsByCase}
                    onChange={(event) => setFilterSessionsByCase(event.target.checked)}
                  />
                  <span>선택한 사건 대화만 보기</span>
                </label>
              )}
              {sessions.length > 0 ? (
                <div className="session-list">
                  {filteredSessions.map((session) => (
                    <article className="session-item" key={session.id}>
                      <button
                        type="button"
                        className={activeSession?.id === session.id ? 'session-open-button active-session' : 'session-open-button'}
                        onClick={() => handleSelectSession(session)}
                      >
                        <span>{session.is_pinned ? `고정 · ${session.title}` : session.title}</span>
                        <b>{domainLabel(session.domain_code)}</b>
                        {session.case_id && (
                          <b className="case-link-badge">{caseTitleForSession(session.case_id) ?? '연결된 사건'}</b>
                        )}
                        <small>
                          메시지 {session.message_count}개
                          {session.last_message_preview ? ` · ${session.last_message_preview}` : ''}
                        </small>
                        <time>{new Date(session.updated_at).toLocaleString('ko-KR')}</time>
                      </button>
                      <button type="button" className="session-pin-button" onClick={() => handleTogglePin(session)}>
                        {session.is_pinned ? '고정 해제' : '고정'}
                      </button>
                      <button type="button" className="session-delete-button" onClick={() => handleDeleteSession(session)}>
                        삭제
                      </button>
                    </article>
                  ))}
                  {filteredSessions.length === 0 && (
                    <p className="empty-state">
                      {activeCase && filterSessionsByCase ? '선택한 사건에 연결된 대화가 없습니다.' : '검색 조건에 맞는 대화가 없습니다.'}
                    </p>
                  )}
                </div>
              ) : (
                <p className="empty-state">아직 저장된 대화가 없습니다.</p>
              )}
            </section>
            </>
          )}
        </aside>

        <section className="chat-panel" aria-label="챗봇">
          <header className="chat-header">
            <div>
              <h2>{activeSession?.title ?? '새 채팅'}</h2>
              <p>
                {activeSession
                  ? `${domainLabel(activeSession.domain_code)} 대화 · ${chatStatus}`
                  : `${activeCase ? `${activeCase.title} 사건에 연결 · ` : ''}${chatStatus}`}
              </p>
            </div>
            <div className="chat-controls">
              <div className="domain-control">
                <label htmlFor="domain">법 분야</label>
                <select
                  id="domain"
                  value={activeSession?.domain_code ?? domainCode}
                  onChange={(event) => setDomainCode(event.target.value)}
                  disabled={Boolean(activeSession)}
                >
                  {domainOptions.map((option) => (
                    <option key={option.value || 'all'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="domain-control">
                <label htmlFor="answer-mode">답변 모드</label>
                <select
                  id="answer-mode"
                  value={answerMode}
                  onChange={(event) => setAnswerMode(event.target.value)}
                >
                  {answerModeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </header>

          <div className="message-list" aria-live="polite">
            {messages.length > 0 ? (
              messages.map((item, index) => {
                const isLastAssistant =
                  item.role === 'assistant' &&
                  index === messages.map((m, i) => (m.role === 'assistant' ? i : -1)).filter((i) => i >= 0).at(-1);
                return (
                <article className={`message-bubble ${item.role}`} key={item.id}>
                  <span>{item.role === 'user' ? '사용자' : 'AI'}</span>
                  {item.role === 'assistant' && item.answer_mode && (
                    <b className="answer-mode-badge">{answerModeLabel(item.answer_mode)}</b>
                  )}
                  {item.role === 'assistant' && evidenceStatusLabel(item.evidence_status) && (
                    <b className={`evidence-status-badge ${item.evidence_status}`}>
                      {evidenceStatusLabel(item.evidence_status)}
                    </b>
                  )}
                  <p>{item.content}</p>
                  {item.evidence_warnings && item.evidence_warnings.length > 0 && (
                    <details className="evidence-warning-details">
                      <summary>근거 품질 경고 {item.evidence_warnings.length}개</summary>
                      <ul>
                        {item.evidence_warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {item.sources.length > 0 && (
                    <details>
                      <summary>검색 근거 {item.sources.length}개</summary>
                      <div className="sources-list">
                        {item.sources.map((source, index) => {
                          const sourceKey = `${item.id}-${source.id}`;
                          const isExpanded = expandedSources.has(sourceKey);
                          const isLong = source.text.length > 200;
                          const sourceEvidenceLabel = evidenceLabel(source);
                          const sourceCaseNumber = caseNumber(source);
                          const sourceAttachment = attachmentReference(source);
                          return (
                            <section className="source-item" key={sourceKey}>
                              <div className="source-meta">
                                <span className={evidenceBadgeClass(source)}>
                                  {sourceEvidenceLabel} 근거 {index + 1}
                                </span>
                                <span>{source.domain_name ?? '분야 미상'}</span>
                                {sourceCaseNumber && <span>{sourceCaseNumber}</span>}
                                {source.score !== null && source.score !== undefined && (
                                  <span>유사도 {(1 - source.score).toFixed(3)}</span>
                                )}
                              </div>
                              <h3>{source.title ?? '제목 없음'}</h3>
                              <p className={isExpanded ? 'expanded' : ''}>{source.text}</p>
                              {sourceAttachment && (
                                <button
                                  type="button"
                                  className="source-download-btn"
                                  onClick={() => handleDownloadCaseAttachment(
                                    sourceAttachment.caseId,
                                    sourceAttachment.attachmentId,
                                    sourceAttachment.filename,
                                  )}
                                >
                                  원본 다운로드
                                </button>
                              )}
                              {isLong && (
                                <button
                                  type="button"
                                  className="source-expand-btn"
                                  onClick={() => toggleSource(sourceKey)}
                                >
                                  {isExpanded ? '접기' : '더보기'}
                                </button>
                              )}
                            </section>
                          );
                        })}
                      </div>
                    </details>
                  )}
                  {isLastAssistant && !isLoading && (
                    <button type="button" className="regenerate-btn" onClick={handleRegenerate}>
                      ↺ 재생성
                    </button>
                  )}
                </article>
                );
              })
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

      {editingCase && (
        <div className="modal-overlay" onClick={() => setEditingCase(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSaveEditCase}>
            <h3>사건 수정</h3>
            <label className="modal-label">
              제목
              <input
                value={editCaseTitle}
                onChange={(e) => setEditCaseTitle(e.target.value)}
                maxLength={255}
                required
              />
            </label>
            <label className="modal-label">
              요약
              <textarea
                value={editCaseSummary}
                onChange={(e) => setEditCaseSummary(e.target.value)}
                rows={4}
              />
            </label>
            <div className="modal-actions">
              <button type="submit">저장</button>
              <button type="button" className="secondary-button" onClick={() => setEditingCase(null)}>취소</button>
            </div>
          </form>
        </div>
      )}

      {deletingCaseId !== null && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>사건 삭제</h3>
            <p>사건과 모든 메모, 할 일, 첨부자료가 영구 삭제됩니다. 계속하시겠습니까?</p>
            <div className="modal-actions">
              <button className="danger-button" onClick={handleConfirmDeleteCase}>삭제</button>
              <button className="secondary-button" onClick={() => setDeletingCaseId(null)}>취소</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
