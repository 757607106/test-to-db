/**
 * 库存分析统计卡片组件
 * 顶部汇总统计数据展示
 */
import React from 'react';
import { Card, Statistic, Row, Col, Tooltip, Progress } from 'antd';
import {
  ShoppingCartOutlined,
  DollarOutlined,
  RiseOutlined,
  SafetyOutlined,
  UserOutlined,
  WarningOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import {
  ABCXYZSummary,
  TurnoverSummary,
  SafetyStockSummary,
  SupplierSummary,
} from '../types/inventoryAnalysis';

interface InventoryStatsCardsProps {
  analysisType: 'abc_xyz' | 'turnover' | 'safety_stock' | 'supplier_eval';
  data: ABCXYZSummary | TurnoverSummary | SafetyStockSummary | SupplierSummary;
}

/** ABC-XYZ 分析统计卡片 */
const ABCXYZStatsCards: React.FC<{ data: ABCXYZSummary }> = ({ data }) => {
  const formatValue = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toFixed(0);
  };

  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="总产品数"
            value={data.total_products}
            prefix={<ShoppingCartOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="总价值"
            value={formatValue(data.total_value)}
            prefix={<DollarOutlined />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Tooltip title={`A类产品 ${data.a_class.count} 个，占 ${data.a_class.product_pct}% 产品，贡献 ${data.a_class.pct}% 价值`}>
          <Card size="small" style={{ borderLeft: '3px solid #52c41a' }}>
            <Statistic
              title="A类占比"
              value={data.a_class.pct}
              suffix="%"
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
            <Progress
              percent={data.a_class.pct}
              showInfo={false}
              strokeColor="#52c41a"
              size="small"
            />
          </Card>
        </Tooltip>
      </Col>
      <Col span={6}>
        <Tooltip title={`C类产品 ${data.c_class.count} 个，占 ${data.c_class.product_pct}% 产品，仅贡献 ${data.c_class.pct}% 价值`}>
          <Card size="small" style={{ borderLeft: '3px solid #ff4d4f' }}>
            <Statistic
              title="C类占比"
              value={data.c_class.pct}
              suffix="%"
              prefix={<WarningOutlined style={{ color: '#ff4d4f' }} />}
              valueStyle={{ color: '#ff4d4f' }}
            />
            <Progress
              percent={data.c_class.pct}
              showInfo={false}
              strokeColor="#ff4d4f"
              size="small"
            />
          </Card>
        </Tooltip>
      </Col>
    </Row>
  );
};

/** 周转率分析统计卡片 */
const TurnoverStatsCards: React.FC<{ data: TurnoverSummary }> = ({ data }) => {
  const healthRate = (data.good_count / data.total_products * 100).toFixed(1);
  
  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="总产品数"
            value={data.total_products}
            prefix={<ShoppingCartOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="平均周转率"
            value={data.avg_turnover_rate}
            precision={2}
            prefix={<RiseOutlined />}
            suffix="次/年"
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="平均库存天数"
            value={data.avg_days_in_inventory}
            precision={1}
            suffix="天"
            valueStyle={{ 
              color: data.avg_days_in_inventory <= 30 ? '#52c41a' : 
                     data.avg_days_in_inventory <= 90 ? '#faad14' : '#ff4d4f' 
            }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Tooltip title={`健康: ${data.good_count}, 警告: ${data.warning_count}, 严重: ${data.critical_count}`}>
          <Card size="small">
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: '#999' }}>健康度分布</span>
            </div>
            <Progress
              percent={100}
              success={{ percent: Number(healthRate) }}
              format={() => `${healthRate}%`}
              size="small"
            />
            <Row style={{ marginTop: 4, fontSize: 12 }}>
              <Col span={8} style={{ color: '#52c41a' }}>{data.good_count}健康</Col>
              <Col span={8} style={{ color: '#faad14' }}>{data.warning_count}警告</Col>
              <Col span={8} style={{ color: '#ff4d4f' }}>{data.critical_count}严重</Col>
            </Row>
          </Card>
        </Tooltip>
      </Col>
    </Row>
  );
};

/** 安全库存统计卡片 */
const SafetyStockStatsCards: React.FC<{ data: SafetyStockSummary }> = ({ data }) => {
  const formatValue = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toFixed(0);
  };

  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="总产品数"
            value={data.total_products}
            prefix={<ShoppingCartOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="安全库存总量"
            value={formatValue(data.total_safety_stock)}
            prefix={<SafetyOutlined />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="再订货点总量"
            value={formatValue(data.total_reorder_point)}
            prefix={<RiseOutlined />}
            valueStyle={{ color: '#faad14' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="服务水平"
            value={data.service_level}
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
    </Row>
  );
};

/** 供应商评估统计卡片 */
const SupplierStatsCards: React.FC<{ data: SupplierSummary }> = ({ data }) => {
  return (
    <Row gutter={16}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="供应商总数"
            value={data.total_suppliers}
            prefix={<UserOutlined />}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="平均得分"
            value={(data.avg_score * 100).toFixed(1)}
            suffix="/100"
            prefix={<RiseOutlined />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small" style={{ borderLeft: '3px solid #52c41a' }}>
          <Statistic
            title="最佳供应商"
            value={data.top_supplier}
            prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            valueStyle={{ fontSize: 16 }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="聚类分组"
            value={data.cluster_count || '-'}
            suffix="组"
            valueStyle={{ color: '#722ed1' }}
          />
        </Card>
      </Col>
    </Row>
  );
};

/** 库存分析统计卡片主组件 */
const InventoryStatsCards: React.FC<InventoryStatsCardsProps> = ({ analysisType, data }) => {
  switch (analysisType) {
    case 'abc_xyz':
      return <ABCXYZStatsCards data={data as ABCXYZSummary} />;
    case 'turnover':
      return <TurnoverStatsCards data={data as TurnoverSummary} />;
    case 'safety_stock':
      return <SafetyStockStatsCards data={data as SafetyStockSummary} />;
    case 'supplier_eval':
      return <SupplierStatsCards data={data as SupplierSummary} />;
    default:
      return null;
  }
};

export default InventoryStatsCards;
