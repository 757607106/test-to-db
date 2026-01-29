/**
 * PredictionConfigPanel 组件
 * P2功能：预测分析配置面板（支持时序预测和分类统计分析）
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
  Switch,
  Tabs,
} from 'antd';
import {
  LineChartOutlined,
  PieChartOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import type { 
  PredictionRequest, 
  PredictionColumnsResponse, 
  PredictionMethod,
  CategoricalAnalysisRequest,
} from '../types/prediction';

const { Text, Title } = Typography;
const { Option } = Select;

interface PredictionConfigPanelProps {
  widgetId: number;
  dashboardId: number;
  columnsData?: PredictionColumnsResponse;
  onPredict: (config: PredictionRequest) => void;
  onAnalyzeCategorical?: (config: CategoricalAnalysisRequest) => void;
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
  onAnalyzeCategorical,
  onLoadColumns,
  isLoading,
  className,
}) => {
  const [form] = Form.useForm();
  const [categoricalForm] = Form.useForm();
  const [columnsData, setColumnsData] = useState<PredictionColumnsResponse | null>(initialColumnsData || null);
  const [loadingColumns, setLoadingColumns] = useState(false);
  const [analysisType, setAnalysisType] = useState<'time_series' | 'categorical'>('time_series');

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
      
      // 根据建议的分析类型设置默认值
      if (data.suggestedAnalysis === 'categorical') {
        setAnalysisType('categorical');
        if (data.categoryColumns.length > 0) {
          categoricalForm.setFieldValue('categoryColumn', data.categoryColumns[0]);
        }
        if (data.valueColumns.length > 0) {
          categoricalForm.setFieldValue('valueColumn', data.valueColumns[0]);
        }
      } else {
        setAnalysisType('time_series');
        // 自动选择第一个可用列
        if (data.dateColumns.length > 0) {
          form.setFieldValue('dateColumn', data.dateColumns[0]);
        }
        if (data.valueColumns.length > 0) {
          form.setFieldValue('valueColumn', data.valueColumns[0]);
        }
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

  const handleCategoricalSubmit = (values: any) => {
    if (!onAnalyzeCategorical) return;
    const config: CategoricalAnalysisRequest = {
      widgetId,
      categoryColumn: values.categoryColumn,
      valueColumn: values.valueColumn,
      includeOutliers: values.includeOutliers ?? true,
    };
    onAnalyzeCategorical(config);
  };

  if (loadingColumns) {
    return (
      <Card className={className} style={{ textAlign: 'center', padding: 40 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16, color: '#666' }}>加载数据列信息...</div>
      </Card>
    );
  }

  // 判断可用的分析类型
  const hasTimeSeriesData = columnsData && columnsData.dateColumns.length > 0 && columnsData.valueColumns.length > 0;
  const hasCategoricalData = columnsData && columnsData.categoryColumns.length > 0 && columnsData.valueColumns.length > 0;
  const suggestedAnalysis = columnsData?.suggestedAnalysis || 'none';
  
  // 完全无法分析的情况
  if (!hasTimeSeriesData && !hasCategoricalData) {
    return (
      <Card className={className}>
        <Alert
          type="warning"
          message="无法进行分析"
          description="当前Widget数据不包含可分析的列组合。需要：时间列+数值列（用于时序预测）或 分类列+数值列（用于分类统计分析）。"
          showIcon
        />
      </Card>
    );
  }

  // 时序预测配置表单
  const renderTimeSeriesForm = () => (
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
          {columnsData?.dateColumns.map((col) => (
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
          {columnsData?.valueColumns.map((col) => (
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
  );

  // 分类统计分析配置表单
  const renderCategoricalForm = () => (
    <Form
      form={categoricalForm}
      layout="vertical"
      onFinish={handleCategoricalSubmit}
      initialValues={{
        includeOutliers: true,
      }}
    >
      <Form.Item
        name="categoryColumn"
        label="分类列"
        rules={[{ required: true, message: '请选择分类列' }]}
        tooltip="用于分组的分类字段"
      >
        <Select placeholder="选择分类列">
          {columnsData?.categoryColumns.map((col) => (
            <Option key={col} value={col}>
              {col}
            </Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item
        name="valueColumn"
        label="分析数值列"
        rules={[{ required: true, message: '请选择数值列' }]}
        tooltip="用于统计分析的数值字段"
      >
        <Select placeholder="选择数值列">
          {columnsData?.valueColumns.map((col) => (
            <Option key={col} value={col}>
              {col}
            </Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item
        name="includeOutliers"
        label="异常值检测"
        valuePropName="checked"
        tooltip="使用Z-score方法检测异常数据点"
      >
        <Switch checkedChildren="开启" unCheckedChildren="关闭" />
      </Form.Item>

      <Alert
        type="info"
        message="分类统计分析"
        description="将对各分类进行描述性统计（均值、标准差、中位数等）、分布分析、ANOVA检验及异常值检测。"
        style={{ marginBottom: 16 }}
        showIcon
      />

      <Form.Item style={{ marginBottom: 0 }}>
        <Button
          type="primary"
          htmlType="submit"
          loading={isLoading}
          icon={<BarChartOutlined />}
          block
          disabled={!onAnalyzeCategorical}
          style={{
            height: 44,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            border: 'none',
          }}
        >
          {isLoading ? '分析中...' : '开始分析'}
        </Button>
      </Form.Item>
    </Form>
  );

  // 构建Tab项
  const tabItems = [];
  if (hasTimeSeriesData) {
    tabItems.push({
      key: 'time_series',
      label: (
        <span>
          <LineChartOutlined /> 时序预测
          {suggestedAnalysis === 'time_series' && <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>推荐</Tag>}
        </span>
      ),
      children: renderTimeSeriesForm(),
    });
  }
  if (hasCategoricalData) {
    tabItems.push({
      key: 'categorical',
      label: (
        <span>
          <PieChartOutlined /> 分类分析
          {suggestedAnalysis === 'categorical' && <Tag color="green" style={{ marginLeft: 4, fontSize: 10 }}>推荐</Tag>}
        </span>
      ),
      children: renderCategoricalForm(),
    });
  }

  return (
    <Card
      className={className}
      style={{
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {analysisType === 'time_series' ? (
          <LineChartOutlined style={{ fontSize: 20, color: '#6366f1' }} />
        ) : (
          <PieChartOutlined style={{ fontSize: 20, color: '#10b981' }} />
        )}
        <Title level={5} style={{ margin: 0 }}>数据分析配置</Title>
      </div>

      {tabItems.length > 1 ? (
        <Tabs
          activeKey={analysisType}
          onChange={(key) => setAnalysisType(key as 'time_series' | 'categorical')}
          items={tabItems}
          size="small"
        />
      ) : (
        // 只有一种分析类型时直接显示
        tabItems[0]?.children
      )}
    </Card>
  );
};

export default PredictionConfigPanel;
