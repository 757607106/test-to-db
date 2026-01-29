/**
 * CategoricalAnalysisDisplay 组件
 * P2功能：分类统计分析结果展示
 */
import React from 'react';
import {
  Card,
  Typography,
  Table,
  Tag,
  Statistic,
  Row,
  Col,
  Tooltip,
  Alert,
  Divider,
  Progress,
  Collapse,
} from 'antd';
import {
  BarChartOutlined,
  PieChartOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import type { CategoricalAnalysisResult, CategoryStatistics, OutlierInfo } from '../types/prediction';

const { Text } = Typography;

interface CategoricalAnalysisDisplayProps {
  result: CategoricalAnalysisResult;
}

export const CategoricalAnalysisDisplay: React.FC<CategoricalAnalysisDisplayProps> = ({ result }) => {
  // 分类统计表格列定义
  const statsColumns = [
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 100,
      ellipsis: true,
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 60,
      sorter: (a: CategoryStatistics, b: CategoryStatistics) => a.count - b.count,
    },
    {
      title: '总和',
      dataIndex: 'sum',
      key: 'sum',
      width: 80,
      render: (val: number) => val?.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) ?? '-',
      sorter: (a: CategoryStatistics, b: CategoryStatistics) => (a.sum ?? 0) - (b.sum ?? 0),
    },
    {
      title: '均值',
      dataIndex: 'mean',
      key: 'mean',
      width: 80,
      render: (val: number) => val?.toFixed(2) ?? '-',
      sorter: (a: CategoryStatistics, b: CategoryStatistics) => (a.mean ?? 0) - (b.mean ?? 0),
    },
    {
      title: '占比',
      dataIndex: 'pct_of_total',
      key: 'pct_of_total',
      width: 100,
      render: (val: number) => (
        <Progress 
          percent={val} 
          size="small" 
          format={(pct) => `${pct?.toFixed(1)}%`}
          strokeColor={{
            '0%': '#6366f1',
            '100%': '#10b981',
          }}
        />
      ),
      sorter: (a: CategoryStatistics, b: CategoryStatistics) => a.pct_of_total - b.pct_of_total,
    },
  ];

  // 异常值表格列定义
  const outlierColumns = [
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: '数值',
      dataIndex: 'value',
      key: 'value',
      render: (val: number) => val?.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) ?? '-',
    },
    {
      title: 'Z-Score',
      dataIndex: 'z_score',
      key: 'z_score',
      render: (val: number) => (
        <Tag color={Math.abs(val ?? 0) > 3 ? 'red' : 'orange'}>
          {val?.toFixed(2) ?? '-'}
        </Tag>
      ),
    },
    {
      title: '偏离度',
      dataIndex: 'deviation_pct',
      key: 'deviation_pct',
      render: (val: number) => val != null ? `${val.toFixed(1)}%` : '-',
    },
  ];

  // 正态性判断提示
  const normalityStatus = result.distribution.is_normal;
  const significantDiff = result.comparison.significant_difference;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 分析摘要 */}
      <Alert
        type="info"
        message="分析摘要"
        description={result.summary}
        showIcon
        icon={<BarChartOutlined />}
      />

      {/* 总体统计 */}
      <Card size="small" title={<><InfoCircleOutlined /> 总体统计</>}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="总记录数" value={result.total_records} />
          </Col>
          <Col span={6}>
            <Statistic title="分类数" value={result.category_count} />
          </Col>
          <Col span={6}>
            <Statistic 
              title="总和" 
              value={result.total_sum} 
              precision={2}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
          <Col span={6}>
            <Statistic 
              title="总体均值" 
              value={result.overall_mean} 
              precision={2}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
        </Row>
      </Card>

      {/* 分布特征 & 分类比较 */}
      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" title="分布特征">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">偏度 (Skewness):</Text>
                <Tooltip title={
                  (result.distribution?.skewness ?? 0) > 0.5 
                    ? '正偏态：数据向右倾斜' 
                    : (result.distribution?.skewness ?? 0) < -0.5 
                      ? '负偏态：数据向左倾斜'
                      : '近似对称分布'
                }>
                  <Text strong>{result.distribution?.skewness?.toFixed(3) ?? '-'}</Text>
                </Tooltip>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">峰度 (Kurtosis):</Text>
                <Tooltip title={
                  (result.distribution?.kurtosis ?? 0) > 0 
                    ? '尖峰：数据集中于均值附近' 
                    : '平峰：数据分布较分散'
                }>
                  <Text strong>{result.distribution?.kurtosis?.toFixed(3) ?? '-'}</Text>
                </Tooltip>
              </div>
              <Divider style={{ margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text type="secondary">正态性检验:</Text>
                <Tag 
                  color={normalityStatus ? 'green' : 'orange'}
                  icon={normalityStatus ? <CheckCircleOutlined /> : <WarningOutlined />}
                >
                  {normalityStatus ? '符合正态分布' : '非正态分布'}
                </Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Shapiro-Wilk p值: {result.distribution?.normality_pvalue?.toFixed(4) ?? '-'}
              </Text>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="分类比较">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">最高分类:</Text>
                <Tag color="green">{result.comparison.top_category}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">最低分类:</Text>
                <Tag color="red">{result.comparison.bottom_category}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">极差比:</Text>
                <Text strong>{result.comparison?.range_ratio?.toFixed(2) ?? '-'}x</Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">变异系数 (CV):</Text>
                <Text strong>{result.comparison?.cv != null ? ((result.comparison.cv * 100).toFixed(1) + '%') : '-'}</Text>
              </div>
              <Divider style={{ margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Tooltip title="ANOVA单因素方差分析检验分类间是否存在显著差异">
                  <Text type="secondary">ANOVA检验:</Text>
                </Tooltip>
                <Tag 
                  color={significantDiff ? 'red' : 'blue'}
                  icon={significantDiff ? <WarningOutlined /> : <CheckCircleOutlined />}
                >
                  {significantDiff ? '存在显著差异' : '无显著差异'}
                </Tag>
              </div>
              {result.comparison?.anova_pvalue != null && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  F={result.comparison.anova_fvalue?.toFixed(2) ?? '-'}, p={result.comparison.anova_pvalue?.toFixed(4) ?? '-'}
                </Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 各分类统计详情 */}
      <Card 
        size="small" 
        title={<><PieChartOutlined /> 各分类统计详情</>}
      >
        <Table
          dataSource={result.category_stats}
          columns={statsColumns}
          rowKey="category"
          size="small"
          pagination={result.category_stats.length > 10 ? { pageSize: 10 } : false}
          scroll={{ x: 420 }}
        />
      </Card>

      {/* 异常值检测 */}
      {result.outliers.length > 0 && (
        <Card 
          size="small" 
          title={
            <span style={{ color: '#fa8c16' }}>
              <WarningOutlined /> 异常值检测 ({result.outliers.length}个)
            </span>
          }
        >
          <Alert
            type="warning"
            message={`检测到 ${result.outliers.length} 个异常数据点 (Z-score > 2.5)`}
            style={{ marginBottom: 12 }}
            showIcon
          />
          <Table
            dataSource={result.outliers}
            columns={outlierColumns}
            rowKey={(record: OutlierInfo, index) => `${record.category}-${index}`}
            size="small"
            pagination={result.outliers.length > 5 ? { pageSize: 5 } : false}
          />
        </Card>
      )}

      {/* 分析方法说明 */}
      <Collapse
        size="small"
        items={[{
          key: 'methodology',
          label: <span><QuestionCircleOutlined /> 分析方法说明</span>,
          children: (
            <div style={{ fontSize: 13, lineHeight: 1.8 }}>
              <Text strong>本分析采用以下统计方法：</Text>
              <Divider style={{ margin: '8px 0' }} />
              
              <Text strong>1. 描述性统计</Text>
              <ul style={{ margin: '4px 0 12px 16px', padding: 0 }}>
                <li><Text type="secondary">均值：各分类数值的算术平均，公式 μ = Σx / n</Text></li>
                <li><Text type="secondary">总和：各分类数值的累加求和</Text></li>
                <li><Text type="secondary">占比：各分类总和占整体的百分比</Text></li>
              </ul>

              <Text strong>2. 分布特征分析</Text>
              <ul style={{ margin: '4px 0 12px 16px', padding: 0 }}>
                <li><Text type="secondary">偏度(Skewness)：衡量数据分布的对称性，|偏度| {'>'} 0.5 表示明显偏斜</Text></li>
                <li><Text type="secondary">峰度(Kurtosis)：衡量数据分布的尖锐程度，{'>'} 0 为尖峰，{'<'} 0 为平峰</Text></li>
                <li><Text type="secondary">Shapiro-Wilk检验：检验数据是否符合正态分布，p值 {'>'} 0.05 表示符合正态分布</Text></li>
              </ul>

              <Text strong>3. 分类比较分析</Text>
              <ul style={{ margin: '4px 0 12px 16px', padding: 0 }}>
                <li><Text type="secondary">极差比：最高分类均值 / 最低分类均值，反映分类间差距</Text></li>
                <li><Text type="secondary">变异系数(CV)：标准差 / 均值 × 100%，衡量数据离散程度</Text></li>
                <li><Text type="secondary">ANOVA检验：单因素方差分析，检验各分类间是否存在统计学显著差异（p {'<'} 0.05 表示显著）</Text></li>
              </ul>

              <Text strong>4. 异常值检测</Text>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                <li><Text type="secondary">Z-Score方法：Z = (x - μ) / σ，|Z| {'>'} 2.5 判定为异常值</Text></li>
                <li><Text type="secondary">偏离度：异常值与均值的百分比偏差</Text></li>
              </ul>
            </div>
          ),
        }]}
      />

      {/* 生成时间 */}
      <div style={{ textAlign: 'right' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          分析时间: {result.generated_at}
        </Text>
      </div>
    </div>
  );
};

export default CategoricalAnalysisDisplay;
