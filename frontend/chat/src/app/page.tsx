"use client";

import { Thread } from "@/components/thread";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import { ArtifactProvider } from "@/components/thread/artifact";
import { Toaster } from "@/components/ui/sonner";
import React, { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

// 后端 API 地址 - 动态适配
const getApiBaseUrl = (): string => {
  if (process.env.NEXT_PUBLIC_BACKEND_API_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_API_URL;
  }
  
  // 根据当前访问的 hostname 动态决定后端地址
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000/api';
  }
  return 'http://192.168.13.163:8000/api';
};

const API_BASE_URL = getApiBaseUrl();

// 用 session code 交换 token
async function exchangeCodeForToken(code: string): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/exchange-code?code=${encodeURIComponent(code)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      console.error('Code exchange failed:', response.status);
      return null;
    }
    
    const data = await response.json();
    return data.access_token;
  } catch (error) {
    console.error('Code exchange error:', error);
    return null;
  }
}

function TokenHandler({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initAuth = async () => {
      // 优先处理 session code (更安全)
      const urlCode = searchParams.get('code');
      if (urlCode) {
        // 用 code 交换 token
        const token = await exchangeCodeForToken(urlCode);
        if (token) {
          localStorage.setItem('auth_token', token);
        }
        // 清除 URL 中的 code 参数
        const url = new URL(window.location.href);
        url.searchParams.delete('code');
        window.history.replaceState({}, '', url.toString());
        
        if (!token) {
          setError('Session 已过期，请重新从管理后台进入');
          setIsReady(true);
          return;
        }
      }
      
      // 兼容旧的 token 方式 (向后兼容)
      const urlToken = searchParams.get('token');
      if (urlToken) {
        localStorage.setItem('auth_token', urlToken);
        const url = new URL(window.location.href);
        url.searchParams.delete('token');
        window.history.replaceState({}, '', url.toString());
      }

      // 检查是否有有效 token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setError('未登录，请先从管理后台进入');
      }
      
      setIsReady(true);
    };
    
    initAuth();
  }, [searchParams]);

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent mx-auto"></div>
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    // 动态获取管理后台地址
    const getAdminUrl = () => {
      const hostname = window.location.hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:3001';
      }
      return 'http://192.168.13.163:3001';
    };

    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-100">
            <svg className="h-8 w-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">需要登录</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <a
            href={getAdminUrl()}
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            前往管理后台登录
          </a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export default function DemoPage(): React.ReactNode {
  return (
    <React.Suspense fallback={<div className="flex min-h-screen items-center justify-center"><p>加载中...</p></div>}>
      <Toaster />
      <TokenHandler>
        <ThreadProvider>
          <StreamProvider>
            <ArtifactProvider>
              <Thread />
            </ArtifactProvider>
          </StreamProvider>
        </ThreadProvider>
      </TokenHandler>
    </React.Suspense>
  );
}
