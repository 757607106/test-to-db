/**
 * PredictionConfigPanel 组件
 * P2功能：预测分析配置面板
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Select,
  InputNumber,
  Button,
  Space,
  Typography,
  Slider,
  Tag,
  Spin,
  Alert,
} from 'antd';
import {
  LineChartOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { PredictionRequest, PredictionColumnsResponse, PredictionMethod } from '../types/prediction';

const { Text, Title } = Typography;
const { Option } = Select;

interface PredictionConfigPanelProps {
  widgetId: number;
  dashboardId: number;
  columnsData?: PredictionColumnsResponse;
  onPredict: (config: PredictionRequest) => void;
  onLoadColumns: () => Promise<PredictionColumnsResponse>;
  isLoading: boolean;
  className?: string;
}

const methodOptions: { value: PredictionMethod; label: string; description: string }[] = [
  { value: 'auto', label: '自动选择', description: '根据数据特征自动选择最佳算法' },
  { value: 'linear', label: '线性回归', description: '适用于有明显趋势的数据' },
  { value: 'moving_average', label: '移动平均', description: '适用于波动较大的数据' },
  { value: 'exponential_smoothing', label: '指数平滑', description: '适用于需要近期数据权重更高的场景' },
];

export const PredictionConfigPanel: React.FC<PredictionConfigPanelProps> = ({
  widgetId,
  dashboardId,
  columnsData: initialColumnsData,
  onPredict,
  onLoadColumns,
  isLoading,
  className,
}) => {
  const [form] = Form.useForm();
  const [columnsData, setColumnsData] = useState<PredictionColumnsResponse | null>(initialColumnsData || null);
  const [loadingColumns, setLoadingColumns] = useState(false);

  useEffect(() => {
    if (!initialColumnsData) {
      loadColumns();
    }
  }, [widgetId]);

  const loadColumns = async () => {
    setLoadingColumns(true);
    try {
      const data = await onLoadColumns();
      setColumnsData(data);
      
      // 自动选择第一个可用列
      if (data.dateColumns.length > 0) {
        form.setFieldValue('dateColumn', data.dateColumns[0]);
      }
      if (data.valueColumns.length > 0) {
        form.setFieldValue('valueColumn', data.valueColumns[0]);
      }
    } catch (error) {
      console.error('加载列信息失败:', error);
    } finally {
      setLoadingColumns(false);
    }
  };

  const handleSubmit = (values: any) => {
    const config: PredictionRequest = {
      widgetId,
      dateColumn: values.dateColumn,
      valueColumn: values.valueColumn,
      periods: values.periods || 7,
      method: values.method || 'auto',
      confidenceLevel: (values.confidenceLevel || 95) / 100,
    };
    onPredict(config);
  };

  if (loadingColumns) {
    return (
      <Card className={className} style={{ textAlign: 'center', padding: 40 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>加载数据列信息...</div>
      </Card>
    );
  }

  // 修复判断逻辑：时间列和数值列缺一不可
  const missingDateColumns = !columnsData || columnsData.dateColumns.length === 0;
  const missingValueColumns = !columnsData || columnsData.valueColumns.length === 0;
  
  if (missingDateColumns || missingValueColumns) {
    // 生成更清晰的错误提示
    let missingParts: string[] = [];
    if (missingDateColumns) missingParts.push('时间列');
    if (missingValueColumns) missingParts.push('数值列');
    
    return (
      <Card className={className}>
        <Alert
          type="warning"
          message="无法进行预测"
          description={`当前Widget没有可用于预测的${missingParts.join('和')}。请确保数据包含日期/时间列（如"日期"、"月份"等）和数值列（如"销售额"、"数量"等）。`}
          showIcon
        />
      </Card>
    );
  }

  return (
    <Card
      className={className}
      style={{
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        <LineChartOutlined style={{ fontSize: 20, color: '#6366f1' }} />
        <Title level={5} style={{ margin: 0 }}>预测配置</Title>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          periods: 7,
          method: 'auto',
          confidenceLevel: 95,
        }}
      >
        <Form.Item
          name="dateColumn"
          label="时间列"
          rules={[{ required: true, message: '请选择时间列' }]}
        >
          <Select placeholder="选择时间列">
            {columnsData.dateColumns.map((col) => (
              <Option key={col} value={col}>
                {col}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="valueColumn"
          label="预测目标列"
          rules={[{ required: true, message: '请选择预测目标列' }]}
        >
          <Select placeholder="选择数值列">
            {columnsData.valueColumns.map((col) => (
              <Option key={col} value={col}>
                {col}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="periods"
          label="预测周期数"
          tooltip="预测未来多少个时间点"
        >
          <Space.Compact style={{ width: '100%' }}>
            <InputNumber
              min={1}
              max={365}
              style={{ width: 'calc(100% - 70px)' }}
            />
            <Button disabled style={{ width: '70px', cursor: 'default', color: 'rgba(0, 0, 0, 0.45)', backgroundColor: '#fafafa', borderColor: '#d9d9d9' }}>个周期</Button>
          </Space.Compact>
        </Form.Item>

        <Form.Item
          name="method"
          label="预测方法"
        >
          <Select>
            {methodOptions.map((opt) => (
              <Option key={opt.value} value={opt.value}>
                <div>
                  <Text strong>{opt.label}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {opt.description}
                  </Text>
                </div>
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="confidenceLevel"
          label={
            <span>
              置信水平 <Tag color="blue">{form.getFieldValue('confidenceLevel') || 95}%</Tag>
            </span>
          }
        >
          <Slider
            min={50}
            max={99}
            marks={{
              50: '50%',
              75: '75%',
              95: '95%',
              99: '99%',
            }}
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            htmlType="submit"
            loading={isLoading}
            icon={<ThunderboltOutlined />}
            block
            style={{
              height: 44,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
              border: 'none',
            }}
          >
            {isLoading ? '预测中...' : '开始预测'}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default PredictionConfigPanel;
