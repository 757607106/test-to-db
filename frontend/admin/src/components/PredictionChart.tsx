/**
 * PredictionChart 组件
 * P2功能：预测结果可视化图表
 */
import React, { useState } from 'react';
import {
  Card,
  Space,
  Typography,
  Tag,
  Switch,
  Statistic,
  Row,
  Col,
  Divider,
  Tooltip,
  Button,
  Collapse,
  Alert,
  Steps,
} from 'antd';
import {
  LineChartOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  InfoCircleOutlined,
  DownloadOutlined,
  QuestionCircleOutlined,
  BulbOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart,
  ReferenceLine,
} from 'recharts';
import type { PredictionResult, PredictionDataPoint } from '../types/prediction';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface PredictionChartProps {
  result: PredictionResult;
  showConfidenceInterval?: boolean;
  onExport?: () => void;
  className?: string;
}

export const PredictionChart: React.FC<PredictionChartProps> = ({
  result,
  showConfidenceInterval: initialShowCI = true,
  onExport,
  className,
}) => {
  const [showConfidenceInterval, setShowConfidenceInterval] = useState(initialShowCI);

  // 合并历史数据和预测数据
  const chartData = [
    ...result.historicalData.map((p) => ({
      date: p.date,
      历史值: p.value,
      预测值: null as number | null,
      置信上界: null as number | null,
      置信下界: null as number | null,
    })),
    ...result.predictions.map((p) => ({
      date: p.date,
      历史值: null as number | null,
      预测值: p.value,
      置信上界: p.upperBound,
      置信下界: p.lowerBound,
    })),
  ];

  // 连接历史数据和预测数据的最后/第一个点
  if (result.historicalData.length > 0 && result.predictions.length > 0) {
    const lastHistorical = result.historicalData[result.historicalData.length - 1];
    const firstPrediction = result.predictions[0];
    
    // 在预测数据的第一个点也显示历史值，形成连接
    const connectionIndex = result.historicalData.length;
    if (chartData[connectionIndex]) {
      chartData[connectionIndex].历史值 = lastHistorical.value;
    }
  }

  const getTrendIcon = () => {
    switch (result.trendAnalysis.direction) {
      case 'up':
        return <ArrowUpOutlined style={{ color: '#52c41a' }} />;
      case 'down':
        return <ArrowDownOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <MinusOutlined style={{ color: '#faad14' }} />;
    }
  };

  const getTrendColor = () => {
    switch (result.trendAnalysis.direction) {
      case 'up':
        return '#52c41a';
      case 'down':
        return '#ff4d4f';
      default:
        return '#faad14';
    }
  };

  const getMethodLabel = () => {
    switch (result.methodUsed) {
      case 'linear':
        return '线性回归';
      case 'moving_average':
        return '移动平均';
      case 'exponential_smoothing':
        return '指数平滑';
      default:
        return '自动选择';
    }
  };

  return (
    <Card
      className={className}
      style={{
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <LineChartOutlined style={{ fontSize: 20, color: '#6366f1' }} />
          <Title level={5} style={{ margin: 0 }}>预测分析结果</Title>
          <Tag color="purple">{getMethodLabel()}</Tag>
        </div>
        <Space>
          <span style={{ fontSize: 12, color: '#666' }}>显示置信区间</span>
          <Switch
            size="small"
            checked={showConfidenceInterval}
            onChange={setShowConfidenceInterval}
          />
          {onExport && (
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={onExport}
            >
              导出
            </Button>
          )}
        </Space>
      </div>

      {/* 趋势指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
            <Statistic
              title={
                <span>
                  趋势方向 {getTrendIcon()}
                </span>
              }
              value={
                result.trendAnalysis.direction === 'up'
                  ? '上升'
                  : result.trendAnalysis.direction === 'down'
                  ? '下降'
                  : '平稳'
              }
              valueStyle={{ color: getTrendColor(), fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
            <Statistic
              title="增长率"
              value={result.trendAnalysis.growthRate}
              precision={2}
              suffix="%"
              valueStyle={{
                color: result.trendAnalysis.growthRate >= 0 ? '#52c41a' : '#ff4d4f',
                fontSize: 18,
              }}
              prefix={result.trendAnalysis.growthRate >= 0 ? '+' : ''}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
            <Statistic
              title={
                <span>
                  预测误差 (MAPE)
                  <Tooltip title="平均绝对百分比误差，越小越好">
                    <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
                  </Tooltip>
                </span>
              }
              value={result.accuracyMetrics.mape}
              precision={2}
              suffix="%"
              valueStyle={{
                color: result.accuracyMetrics.mape < 10 ? '#52c41a' : result.accuracyMetrics.mape < 20 ? '#faad14' : '#ff4d4f',
                fontSize: 18,
              }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
            <Statistic
              title="波动率"
              value={result.trendAnalysis.volatility}
              precision={2}
              suffix="%"
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表 */}
      <div style={{ height: 350 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#e0e0e0' }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#e0e0e0' }}
              domain={['auto', 'auto']}
            />
            <RechartsTooltip
              contentStyle={{
                background: 'rgba(255,255,255,0.96)',
                border: '1px solid #e0e0e0',
                borderRadius: 8,
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}
              formatter={(value: any, name: any) => {
                if (value === null) return ['-', name];
                return [typeof value === 'number' ? value.toLocaleString() : value, name];
              }}
            />
            <Legend />
            
            {/* 置信区间 */}
            {showConfidenceInterval && (
              <Area
                type="monotone"
                dataKey="置信上界"
                stroke="none"
                fill="#6366f1"
                fillOpacity={0.1}
                connectNulls={false}
              />
            )}
            {showConfidenceInterval && (
              <Area
                type="monotone"
                dataKey="置信下界"
                stroke="none"
                fill="#fff"
                fillOpacity={1}
                connectNulls={false}
              />
            )}

            {/* 历史数据线 */}
            <Line
              type="monotone"
              dataKey="历史值"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6', strokeWidth: 0, r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />

            {/* 预测数据线 */}
            <Line
              type="monotone"
              dataKey="预测值"
              stroke="#8b5cf6"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ fill: '#8b5cf6', strokeWidth: 0, r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls={false}
            />

            {/* 分界线 */}
            {result.historicalData.length > 0 && (
              <ReferenceLine
                x={result.historicalData[result.historicalData.length - 1].date}
                stroke="#999"
                strokeDasharray="3 3"
                label={{
                  value: '预测起点',
                  position: 'top',
                  fill: '#666',
                  fontSize: 11,
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* 图例说明 */}
      <Divider style={{ margin: '16px 0' }} />
      <div style={{ display: 'flex', justifyContent: 'center', gap: 24 }}>
        <Space size={4}>
          <div style={{ width: 20, height: 3, background: '#3b82f6', borderRadius: 2 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>历史数据</Text>
        </Space>
        <Space size={4}>
          <div style={{ width: 20, height: 3, background: '#8b5cf6', borderRadius: 2, borderStyle: 'dashed' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>预测数据</Text>
        </Space>
        {showConfidenceInterval && (
          <Space size={4}>
            <div style={{ width: 20, height: 10, background: 'rgba(99, 102, 241, 0.1)', borderRadius: 2 }} />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {Math.round((result.predictions[0]?.upperBound ? 0.95 : 0) * 100)}% 置信区间
            </Text>
          </Space>
        )}
      </div>

      {/* 详细统计 */}
      <Divider style={{ margin: '16px 0' }} />
      <Row gutter={16}>
        <Col span={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>历史平均值</Text>
          <div>
            <Text strong>{result.trendAnalysis.averageValue.toLocaleString()}</Text>
          </div>
        </Col>
        <Col span={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>历史最小值</Text>
          <div>
            <Text strong>{result.trendAnalysis.minValue.toLocaleString()}</Text>
          </div>
        </Col>
        <Col span={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>历史最大值</Text>
          <div>
            <Text strong>{result.trendAnalysis.maxValue.toLocaleString()}</Text>
          </div>
        </Col>
      </Row>

      {/* 预测依据区块 - 新增 */}
      {(result.explanation || result.methodSelectionReason) && (
        <>
          <Divider style={{ margin: '20px 0' }} />
          <Collapse
            defaultActiveKey={['explanation']}
            bordered={false}
            style={{ background: '#f8fafc', borderRadius: 8 }}
          >
            {/* 预测方法与依据 */}
            <Panel
              header={
                <Space>
                  <BulbOutlined style={{ color: '#6366f1' }} />
                  <Text strong>预测依据与公式</Text>
                </Space>
              }
              key="explanation"
            >
              {/* 方法选择理由 */}
              {result.methodSelectionReason && (
                <div style={{ marginBottom: 16 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>方法选择理由</Text>
                  <Alert
                    type="info"
                    message={result.methodSelectionReason.reason}
                    style={{ marginTop: 8 }}
                    showIcon
                    icon={<ExperimentOutlined />}
                  />
                  {/* 方法评分 */}
                  {Object.keys(result.methodSelectionReason.methodScores).length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>方法评分对比：</Text>
                      <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                        {Object.entries(result.methodSelectionReason.methodScores).map(([method, score]) => {
                          const methodNames: Record<string, string> = {
                            linear: '线性回归',
                            moving_average: '移动平均',
                            exponential_smoothing: '指数平滑',
                          };
                          const isSelected = method === result.methodSelectionReason?.selectedMethod;
                          return (
                            <Tag
                              key={method}
                              color={isSelected ? 'purple' : 'default'}
                              style={{ margin: 0 }}
                            >
                              {methodNames[method] || method}: {(score as number).toFixed(1)}分
                              {isSelected && ' ✓'}
                            </Tag>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 预测公式 */}
              {result.explanation && (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>算法原理</Text>
                    <div style={{ marginTop: 4, padding: 12, background: '#fff', borderRadius: 6, border: '1px solid #e0e0e0' }}>
                      <Text>{result.explanation.methodExplanation}</Text>
                    </div>
                  </div>

                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>计算公式</Text>
                    <div style={{ marginTop: 4, padding: 12, background: '#1e1e1e', borderRadius: 6, fontFamily: 'monospace' }}>
                      <Text style={{ color: '#d4d4d4' }}>{result.explanation.formulaUsed}</Text>
                    </div>
                  </div>

                  {/* 关键参数 */}
                  {Object.keys(result.explanation.keyParameters).length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>关键参数</Text>
                      <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                        {Object.entries(result.explanation.keyParameters).map(([key, value]) => (
                          <Tag key={key} color="blue">
                            {key}: {typeof value === 'number' ? value.toFixed(4) : String(value)}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 计算步骤 */}
                  {result.explanation.calculationSteps.length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>计算步骤</Text>
                      <Steps
                        direction="vertical"
                        size="small"
                        current={result.explanation.calculationSteps.length}
                        style={{ marginTop: 8 }}
                        items={result.explanation.calculationSteps.map((step, idx) => ({
                          title: `步骤 ${idx + 1}`,
                          description: step,
                          status: 'finish' as const,
                        }))}
                      />
                    </div>
                  )}

                  {/* 置信区间解释 */}
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>置信区间说明</Text>
                    <div style={{ marginTop: 4, padding: 12, background: '#fff', borderRadius: 6, border: '1px solid #e0e0e0' }}>
                      <Text>{result.explanation.confidenceExplanation}</Text>
                    </div>
                  </div>

                  {/* 可靠性评估 */}
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>可靠性评估</Text>
                    <Alert
                      type={result.accuracyMetrics.mape < 20 ? 'success' : result.accuracyMetrics.mape < 50 ? 'warning' : 'error'}
                      message={result.explanation.reliabilityAssessment}
                      style={{ marginTop: 8 }}
                      showIcon
                      icon={result.accuracyMetrics.mape < 20 ? <CheckCircleOutlined /> : <WarningOutlined />}
                    />
                  </div>
                </>
              )}
            </Panel>

            {/* 数据质量信息 */}
            {result.dataQuality && (
              <Panel
                header={
                  <Space>
                    <InfoCircleOutlined style={{ color: '#6366f1' }} />
                    <Text strong>数据质量报告</Text>
                  </Space>
                }
                key="dataQuality"
              >
                <Row gutter={[16, 16]}>
                  <Col span={8}>
                    <Statistic
                      title="原始数据点"
                      value={result.dataQuality.totalPoints}
                      suffix="个"
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="有效数据点"
                      value={result.dataQuality.validPoints}
                      suffix="个"
                      valueStyle={{ color: result.dataQuality.validPoints === result.dataQuality.totalPoints ? '#52c41a' : '#faad14' }}
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="数据间隔"
                      value={result.dataQuality.dateInterval || '未检测'}
                    />
                  </Col>
                  {result.dataQuality.missingCount > 0 && (
                    <Col span={12}>
                      <Text type="secondary">缺失值处理：</Text>
                      <Tag color="orange">
                        {result.dataQuality.missingCount}个缺失值，使用{result.dataQuality.missingFilledMethod || '前向填充'}填充
                      </Tag>
                    </Col>
                  )}
                  {result.dataQuality.outlierCount > 0 && (
                    <Col span={12}>
                      <Text type="secondary">异常值检测：</Text>
                      <Tag color="red">检测到{result.dataQuality.outlierCount}个异常点</Tag>
                    </Col>
                  )}
                </Row>
              </Panel>
            )}
          </Collapse>
        </>
      )}
    </Card>
  );
};

export default PredictionChart;
