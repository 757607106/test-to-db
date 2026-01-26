/**
 * RefreshControlPanel 组件
 * P1功能：Dashboard刷新控制面板，包括一键刷新和自动刷新配置
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Switch,
  InputNumber,
  Space,
  Typography,
  Tooltip,
  Progress,
  Tag,
  Divider,
  message,
} from 'antd';
import {
  ReloadOutlined,
  ClockCircleOutlined,
  SettingOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { RefreshConfig, GlobalRefreshResponse } from '../types/dashboard';

const { Text, Title } = Typography;

interface RefreshControlPanelProps {
  dashboardId: number;
  config: RefreshConfig;
  onConfigChange: (config: RefreshConfig) => Promise<void>;
  onGlobalRefresh: (force: boolean) => Promise<GlobalRefreshResponse>;
  isRefreshing: boolean;
  lastRefreshTime?: Date | null;
  nextRefreshIn?: number;
  isPaused?: boolean;
  onPause?: () => void;
  onResume?: () => void;
  className?: string;
}

export const RefreshControlPanel: React.FC<RefreshControlPanelProps> = ({
  dashboardId,
  config,
  onConfigChange,
  onGlobalRefresh,
  isRefreshing,
  lastRefreshTime,
  nextRefreshIn = 0,
  isPaused = false,
  onPause,
  onResume,
  className,
}) => {
  const [localConfig, setLocalConfig] = useState<RefreshConfig>(config);
  const [showSettings, setShowSettings] = useState(false);
  const [refreshResult, setRefreshResult] = useState<GlobalRefreshResponse | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleRefresh = async (force: boolean = false) => {
    try {
      const result = await onGlobalRefresh(force);
      setRefreshResult(result);
      
      if (result.failedCount === 0) {
        message.success(`刷新完成: ${result.successCount} 个组件已更新`);
      } else {
        message.warning(`刷新完成: ${result.successCount} 成功, ${result.failedCount} 失败`);
      }
    } catch (error) {
      message.error('刷新失败');
    }
  };

  const handleConfigChange = async (changes: Partial<RefreshConfig>) => {
    const newConfig = { ...localConfig, ...changes };
    setLocalConfig(newConfig);
  };

  const handleSaveConfig = async () => {
    setIsSaving(true);
    try {
      await onConfigChange(localConfig);
      message.success('刷新配置已保存');
      setShowSettings(false);
    } catch (error) {
      message.error('保存配置失败');
    } finally {
      setIsSaving(false);
    }
  };

  const formatTime = (date: Date | null | undefined) => {
    if (!date) return '--';
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatCountdown = (seconds: number) => {
    if (seconds <= 0) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`;
  };

  return (
    <Card
      className={className}
      size="small"
      style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: 12,
        border: 'none',
        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
      }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* 左侧：刷新按钮和状态 */}
        <Space size={12}>
          <Tooltip title={isRefreshing ? '刷新中...' : '一键刷新所有数据'}>
            <Button
              type="primary"
              icon={<ReloadOutlined spin={isRefreshing} />}
              loading={isRefreshing}
              onClick={() => handleRefresh(false)}
              style={{
                background: 'rgba(255,255,255,0.2)',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: 8,
              }}
            >
              {isRefreshing ? '刷新中' : '一键刷新'}
            </Button>
          </Tooltip>

          <Tooltip title="强制刷新（忽略缓存）">
            <Button
              type="text"
              size="small"
              onClick={() => handleRefresh(true)}
              disabled={isRefreshing}
              style={{ color: 'rgba(255,255,255,0.85)' }}
            >
              强制刷新
            </Button>
          </Tooltip>

          <Divider type="vertical" style={{ background: 'rgba(255,255,255,0.3)', height: 24 }} />

          {/* 自动刷新状态 */}
          {config.enabled && (
            <Space size={8}>
              <Tag
                color={isPaused ? 'orange' : 'green'}
                style={{ borderRadius: 4, margin: 0 }}
              >
                {isPaused ? '已暂停' : '自动刷新'}
              </Tag>
              
              {!isPaused && nextRefreshIn > 0 && (
                <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12 }}>
                  <ClockCircleOutlined style={{ marginRight: 4 }} />
                  {formatCountdown(nextRefreshIn)}后刷新
                </Text>
              )}

              {isPaused ? (
                <Tooltip title="恢复自动刷新">
                  <Button
                    type="text"
                    size="small"
                    icon={<PlayCircleOutlined />}
                    onClick={onResume}
                    style={{ color: 'rgba(255,255,255,0.85)' }}
                  />
                </Tooltip>
              ) : (
                <Tooltip title="暂停自动刷新">
                  <Button
                    type="text"
                    size="small"
                    icon={<PauseCircleOutlined />}
                    onClick={onPause}
                    style={{ color: 'rgba(255,255,255,0.85)' }}
                  />
                </Tooltip>
              )}
            </Space>
          )}
        </Space>

        {/* 右侧：配置按钮和上次刷新时间 */}
        <Space size={12}>
          {lastRefreshTime && (
            <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>
              上次刷新: {formatTime(lastRefreshTime)}
            </Text>
          )}

          <Tooltip title="刷新设置">
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => setShowSettings(!showSettings)}
              style={{ color: 'rgba(255,255,255,0.85)' }}
            />
          </Tooltip>
        </Space>
      </div>

      {/* 刷新结果展示 */}
      {refreshResult && !isRefreshing && (
        <div
          style={{
            marginTop: 12,
            padding: '8px 12px',
            background: 'rgba(255,255,255,0.1)',
            borderRadius: 8,
          }}
        >
          <Space size={16}>
            <span style={{ color: 'rgba(255,255,255,0.85)' }}>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
              成功: {refreshResult.successCount}
            </span>
            {refreshResult.failedCount > 0 && (
              <span style={{ color: 'rgba(255,255,255,0.85)' }}>
                <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 4 }} />
                失败: {refreshResult.failedCount}
              </span>
            )}
            <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12 }}>
              耗时: {refreshResult.totalDurationMs}ms
            </span>
          </Space>
        </div>
      )}

      {/* 设置面板 */}
      {showSettings && (
        <div
          style={{
            marginTop: 12,
            padding: 16,
            background: 'rgba(255,255,255,0.95)',
            borderRadius: 8,
          }}
        >
          <Title level={5} style={{ marginBottom: 16, color: '#334155' }}>
            刷新设置
          </Title>

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Text>启用自动刷新</Text>
              <Switch
                checked={localConfig.enabled}
                onChange={(checked) => handleConfigChange({ enabled: checked })}
              />
            </div>

            {localConfig.enabled && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text>刷新间隔</Text>
                <Space>
                  <InputNumber
                    min={30}
                    max={86400}
                    value={localConfig.intervalSeconds}
                    onChange={(value) =>
                      handleConfigChange({ intervalSeconds: value || 300 })
                    }
                    style={{ width: 100 }}
                  />
                  <Text type="secondary">秒</Text>
                </Space>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button size="small" onClick={() => setShowSettings(false)}>
                取消
              </Button>
              <Button
                type="primary"
                size="small"
                loading={isSaving}
                onClick={handleSaveConfig}
              >
                保存
              </Button>
            </div>
          </Space>
        </div>
      )}
    </Card>
  );
};

export default RefreshControlPanel;
