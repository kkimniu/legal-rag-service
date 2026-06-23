import axios from 'axios';

const TOKEN_STORAGE_KEY = 'legal-rag-access-token';
const REFRESH_TOKEN_STORAGE_KEY = 'legal-rag-refresh-token';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export type User = {
  id: number;
  email: string;
  is_active: boolean;
  is_guest?: boolean;
};

export type AuthResult = {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  message: string;
};

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
}

function storeToken(token: string) {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function getStoredRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
}

function storeRefreshToken(token: string) {
  window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
}

function storeTokens(accessToken: string, refreshToken?: string | null) {
  storeToken(accessToken);
  if (refreshToken) {
    storeRefreshToken(refreshToken);
  }
}

export async function register(email: string, password: string): Promise<AuthResult> {
  try {
    await api.post<User>('/auth/register', { email, password });
    const loginResult = await login(email, password);
    if (loginResult.user) {
      return {
        ...loginResult,
        message: '회원가입 후 로그인되었습니다.',
      };
    }
    return loginResult;
  } catch {
    return {
      user: null,
      token: null,
      refreshToken: null,
      message: '회원가입에 실패했습니다. 이미 가입된 이메일이거나 DB 상태를 확인해주세요.',
    };
  }
}

export async function login(email: string, password: string): Promise<AuthResult> {
  try {
    const body = new URLSearchParams();
    body.set('username', email);
    body.set('password', password);

    const tokenResponse = await api.post<{ access_token: string; refresh_token?: string | null; token_type: string }>('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    storeTokens(tokenResponse.data.access_token, tokenResponse.data.refresh_token);

    const userResponse = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${tokenResponse.data.access_token}` },
    });

    return {
      user: userResponse.data,
      token: tokenResponse.data.access_token,
      refreshToken: tokenResponse.data.refresh_token ?? null,
      message: '로그인되었습니다.',
    };
  } catch {
    return {
      user: null,
      token: null,
      refreshToken: null,
      message: '로그인에 실패했습니다. 이메일, 비밀번호, DB 상태를 확인해주세요.',
    };
  }
}

export async function loginAsGuest(): Promise<AuthResult> {
  try {
    const tokenResponse = await api.post<{ access_token: string; token_type: string }>('/auth/guest');
    storeToken(tokenResponse.data.access_token);

    const userResponse = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${tokenResponse.data.access_token}` },
    });

    return {
      user: userResponse.data,
      token: tokenResponse.data.access_token,
      refreshToken: null,
      message: '게스트로 시작합니다. 대화 내용은 세션 종료 시 삭제됩니다.',
    };
  } catch {
    return {
      user: null,
      token: null,
      refreshToken: null,
      message: '게스트 로그인에 실패했습니다.',
    };
  }
}

export async function fetchCurrentUser(): Promise<User | null> {
  let token = getStoredToken();
  if (!token) {
    token = await refreshAccessToken();
    if (!token) {
      return null;
    }
  }

  try {
    const response = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  } catch {
    const refreshedToken = await refreshAccessToken();
    if (!refreshedToken) {
      clearStoredToken();
      return null;
    }
    try {
      const response = await api.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${refreshedToken}` },
      });
      return response.data;
    } catch {
      clearStoredToken();
      return null;
    }
  }
}

export async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await api.post<{ access_token: string; refresh_token?: string | null; token_type: string }>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    storeTokens(response.data.access_token, response.data.refresh_token);
    return response.data.access_token;
  } catch {
    clearStoredToken();
    return null;
  }
}

export async function getAuthHeaders(): Promise<{ Authorization: string } | undefined> {
  const token = getStoredToken() ?? (await refreshAccessToken());
  return token ? { Authorization: `Bearer ${token}` } : undefined;
}
