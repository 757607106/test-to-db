/**
 * InsightLineagePanel 组件
 * P0功能：展示数据洞察的溯源信息，包括数据来源、SQL生成过程、执行元数据等
 */
import React, { useState } from 'react';
import { Card, Tag, Typography, Space, Button, Tooltip, Divider, message } from 'antd';
import {
  DatabaseOutlined,
  CodeOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  RightOutlined,
  TableOutlined,
} from '@ant-design/icons';
import type { InsightLineage } from '../types/dashboard';

const { Text, Title, Paragraph } = Typography;

interface InsightLineagePanelProps {
  lineage: InsightLineage;
  onViewSql?: () => void;
  onViewTables?: (tables: string[]) => void;
  className?: string;
}

export const InsightLineagePanel: React.FC<InsightLineagePanelProps> = ({
  lineage,
  onViewSql,
  onViewTables,
  className,
}) => {
  const [sqlVisible, setSqlVisible] = useState(false);

  const handleCopySql = () => {
    if (lineage.generatedSql) {
      navigator.clipboard.writeText(lineage.generatedSql);
      message.success('SQL已复制到剪贴板');
    }
  };

  const hasSourceTables = lineage.sourceTables && lineage.sourceTables.length > 0;
  const hasTransformations = lineage.dataTransformations && lineage.dataTransformations.length > 0;

  return (
    <Card
      className={className}
      style={{
        background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
      }}
      styles={{ body: { padding: '16px 20px' } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <InfoCircleOutlined style={{ fontSize: 18, color: '#6366f1' }} />
        <Title level={5} style={{ margin: 0, color: '#334155' }}>
          数据溯源
        </Title>
        <Tooltip title="展示数据的来源、生成过程和执行详情">
          <InfoCircleOutlined style={{ fontSize: 14, color: '#94a3b8', cursor: 'pointer' }} />
        </Tooltip>
      </div>

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {/* 数据来源表 */}
        {hasSourceTables && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <TableOutlined style={{ color: '#3b82f6' }} />
              <Text strong style={{ color: '#475569' }}>数据来源</Text>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {lineage.sourceTables.map((table, index) => (
                <Tag
                  key={index}
                  color="blue"
                  style={{
                    borderRadius: 6,
                    padding: '2px 10px',
                    cursor: onViewTables ? 'pointer' : 'default',
                  }}
                  onClick={() => onViewTables?.([table])}
                >
                  <DatabaseOutlined style={{ marginRight: 4 }} />
                  {table}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* 执行元数据 */}
        <div
          style={{
            background: 'white',
            borderRadius: 8,
            padding: 12,
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <ThunderboltOutlined style={{ color: '#f59e0b' }} />
            <Text strong style={{ color: '#475569' }}>执行详情</Text>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>执行耗时</Text>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <ClockCircleOutlined style={{ color: '#6366f1', fontSize: 14 }} />
                <Text strong style={{ color: '#334155' }}>
                  {lineage.executionMetadata.executionTimeMs} ms
                </Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>数据行数</Text>
              <div>
                <Text strong style={{ color: '#334155' }}>
                  {lineage.executionMetadata.rowCount.toLocaleString()} 行
                </Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>缓存状态</Text>
              <div>
                <Tag
                  color={lineage.executionMetadata.fromCache ? 'green' : 'default'}
                  style={{ borderRadius: 4 }}
                >
                  {lineage.executionMetadata.fromCache ? '命中缓存' : '实时查询'}
                </Tag>
              </div>
            </div>
            {lineage.executionMetadata.dbType && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>数据库类型</Text>
                <div>
                  <Tag color="purple" style={{ borderRadius: 4 }}>
                    {lineage.executionMetadata.dbType}
                  </Tag>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* SQL生成追踪 */}
        <div
          style={{
            background: 'white',
            borderRadius: 8,
            padding: 12,
            border: '1px solid #e2e8f0',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <CodeOutlined style={{ color: '#10b981' }} />
              <Text strong style={{ color: '#475569' }}>SQL生成</Text>
            </div>
            <Tag
              color={
                lineage.sqlGenerationTrace.generationMethod === 'cache'
                  ? 'green'
                  : lineage.sqlGenerationTrace.generationMethod === 'template'
                  ? 'blue'
                  : 'default'
              }
              style={{ borderRadius: 4 }}
            >
              {lineage.sqlGenerationTrace.generationMethod === 'cache'
                ? '缓存命中'
                : lineage.sqlGenerationTrace.generationMethod === 'template'
                ? '模板生成'
                : '智能生成'}
            </Tag>
          </div>

          {lineage.sqlGenerationTrace.userIntent && (
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>用户意图：</Text>
              <Text style={{ color: '#334155' }}>{lineage.sqlGenerationTrace.userIntent}</Text>
            </div>
          )}

          {lineage.sqlGenerationTrace.fewShotSamplesCount > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                参考了 <Text strong>{lineage.sqlGenerationTrace.fewShotSamplesCount}</Text> 个样本
              </Text>
            </div>
          )}

          {/* SQL语句 */}
          {lineage.generatedSql && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setSqlVisible(!sqlVisible)}
                  style={{ padding: 0, height: 'auto' }}
                >
                  <RightOutlined
                    style={{
                      transform: sqlVisible ? 'rotate(90deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s',
                      marginRight: 4,
                    }}
                  />
                  {sqlVisible ? '收起SQL' : '查看SQL'}
                </Button>
                <Tooltip title="复制SQL">
                  <Button
                    type="text"
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={handleCopySql}
                  />
                </Tooltip>
              </div>
              {sqlVisible && (
                <pre
                  style={{
                    background: '#1e293b',
                    color: '#e2e8f0',
                    padding: 12,
                    borderRadius: 6,
                    fontSize: 12,
                    overflow: 'auto',
                    maxHeight: 200,
                    margin: 0,
                  }}
                >
                  {lineage.generatedSql}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* 数据转换步骤 */}
        {hasTransformations && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <CheckCircleOutlined style={{ color: '#10b981' }} />
              <Text strong style={{ color: '#475569' }}>处理流程</Text>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {lineage.dataTransformations.map((step, index) => (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '4px 0',
                  }}
                >
                  <div
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      background: '#6366f1',
                      color: 'white',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    {index + 1}
                  </div>
                  <Text style={{ color: '#475569' }}>{step}</Text>
                </div>
              ))}
            </div>
          </div>
        )}
      </Space>
    </Card>
  );
};

export default InsightLineagePanel;
