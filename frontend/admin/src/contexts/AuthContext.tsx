import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  User,
  LoginRequest,
  RegisterRequest,
  login as apiLogin,
  register as apiRegister,
  getCurrentUser,
  logout as apiLogout,
  getToken,
  setToken,
  getStoredUser,
  setStoredUser,
  removeStoredUser,
  removeToken,
} from '../services/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(getStoredUser());
  const [token, setTokenState] = useState<string | null>(getToken());
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!token && !!user;

  // Refresh user data from API
  const refreshUser = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
      setStoredUser(userData);
    } catch (error) {
      // Token is invalid, clear auth
      console.error('Failed to refresh user:', error);
      setUser(null);
      setTokenState(null);
      removeToken();
      removeStoredUser();
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // Initialize auth state on mount
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (data: LoginRequest) => {
    setIsLoading(true);
    try {
      const response = await apiLogin(data);
      setToken(response.access_token);
      setTokenState(response.access_token);
      
      // Fetch user data
      const userData = await getCurrentUser();
      setUser(userData);
      setStoredUser(userData);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: RegisterRequest) => {
    setIsLoading(true);
    try {
      await apiRegister(data);
      // After registration, automatically login
      await login({ username: data.username, password: data.password });
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    apiLogout();
    setUser(null);
    setTokenState(null);
  };

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    isAuthenticated,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
