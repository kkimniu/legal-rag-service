import axios from 'axios';

const TOKEN_STORAGE_KEY = 'legal-rag-access-token';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
});

export type User = {
  id: number;
  email: string;
  is_active: boolean;
};

export type AuthResult = {
  user: User | null;
  token: string | null;
  message: string;
};

export function getStoredToken(): string | null {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function storeToken(token: string) {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export async function register(email: string, password: string): Promise<AuthResult> {
  try {
    const response = await api.post<User>('/auth/register', { email, password });
    return {
      user: response.data,
      token: null,
      message: '회원가입이 완료되었습니다. 로그인해주세요.',
    };
  } catch {
    return {
      user: null,
      token: null,
      message: '회원가입에 실패했습니다. 이미 가입된 이메일이거나 DB가 준비되지 않았을 수 있습니다.',
    };
  }
}

export async function login(email: string, password: string): Promise<AuthResult> {
  try {
    const body = new URLSearchParams();
    body.set('username', email);
    body.set('password', password);

    const tokenResponse = await api.post<{ access_token: string; token_type: string }>('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    storeToken(tokenResponse.data.access_token);

    const userResponse = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${tokenResponse.data.access_token}` },
    });

    return {
      user: userResponse.data,
      token: tokenResponse.data.access_token,
      message: '로그인되었습니다.',
    };
  } catch {
    return {
      user: null,
      token: null,
      message: '로그인에 실패했습니다. 이메일, 비밀번호, DB 상태를 확인해주세요.',
    };
  }
}

export async function fetchCurrentUser(): Promise<User | null> {
  const token = getStoredToken();
  if (!token) {
    return null;
  }

  try {
    const response = await api.get<User>('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  } catch {
    clearStoredToken();
    return null;
  }
}
