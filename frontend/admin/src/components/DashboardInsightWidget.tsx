/**
 * DashboardInsightWidget 组件
 * 用于在Dashboard中展示智能数据洞察分析结果
 */
import React, { useState } from 'react';
import { Card, Button, Space, Tag, Typography, Collapse, Spin, message } from 'antd';
import {
  LineChartOutlined,
  AlertOutlined,
  BulbOutlined,
  BarChartOutlined,
  ReloadOutlined,
  SettingOutlined,
  UpOutlined,
  DownOutlined,
  LinkOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons';
import type { InsightResult } from '../types/dashboard';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface DashboardInsightWidgetProps {
  widgetId: number;
  insights: InsightResult;
  loading?: boolean;
  onRefresh?: () => void;
  onOpenConditionPanel?: () => void;
  onViewLineage?: () => void;
  className?: string;
}

export const DashboardInsightWidget: React.FC<DashboardInsightWidgetProps> = ({
  widgetId,
  insights,
  loading = false,
  onRefresh,
  onOpenConditionPanel,
  onViewLineage,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasSummary = insights?.summary && Object.keys(insights.summary).length > 0;
  const hasTrends = insights?.trends;
  const hasAnomalies = insights?.anomalies && insights.anomalies.length > 0;
  const hasCorrelations = insights?.correlations && insights.correlations.length > 0;
  const hasRecommendations = insights?.recommendations && insights.recommendations.length > 0;

  const hasAnyInsights =
    hasSummary || hasTrends || hasAnomalies || hasCorrelations || hasRecommendations;

  if (!hasAnyInsights && !loading) {
    return (
      <Card
        className={className}
        style={{
          background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
          color: 'white',
          marginBottom: 20,
          borderRadius: 16,
          border: 'none',
          boxShadow: '0 4px 16px rgba(99, 102, 241, 0.25)',
        }}
      >
        <div style={{ textAlign: 'center', padding: '28px 20px' }}>
          <BarChartOutlined style={{ fontSize: 52, marginBottom: 16, opacity: 0.9 }} />
          <Title level={4} style={{ color: 'white', marginBottom: 8 }}>暂无洞察数据</Title>
          <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: 14 }}>请点击"生成洞察"按钮开始分析</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={className}
      style={{
        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
        marginBottom: 20,
        border: 'none',
        borderRadius: 16,
        boxShadow: '0 4px 16px rgba(99, 102, 241, 0.25)',
      }}
      styles={{ body: { padding: 0 } }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '18px 24px',
          borderBottom: '1px solid rgba(255,255,255,0.12)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BarChartOutlined style={{ fontSize: 22, color: 'white' }} />
          <Title level={4} style={{ margin: 0, color: 'white', fontWeight: 600 }}>
            智能数据洞察
          </Title>
        </div>
        <Space>
          {onViewLineage && (
            <Button
              size="small"
              icon={<NodeIndexOutlined />}
              onClick={onViewLineage}
              style={{
                background: 'rgba(255,255,255,0.15)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 8,
              }}
            >
              数据溯源
            </Button>
          )}
          {onOpenConditionPanel && (
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={onOpenConditionPanel}
              style={{
                background: 'rgba(255,255,255,0.15)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 8,
              }}
            >
              调整条件
            </Button>
          )}
          {onRefresh && (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={onRefresh}
              style={{
                background: 'rgba(255,255,255,0.15)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 8,
              }}
            >
              刷新
            </Button>
          )}
          <Button
            size="small"
            type="text"
            icon={isExpanded ? <UpOutlined /> : <DownOutlined />}
            onClick={() => setIsExpanded(!isExpanded)}
            style={{ color: 'white' }}
          >
            {isExpanded ? '收起' : '展开'}
          </Button>
        </Space>
      </div>

      {/* 内容区域 */}
      {isExpanded && (
        <div style={{ padding: '20px 24px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 20, color: 'white', fontSize: 14 }}>正在生成洞察分析...</div>
            </div>
          ) : (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              {/* 数据摘要 */}
              {hasSummary && (
                <Card
                  size="small"
                  title={
                    <span style={{ color: '#4b5563', fontWeight: 600 }}>
                      <BarChartOutlined style={{ marginRight: 8, color: '#6366f1' }} />
                      数据摘要
                    </span>
                  }
                  style={{ 
                    background: 'rgba(255,255,255,0.98)', 
                    borderRadius: 12,
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  }}
                  styles={{ header: { borderBottom: '1px solid #f3f4f6' } }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.summary?.description && (
                      <Text>{insights.summary.description}</Text>
                    )}
                    {insights.summary?.data_points && (
                      <Text type="secondary">
                        数据点数: <Text strong>{insights.summary.data_points}</Text>
                      </Text>
                    )}
                    {insights.summary?.key_metrics &&
                      Object.entries(insights.summary.key_metrics)
                        .slice(0, 5)
                        .map(([key, value]) => (
                          <div key={key}>
                            <Text type="secondary">{key}: </Text>
                            <Text strong>
                              {typeof value === 'number'
                                ? value.toLocaleString()
                                : String(value)}
                            </Text>
                          </div>
                        ))}
                  </Space>
                </Card>
              )}

              {/* 趋势分析 */}
              {hasTrends && (
                <Card
                  size="small"
                  title={
                    <span style={{ color: '#4b5563', fontWeight: 600 }}>
                      <LineChartOutlined style={{ marginRight: 8, color: '#10b981' }} />
                      趋势分析
                    </span>
                  }
                  style={{ 
                    background: 'rgba(255,255,255,0.98)', 
                    borderRadius: 12,
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  }}
                  styles={{ header: { borderBottom: '1px solid #f3f4f6' } }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.trends?.description && (
                      <Text>{insights.trends?.description}</Text>
                    )}
                    {insights.trends?.direction && (
                      <div>
                        <Text type="secondary">趋势方向: </Text>
                        <Tag
                          color={
                            insights.trends?.direction === 'up'
                              ? 'green'
                              : insights.trends?.direction === 'down'
                              ? 'red'
                              : 'blue'
                          }
                        >
                          {insights.trends?.direction === 'up'
                            ? '上升'
                            : insights.trends?.direction === 'down'
                            ? '下降'
                            : '稳定'}
                        </Tag>
                      </div>
                    )}
                    {insights.trends?.change_rate !== undefined && (
                      <div>
                        <Text type="secondary">变化率: </Text>
                        <Text
                          strong
                          style={{
                            color:
                              (insights.trends?.change_rate ?? 0) > 0
                                ? '#52c41a'
                                : (insights.trends?.change_rate ?? 0) < 0
                                ? '#ff4d4f'
                                : '#666',
                          }}
                        >
                          {(insights.trends?.change_rate ?? 0) > 0 ? '+' : ''}
                          {insights.trends?.change_rate?.toFixed(2)}%
                        </Text>
                      </div>
                    )}
                  </Space>
                </Card>
              )}

              {/* 异常检测 */}
              {hasAnomalies && (
                <Card
                  size="small"
                  title={
                    <span style={{ color: '#4b5563', fontWeight: 600 }}>
                      <AlertOutlined style={{ marginRight: 8, color: '#f59e0b' }} />
                      异常检测
                    </span>
                  }
                  style={{ 
                    background: 'rgba(255,255,255,0.98)', 
                    borderRadius: 12,
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  }}
                  styles={{ header: { borderBottom: '1px solid #f3f4f6' } }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.anomalies?.slice(0, 5).map((anomaly: any, index: number) => (
                      <div key={index} style={{ paddingLeft: 12, borderLeft: '3px solid #f59e0b', borderRadius: 2 }}>
                        {anomaly.metric && (
                          <Tag color="orange" style={{ borderRadius: 4 }}>{anomaly.metric}</Tag>
                        )}
                        <Text style={{ color: '#4b5563' }}>{anomaly.description}</Text>
                        {anomaly.severity && (
                          <Tag
                            color={
                              anomaly.severity === 'high'
                                ? 'red'
                                : anomaly.severity === 'medium'
                                ? 'orange'
                                : 'yellow'
                            }
                            style={{ marginLeft: 8, borderRadius: 4 }}
                          >
                            {anomaly.severity}
                          </Tag>
                        )}
                      </div>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 关联洞察 */}
              {hasCorrelations && (
                <Card
                  size="small"
                  title={
                    <span style={{ color: '#4b5563', fontWeight: 600 }}>
                      <LinkOutlined style={{ marginRight: 8, color: '#3b82f6' }} />
                      关联洞察
                    </span>
                  }
                  style={{ 
                    background: 'rgba(255,255,255,0.98)', 
                    borderRadius: 12,
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  }}
                  styles={{ header: { borderBottom: '1px solid #f3f4f6' } }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.correlations?.slice(0, 5).map((correlation: any, index: number) => (
                      <div
                        key={index}
                        style={{ paddingLeft: 12, borderLeft: '3px solid #3b82f6', borderRadius: 2 }}
                      >
                        {correlation.entities && correlation.entities.length > 0 && (
                          <div style={{ marginBottom: 6 }}>
                            {correlation.entities.map((entity: any, idx: number) => (
                              <Tag key={idx} color="blue" style={{ borderRadius: 4 }}>
                                {entity}
                              </Tag>
                            ))}
                          </div>
                        )}
                        <Text style={{ color: '#4b5563' }}>{correlation.description}</Text>
                        {correlation.strength !== undefined && (
                          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                            (相关度: {(correlation.strength * 100).toFixed(0)}%)
                          </Text>
                        )}
                      </div>
                    ))}
                  </Space>
                </Card>
              )}

              {/* 业务建议 */}
              {hasRecommendations && (
                <Card
                  size="small"
                  title={
                    <span style={{ color: '#4b5563', fontWeight: 600 }}>
                      <BulbOutlined style={{ marginRight: 8, color: '#8b5cf6' }} />
                      业务建议
                    </span>
                  }
                  style={{ 
                    background: 'rgba(255,255,255,0.98)', 
                    borderRadius: 12,
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  }}
                  styles={{ header: { borderBottom: '1px solid #f3f4f6' } }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.recommendations?.slice(0, 5).map((rec: any, index: number) => (
                      <div
                        key={index}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 10,
                        }}
                      >
                        <Text strong style={{ color: '#8b5cf6', minWidth: 20 }}>
                          {index + 1}.
                        </Text>
                        <div style={{ flex: 1 }}>
                          {rec.category && (
                            <Tag color="purple" style={{ marginRight: 8, borderRadius: 4 }}>
                              {rec.category}
                            </Tag>
                          )}
                          <Text style={{ color: '#4b5563' }}>{rec.content}</Text>
                          {rec.priority && (
                            <Tag
                              color={
                                rec.priority === 'high'
                                  ? 'red'
                                  : rec.priority === 'medium'
                                  ? 'orange'
                                  : 'default'
                              }
                              style={{ marginLeft: 8, borderRadius: 4 }}
                            >
                              {rec.priority}
                            </Tag>
                          )}
                        </div>
                      </div>
                    ))}
                  </Space>
                </Card>
              )}
            </Space>
          )}
        </div>
      )}
    </Card>
  );
};

export default DashboardInsightWidget;
