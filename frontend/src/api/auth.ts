/** 认证 API 服务层 — 登录/注册/身份切换 */

import { API_BASE } from './client';

function jsonHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json' };
}

export interface LoginRequest {
  email: string;
  password: string;
  role: 'patient' | 'doctor' | 'admin';
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in?: number;
  user: {
    id: string;
    email: string;
    role: string;
    name?: string;
  };
  password_change_required?: boolean;
}

export interface RegisterRequest {
  email: string;
  password: string;
  role: 'patient' | 'doctor';
  full_name: string;
  phone?: string;
}

export interface UserInfo {
  id: string;
  email: string;
  role: string;
  name?: string;
  full_name?: string;
  phone?: string;
  is_verified?: boolean;
  avatar_url?: string;
  license_number?: string;
  hospital?: string;
  department?: string;
  title?: string;
}

/** 存储 token 到 sessionStorage（关闭 tab 即清除，减少持久化攻击面） */
function storeTokens(accessToken: string, role: string): void {
  sessionStorage.setItem('access_token', accessToken);
  localStorage.setItem('user_role', role);
}

/** 清除所有存储的 token */
function clearTokens(): void {
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('refresh_token');
  localStorage.removeItem('user_role');
  localStorage.removeItem('access_token');      // 兼容旧版
  localStorage.removeItem('guest_token');
  localStorage.removeItem('guest_status');
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      username: data.email,
      password: data.password,
    }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || json.message || 'Login failed');
  // 生产环境：httpOnly cookie 已在后端 set-cookie
  // sessionStorage 作为开发环境跨域 fallback
  storeTokens(json.access_token, json.user?.role || data.role);
  if (json.refresh_token) {
    sessionStorage.setItem('refresh_token', json.refresh_token);
  }
  return json;
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || json.message || 'Register failed');
  storeTokens(json.access_token, data.role);
  if (json.refresh_token) {
    sessionStorage.setItem('refresh_token', json.refresh_token);
  }
  return json;
}

export async function getMe(): Promise<UserInfo> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to get user info');
  return json;
}

export async function logout(): Promise<void> {
  const token = getToken();
  if (token) {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // 即使后端不可用，也要清理本地状态
    }
  }
  clearTokens();
}

export function getToken(): string | null {
  return sessionStorage.getItem('access_token');
}

/** 获取 refresh_token（开发环境跨域 fallback） */
export function getRefreshToken(): string | null {
  return sessionStorage.getItem('refresh_token');
}

export function getUserRole(): string | null {
  return localStorage.getItem('user_role');
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

/** 更新当前用户信息（full_name, phone） */
export async function updateMe(data: { full_name?: string; phone?: string }): Promise<UserInfo> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/auth/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || 'Failed to update profile');
  return json;
}

/** 刷新 access_token（401 时调用） */
let _refreshPromise: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  // 防并发锁
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = _doRefresh().finally(() => { _refreshPromise = null; });
  return _refreshPromise;
}

async function _doRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  const url = `${API_BASE}/auth/refresh`;

  // 方案 A：有 refresh_token（开发环境跨域）→ 放 body
  if (refreshToken) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return null;
      const json = await res.json();
      if (json.access_token) {
        storeTokens(json.access_token, json.user?.role || '');
        if (json.refresh_token) {
          sessionStorage.setItem('refresh_token', json.refresh_token);
        }
        return json.access_token;
      }
      return null;
    } catch {
      return null;
    }
  }

  // 方案 B：无 refresh_token（生产环境靠 cookie）
  try {
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) return null;
    const json = await res.json();
    if (json.access_token) {
      storeTokens(json.access_token, json.user?.role || '');
      if (json.refresh_token) {
        sessionStorage.setItem('refresh_token', json.refresh_token);
      }
      return json.access_token;
    }
    return null;
  } catch {
    return null;
  }
}
