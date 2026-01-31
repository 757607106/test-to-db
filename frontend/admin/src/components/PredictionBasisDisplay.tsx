/**
 * 预测分析依据展示组件
 * 用于展示数据溯源、关键指标和推理步骤
 */
import React from 'react';
import { Card, Collapse, Descriptions, Table, Steps, Alert, Tag, Space, Typography } from 'antd';
import { 
  QuestionCircleOutlined, 
  DatabaseOutlined, 
  BarChartOutlined, 
  BranchesOutlined,
  CheckCircleOutlined 
} from '@ant-design/icons';

const { Text } = Typography;

interface DataSource {
  tables: string[];
  columns: string[];
  row_count: number;
  time_range?: string;
  filters_applied?: string[];
}

interface KeyMetric {
  name: string;
  value: number;
  description: string;
  used_in_steps: number[];
}

interface ReasoningStep {
  step: number;
  description: string;
  formula?: string;
  input_description: string;
  output_description: string;
}

interface PredictionExplanation {
  method_explanation: string;
  formula_used: string;
  key_parameters: Record<string, any>;
  calculation_steps: string[];
  confidence_explanation: string;
  reliability_assessment: string;
  // 新增字段
  data_source?: DataSource;
  key_metrics?: KeyMetric[];
  reasoning_chain?: ReasoningStep[];
}

interface Props {
  explanation: PredictionExplanation;
}

const PredictionBasisDisplay: React.FC<Props> = ({ explanation }) => {
  // 如果没有新增字段，不显示此组件
  if (!explanation.data_source && !explanation.key_metrics && !explanation.reasoning_chain) {
    return null;
  }

  type ItemType = {
    key: string;
    label: React.ReactElement;
    children: React.ReactElement;
  };

  const items: ItemType[] = [
    // 数据来源
    explanation.data_source ? {
      key: 'data_source',
      label: (
        <span>
          <DatabaseOutlined style={{ marginRight: 8 }} />
          数据来源
        </span>
      ),
      children: (
        <Card size="small" bordered={false}>
          <Descriptions size="small" column={2} bordered>
            {explanation.data_source.tables.length > 0 && (
              <Descriptions.Item label="数据表" span={2}>
                {explanation.data_source.tables.map(t => (
                  <Tag key={t} color="blue">{t}</Tag>
                ))}
              </Descriptions.Item>
            )}
            {explanation.data_source.columns.length > 0 && (
              <Descriptions.Item label="分析字段" span={2}>
                {explanation.data_source.columns.map(c => (
                  <Tag key={c} color="cyan">{c}</Tag>
                ))}
              </Descriptions.Item>
            )}
            <Descriptions.Item label="数据行数">
              <Text strong>{explanation.data_source.row_count.toLocaleString()}</Text> 行
            </Descriptions.Item>
            {explanation.data_source.time_range && (
              <Descriptions.Item label="时间范围">
                {explanation.data_source.time_range}
              </Descriptions.Item>
            )}
            {explanation.data_source.filters_applied && explanation.data_source.filters_applied.length > 0 && (
              <Descriptions.Item label="筛选条件" span={2}>
                {explanation.data_source.filters_applied.join(', ')}
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      ),
    } : null,
    
    // 关键指标
    explanation.key_metrics && explanation.key_metrics.length > 0 ? {
      key: 'key_metrics',
      label: (
        <span>
          <BarChartOutlined style={{ marginRight: 8 }} />
          关键指标
        </span>
      ),
      children: (
        <Table
          size="small"
          pagination={false}
          dataSource={explanation.key_metrics}
          rowKey="name"
          columns={[
            {
              title: '指标名称',
              dataIndex: 'name',
              width: 100,
              render: (text) => <Text strong>{text}</Text>,
            },
            {
              title: '数值',
              dataIndex: 'value',
              width: 120,
              render: (val) => <Text code>{val.toFixed(2)}</Text>,
            },
            {
              title: '说明',
              dataIndex: 'description',
              render: (text) => <Text type="secondary">{text}</Text>,
            },
            {
              title: '用于步骤',
              dataIndex: 'used_in_steps',
              width: 120,
              render: (steps: number[]) => 
                steps.length > 0 ? (
                  <Space size={4}>
                    {steps.map(s => (
                      <Tag key={s} color="processing">步骤{s}</Tag>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">-</Text>
                ),
            },
          ]}
        />
      ),
    } : null,
    
    // 推理步骤
    explanation.reasoning_chain && explanation.reasoning_chain.length > 0 ? {
      key: 'reasoning_chain',
      label: (
        <span>
          <BranchesOutlined style={{ marginRight: 8 }} />
          计算过程
        </span>
      ),
      children: (
        <Steps
          direction="vertical"
          size="small"
          items={explanation.reasoning_chain.map(step => ({
            title: (
              <Space>
                <Text strong>步骤 {step.step}</Text>
                <Text>{step.description}</Text>
              </Space>
            ),
            description: (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <div>
                  <Text type="secondary">输入: </Text>
                  <Text>{step.input_description}</Text>
                </div>
                {step.formula && (
                  <div>
                    <Text type="secondary">公式: </Text>
                    <Text code>{step.formula}</Text>
                  </div>
                )}
                <div>
                  <Text type="secondary">输出: </Text>
                  <Text strong>{step.output_description}</Text>
                </div>
              </Space>
            ),
            icon: <CheckCircleOutlined />,
          }))}
        />
      ),
    } : null,
  ].filter((item): item is ItemType => item !== null);

  return (
    <Collapse
      size="small"
      items={items}
      defaultActiveKey={['data_source']}
      style={{ marginTop: 16 }}
    />
  );
};

export default PredictionBasisDisplay;
