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
    <div className={className} style={{ display: 'inline-flex', alignItems: 'center', position: 'relative' }}>
      <Space size={8} split={<Divider type="vertical" />}>
        {/* 左侧：刷新按钮 */}
        <Space size={8}>
          <Tooltip title={isRefreshing ? '刷新中...' : '一键刷新所有数据'}>
            <Button
              type="default"
              icon={<ReloadOutlined spin={isRefreshing} />}
              loading={isRefreshing}
              onClick={() => handleRefresh(false)}
            >
              {isRefreshing ? '刷新中' : '刷新数据'}
            </Button>
          </Tooltip>

          <Tooltip title="强制刷新（忽略缓存）">
            <Button
              type="text"
              size="small"
              onClick={() => handleRefresh(true)}
              disabled={isRefreshing}
            >
              强制刷新
            </Button>
          </Tooltip>
        </Space>

        {/* 自动刷新状态 */}
        <Space size={8} style={{ alignItems: 'center' }}>
          {config.enabled ? (
            <>
              <Tag
                color={isPaused ? 'warning' : 'success'}
                style={{ margin: 0 }}
                icon={isPaused ? <PauseCircleOutlined /> : <ClockCircleOutlined />}
              >
                {isPaused ? '已暂停' : `自动刷新 (${config.intervalSeconds}s)`}
              </Tag>
              
              {!isPaused && nextRefreshIn > 0 && (
                <Text type="secondary" style={{ fontSize: 12, width: 60, display: 'inline-block' }}>
                  {formatCountdown(nextRefreshIn)}
                </Text>
              )}

              <Tooltip title={isPaused ? '恢复自动刷新' : '暂停自动刷新'}>
                <Button
                  type="text"
                  size="small"
                  icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                  onClick={isPaused ? onResume : onPause}
                />
              </Tooltip>
            </>
          ) : (
            <Text type="secondary" style={{ fontSize: 12 }}>自动刷新未开启</Text>
          )}

          <Tooltip title="刷新设置">
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => setShowSettings(true)}
            />
          </Tooltip>
        </Space>
      </Space>

      {/* 设置面板 (Modal style) */}
      {showSettings && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            zIndex: 1000,
            marginTop: 8,
            padding: 16,
            background: '#fff',
            borderRadius: 8,
            boxShadow: '0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
            width: 300,
            border: '1px solid #f0f0f0',
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
    </div>
  );
};

export default RefreshControlPanel;
