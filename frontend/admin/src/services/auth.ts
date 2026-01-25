import api from './api';

export interface User {
  id: number;
  username: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  tenant_id?: number | null;
  permissions?: { menus?: string[]; features?: Record<string, string[]> } | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  tenant_name?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

// Token management
export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

// User management
export const getStoredUser = (): User | null => {
  const userStr = localStorage.getItem(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
};

export const setStoredUser = (user: User): void => {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const removeStoredUser = (): void => {
  localStorage.removeItem(USER_KEY);
};

// API calls
export const login = async (data: LoginRequest): Promise<TokenResponse> => {
  // Use form data format for OAuth2 compatibility
  const formData = new URLSearchParams();
  formData.append('username', data.username);
  formData.append('password', data.password);
  
  const response = await api.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const loginJson = async (data: LoginRequest): Promise<TokenResponse> => {
  const response = await api.post('/auth/login/json', data);
  return response.data;
};

export const register = async (data: RegisterRequest): Promise<User> => {
  const response = await api.post('/auth/register', data);
  return response.data;
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await api.get('/auth/me');
  return response.data;
};

export const updateProfile = async (data: { display_name?: string; avatar_url?: string }): Promise<User> => {
  const response = await api.put('/auth/me', data);
  return response.data;
};

export const changePassword = async (data: { old_password: string; new_password: string }): Promise<{ message: string }> => {
  const response = await api.post('/auth/change-password', data);
  return response.data;
};

// Logout - clear all auth data
export const logout = (): void => {
  removeToken();
  removeStoredUser();
};

// Check if user is authenticated
export const isAuthenticated = (): boolean => {
  return !!getToken();
};

// Session Code API (用于安全的跨域 token 传递)
export interface SessionCodeResponse {
  code: string;
  expires_in: number;
}

export const createSessionCode = async (): Promise<SessionCodeResponse> => {
  const response = await api.post('/auth/session-code');
  return response.data;
};
