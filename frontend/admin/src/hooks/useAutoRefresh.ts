/**
 * useAutoRefresh Hook
 * P1功能：自动刷新Dashboard数据的Hook
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import type { RefreshConfig } from '../types/dashboard';

interface UseAutoRefreshOptions {
  dashboardId: number;
  config: RefreshConfig;
  onRefresh: () => Promise<void>;
  enabled?: boolean;
}

interface UseAutoRefreshReturn {
  isRefreshing: boolean;
  lastRefreshTime: Date | null;
  nextRefreshIn: number; // 秒
  manualRefresh: () => Promise<void>;
  pauseAutoRefresh: () => void;
  resumeAutoRefresh: () => void;
  isPaused: boolean;
}

export function useAutoRefresh({
  dashboardId,
  config,
  onRefresh,
  enabled = true,
}: UseAutoRefreshOptions): UseAutoRefreshReturn {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [nextRefreshIn, setNextRefreshIn] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // 执行刷新
  const executeRefresh = useCallback(async () => {
    if (isRefreshing) return;
    
    setIsRefreshing(true);
    try {
      await onRefresh();
      setLastRefreshTime(new Date());
    } catch (error) {
      console.error('Auto refresh failed:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh, isRefreshing]);

  // 手动刷新
  const manualRefresh = useCallback(async () => {
    await executeRefresh();
    // 重置倒计时
    setNextRefreshIn(config.intervalSeconds);
  }, [executeRefresh, config.intervalSeconds]);

  // 暂停自动刷新
  const pauseAutoRefresh = useCallback(() => {
    setIsPaused(true);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  }, []);

  // 恢复自动刷新
  const resumeAutoRefresh = useCallback(() => {
    setIsPaused(false);
    setNextRefreshIn(config.intervalSeconds);
  }, [config.intervalSeconds]);

  // 设置自动刷新定时器
  useEffect(() => {
    // 清理旧的定时器
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }

    // 检查是否启用自动刷新
    if (!enabled || !config.enabled || isPaused || config.intervalSeconds < 30) {
      setNextRefreshIn(0);
      return;
    }

    // 初始化倒计时
    setNextRefreshIn(config.intervalSeconds);

    // 设置刷新定时器
    intervalRef.current = setInterval(() => {
      executeRefresh();
      setNextRefreshIn(config.intervalSeconds);
    }, config.intervalSeconds * 1000);

    // 设置倒计时更新定时器
    countdownRef.current = setInterval(() => {
      setNextRefreshIn((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
      }
    };
  }, [enabled, config.enabled, config.intervalSeconds, isPaused, executeRefresh, dashboardId]);

  return {
    isRefreshing,
    lastRefreshTime,
    nextRefreshIn,
    manualRefresh,
    pauseAutoRefresh,
    resumeAutoRefresh,
    isPaused,
  };
}

export default useAutoRefresh;
