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
  className?: string;
}

export const DashboardInsightWidget: React.FC<DashboardInsightWidgetProps> = ({
  widgetId,
  insights,
  loading = false,
  onRefresh,
  onOpenConditionPanel,
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
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          marginBottom: 16,
        }}
      >
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <BarChartOutlined style={{ fontSize: 48, marginBottom: 16 }} />
          <Title level={4} style={{ color: 'white' }}>暂无洞察数据</Title>
          <Text style={{ color: 'rgba(255,255,255,0.8)' }}>请点击"生成洞察"按钮开始分析</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={className}
      style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        marginBottom: 16,
        border: 'none',
      }}
      bodyStyle={{ padding: 0 }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChartOutlined style={{ fontSize: 20, color: 'white' }} />
          <Title level={4} style={{ margin: 0, color: 'white' }}>
            智能数据洞察
          </Title>
        </div>
        <Space>
          {onOpenConditionPanel && (
            <Button
              size="small"
              icon={<SettingOutlined />}
              onClick={onOpenConditionPanel}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: 'white',
                border: 'none',
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
                background: 'rgba(255,255,255,0.2)',
                color: 'white',
                border: 'none',
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
        <div style={{ padding: 20 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16, color: 'white' }}>正在生成洞察分析...</div>
            </div>
          ) : (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {/* 数据摘要 */}
              {hasSummary && (
                <Card
                  size="small"
                  title={
                    <span>
                      <BarChartOutlined style={{ marginRight: 8 }} />
                      数据摘要
                    </span>
                  }
                  style={{ background: 'rgba(255,255,255,0.95)' }}
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
                    <span style={{ color: '#52c41a' }}>
                      <LineChartOutlined style={{ marginRight: 8 }} />
                      趋势分析
                    </span>
                  }
                  style={{ background: 'rgba(255,255,255,0.95)' }}
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
                    <span style={{ color: '#fa8c16' }}>
                      <AlertOutlined style={{ marginRight: 8 }} />
                      异常检测
                    </span>
                  }
                  style={{ background: 'rgba(255,255,255,0.95)' }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.anomalies?.slice(0, 5).map((anomaly: any, index: number) => (
                      <div key={index} style={{ paddingLeft: 8, borderLeft: '3px solid #fa8c16' }}>
                        {anomaly.metric && (
                          <Tag color="orange">{anomaly.metric}</Tag>
                        )}
                        <Text>{anomaly.description}</Text>
                        {anomaly.severity && (
                          <Tag
                            color={
                              anomaly.severity === 'high'
                                ? 'red'
                                : anomaly.severity === 'medium'
                                ? 'orange'
                                : 'yellow'
                            }
                            style={{ marginLeft: 8 }}
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
                    <span style={{ color: '#1890ff' }}>
                      <LinkOutlined style={{ marginRight: 8 }} />
                      关联洞察
                    </span>
                  }
                  style={{ background: 'rgba(255,255,255,0.95)' }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.correlations?.slice(0, 5).map((correlation: any, index: number) => (
                      <div
                        key={index}
                        style={{ paddingLeft: 8, borderLeft: '3px solid #1890ff' }}
                      >
                        {correlation.entities && correlation.entities.length > 0 && (
                          <div style={{ marginBottom: 4 }}>
                            {correlation.entities.map((entity: any, idx: number) => (
                              <Tag key={idx} color="blue">
                                {entity}
                              </Tag>
                            ))}
                          </div>
                        )}
                        <Text>{correlation.description}</Text>
                        {correlation.strength !== undefined && (
                          <Text type="secondary" style={{ marginLeft: 8 }}>
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
                    <span style={{ color: '#722ed1' }}>
                      <BulbOutlined style={{ marginRight: 8 }} />
                      业务建议
                    </span>
                  }
                  style={{ background: 'rgba(255,255,255,0.95)' }}
                >
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {insights.recommendations?.slice(0, 5).map((rec: any, index: number) => (
                      <div
                        key={index}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 8,
                        }}
                      >
                        <Text strong style={{ color: '#722ed1', minWidth: 20 }}>
                          {index + 1}.
                        </Text>
                        <div style={{ flex: 1 }}>
                          {rec.category && (
                            <Tag color="purple" style={{ marginRight: 8 }}>
                              {rec.category}
                            </Tag>
                          )}
                          <Text>{rec.content}</Text>
                          {rec.priority && (
                            <Tag
                              color={
                                rec.priority === 'high'
                                  ? 'red'
                                  : rec.priority === 'medium'
                                  ? 'orange'
                                  : 'default'
                              }
                              style={{ marginLeft: 8 }}
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
