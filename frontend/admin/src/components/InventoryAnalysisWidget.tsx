/**
 * 库存分析 Widget 主组件
 * 整合统计卡片、9宫格矩阵、帕累托图、详细表格
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card,
  Spin,
  Alert,
  Table,
  Tabs,
  Space,
  Button,
  Select,
  Tag,
  Tooltip,
  Row,
  Col,
  Modal,
  Form,
  Input,
  InputNumber,
  message,
} from 'antd';
import {
  ReloadOutlined,
  SettingOutlined,
  DownloadOutlined,
  FilterOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import InventoryStatsCards from './InventoryStatsCards';
import ABCXYZMatrix from './ABCXYZMatrix';
import ParetoChart from './ParetoChart';
import { inventoryAnalysisService } from '../services/inventoryAnalysisService';
import {
  ABCXYZResult,
  ABCXYZDetail,
  TurnoverResult,
  TurnoverDetail,
  SafetyStockResult,
  SafetyStockDetail,
  SupplierResult,
  SupplierDetail,
  InventoryAnalysisConfig,
} from '../types/inventoryAnalysis';

interface InventoryAnalysisWidgetProps {
  config: InventoryAnalysisConfig;
  onConfigChange?: (config: InventoryAnalysisConfig) => void;
  editable?: boolean;
}

/** ABC-XYZ 详细表格列 */
const abcXyzColumns: ColumnsType<ABCXYZDetail> = [
  {
    title: '产品',
    dataIndex: 'product_id',
    key: 'product_id',
    ellipsis: true,
    width: 120,
  },
  {
    title: '价值',
    dataIndex: 'value',
    key: 'value',
    align: 'right',
    sorter: (a, b) => a.value - b.value,
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '数量',
    dataIndex: 'quantity',
    key: 'quantity',
    align: 'right',
    sorter: (a, b) => a.quantity - b.quantity,
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '累计占比',
    dataIndex: 'cumulative_pct',
    key: 'cumulative_pct',
    align: 'right',
    render: (value: number) => `${(value * 100).toFixed(1)}%`,
  },
  {
    title: '变异系数',
    dataIndex: 'cv',
    key: 'cv',
    align: 'right',
    render: (value: number) => value.toFixed(3),
  },
  {
    title: 'ABC',
    dataIndex: 'abc_class',
    key: 'abc_class',
    width: 60,
    filters: [
      { text: 'A', value: 'A' },
      { text: 'B', value: 'B' },
      { text: 'C', value: 'C' },
    ],
    onFilter: (value, record) => record.abc_class === value,
    render: (value: string) => (
      <Tag color={value === 'A' ? 'green' : value === 'B' ? 'blue' : 'red'}>
        {value}
      </Tag>
    ),
  },
  {
    title: 'XYZ',
    dataIndex: 'xyz_class',
    key: 'xyz_class',
    width: 60,
    filters: [
      { text: 'X', value: 'X' },
      { text: 'Y', value: 'Y' },
      { text: 'Z', value: 'Z' },
    ],
    onFilter: (value, record) => record.xyz_class === value,
    render: (value: string) => (
      <Tag color={value === 'X' ? 'green' : value === 'Y' ? 'orange' : 'red'}>
        {value}
      </Tag>
    ),
  },
  {
    title: '组合分类',
    dataIndex: 'combined_class',
    key: 'combined_class',
    width: 80,
    render: (value: string) => <Tag>{value}</Tag>,
  },
];

/** 周转率表格列 */
const turnoverColumns: ColumnsType<TurnoverDetail> = [
  {
    title: '产品',
    dataIndex: 'product_id',
    key: 'product_id',
    ellipsis: true,
  },
  {
    title: '销售成本',
    dataIndex: 'cogs',
    key: 'cogs',
    align: 'right',
    sorter: (a, b) => a.cogs - b.cogs,
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '平均库存',
    dataIndex: 'avg_inventory',
    key: 'avg_inventory',
    align: 'right',
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '周转率',
    dataIndex: 'turnover_rate',
    key: 'turnover_rate',
    align: 'right',
    sorter: (a, b) => a.turnover_rate - b.turnover_rate,
    render: (value: number) => value.toFixed(2),
  },
  {
    title: '库存天数',
    dataIndex: 'days_in_inventory',
    key: 'days_in_inventory',
    align: 'right',
    sorter: (a, b) => a.days_in_inventory - b.days_in_inventory,
    render: (value: number) => value.toFixed(0),
  },
  {
    title: '健康度',
    dataIndex: 'health',
    key: 'health',
    render: (value: string) => (
      <Tag color={value === 'good' ? 'green' : value === 'warning' ? 'orange' : 'red'}>
        {value === 'good' ? '健康' : value === 'warning' ? '警告' : '严重'}
      </Tag>
    ),
  },
];

/** 安全库存表格列 */
const safetyStockColumns: ColumnsType<SafetyStockDetail> = [
  {
    title: '产品',
    dataIndex: 'product_id',
    key: 'product_id',
    ellipsis: true,
  },
  {
    title: '平均需求',
    dataIndex: 'avg_demand',
    key: 'avg_demand',
    align: 'right',
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '需求标准差',
    dataIndex: 'demand_std',
    key: 'demand_std',
    align: 'right',
    render: (value: number) => value.toFixed(2),
  },
  {
    title: '安全库存',
    dataIndex: 'safety_stock',
    key: 'safety_stock',
    align: 'right',
    sorter: (a, b) => a.safety_stock - b.safety_stock,
    render: (value: number) => value.toLocaleString(),
  },
  {
    title: '再订货点',
    dataIndex: 'reorder_point',
    key: 'reorder_point',
    align: 'right',
    sorter: (a, b) => a.reorder_point - b.reorder_point,
    render: (value: number) => value.toLocaleString(),
  },
];

/** 供应商评估表格列 */
const supplierColumns: ColumnsType<SupplierDetail> = [
  {
    title: '排名',
    dataIndex: 'rank',
    key: 'rank',
    width: 60,
    sorter: (a, b) => a.rank - b.rank,
  },
  {
    title: '供应商',
    dataIndex: 'supplier_id',
    key: 'supplier_id',
    ellipsis: true,
  },
  {
    title: '加权得分',
    dataIndex: 'weighted_score',
    key: 'weighted_score',
    align: 'right',
    sorter: (a, b) => a.weighted_score - b.weighted_score,
    render: (value: number) => (value * 100).toFixed(1),
  },
  {
    title: '聚类分组',
    dataIndex: 'cluster',
    key: 'cluster',
    render: (value: number | undefined) =>
      value !== undefined ? <Tag color="blue">组 {value + 1}</Tag> : '-',
  },
];

const InventoryAnalysisWidget: React.FC<InventoryAnalysisWidgetProps> = ({
  config,
  onConfigChange,
  editable = false,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ABCXYZResult | TurnoverResult | SafetyStockResult | SupplierResult | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedClass, setSelectedClass] = useState<{ abc?: string; xyz?: string } | null>(null);
  const [configModalVisible, setConfigModalVisible] = useState(false);

  // 执行分析
  const runAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const { analysis_type, data_source, column_mapping, parameters } = config;
      
      let response;
      switch (analysis_type) {
        case 'abc_xyz':
          response = await inventoryAnalysisService.analyzeABCXYZ({
            widget_id: data_source.widget_id,
            connection_id: data_source.connection_id,
            sql: data_source.sql,
            product_column: column_mapping.product_column!,
            value_column: column_mapping.value_column!,
            quantity_column: column_mapping.quantity_column!,
            abc_thresholds: parameters?.abc_thresholds,
            xyz_thresholds: parameters?.xyz_thresholds,
          });
          break;
        case 'turnover':
          response = await inventoryAnalysisService.analyzeTurnover({
            widget_id: data_source.widget_id,
            connection_id: data_source.connection_id,
            sql: data_source.sql,
            product_column: column_mapping.product_column!,
            cogs_column: column_mapping.cogs_column!,
            inventory_column: column_mapping.inventory_column!,
          });
          break;
        case 'safety_stock':
          response = await inventoryAnalysisService.calculateSafetyStock({
            widget_id: data_source.widget_id,
            connection_id: data_source.connection_id,
            sql: data_source.sql,
            product_column: column_mapping.product_column!,
            demand_column: column_mapping.demand_column!,
            period_column: column_mapping.period_column!,
            lead_time: parameters?.lead_time || 7,
            service_level: parameters?.service_level || 0.95,
          });
          break;
        case 'supplier_eval':
          response = await inventoryAnalysisService.evaluateSuppliers({
            widget_id: data_source.widget_id,
            connection_id: data_source.connection_id,
            sql: data_source.sql,
            supplier_column: column_mapping.supplier_column!,
            metrics_columns: column_mapping.metrics_columns!,
            weights: parameters?.weights,
          });
          break;
      }
      
      if (response?.success) {
        setResult(response.result);
      } else {
        setError('分析失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '分析请求失败');
    } finally {
      setLoading(false);
    }
  }, [config]);

  // 初始加载
  useEffect(() => {
    if (config.data_source.widget_id || config.data_source.sql) {
      runAnalysis();
    }
  }, []);

  // 过滤后的表格数据
  const filteredDetails = useMemo(() => {
    if (config.analysis_type !== 'abc_xyz' || !result) return [];
    const abcResult = result as ABCXYZResult;
    
    if (!selectedClass) return abcResult.details;
    
    return abcResult.details.filter(item => {
      if (selectedClass.abc && item.abc_class !== selectedClass.abc) return false;
      if (selectedClass.xyz && item.xyz_class !== selectedClass.xyz) return false;
      return true;
    });
  }, [result, selectedClass, config.analysis_type]);

  // 处理矩阵点击
  const handleMatrixCellClick = useCallback((abc: string, xyz: string) => {
    setSelectedClass({ abc, xyz });
    setActiveTab('details');
  }, []);

  // 清除筛选
  const clearFilter = useCallback(() => {
    setSelectedClass(null);
  }, []);

  // 导出数据
  const handleExport = useCallback(() => {
    if (!result) return;
    
    let data: unknown[] = [];
    let filename = '';
    
    if (config.analysis_type === 'abc_xyz') {
      data = (result as ABCXYZResult).details as unknown[];
      filename = 'abc_xyz_analysis.json';
    } else if (config.analysis_type === 'turnover') {
      data = (result as TurnoverResult).details as unknown[];
      filename = 'turnover_analysis.json';
    } else if (config.analysis_type === 'safety_stock') {
      data = (result as SafetyStockResult).details as unknown[];
      filename = 'safety_stock.json';
    } else if (config.analysis_type === 'supplier_eval') {
      data = (result as SupplierResult).details as unknown[];
      filename = 'supplier_evaluation.json';
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    message.success('导出成功');
  }, [result, config.analysis_type]);

  // 渲染内容
  const renderContent = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="分析中..." />
        </div>
      );
    }
    
    if (error) {
      return <Alert message="分析失败" description={error} type="error" showIcon />;
    }
    
    if (!result) {
      return <Alert message="请配置数据源后执行分析" type="info" showIcon />;
    }
    
    // ABC-XYZ 分析视图
    if (config.analysis_type === 'abc_xyz') {
      const abcResult = result as ABCXYZResult;
      
      return (
        <div>
          <InventoryStatsCards analysisType="abc_xyz" data={abcResult.summary} />
          
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            style={{ marginTop: 16 }}
            items={[
              {
                key: 'overview',
                label: '概览',
                children: (
                  <Row gutter={16}>
                    <Col span={12}>
                      <ABCXYZMatrix
                        data={abcResult.matrix}
                        onCellClick={handleMatrixCellClick}
                        height={320}
                      />
                    </Col>
                    <Col span={12}>
                      <ParetoChart data={abcResult.pareto} height={320} maxItems={20} />
                    </Col>
                  </Row>
                ),
              },
              {
                key: 'details',
                label: (
                  <span>
                    详细列表
                    {selectedClass && (
                      <Tag color="blue" style={{ marginLeft: 8 }}>
                        {selectedClass.abc}{selectedClass.xyz}
                      </Tag>
                    )}
                  </span>
                ),
                children: (
                  <div>
                    {selectedClass && (
                      <div style={{ marginBottom: 8 }}>
                        <Button size="small" onClick={clearFilter} icon={<FilterOutlined />}>
                          清除筛选 ({filteredDetails.length} / {abcResult.details.length})
                        </Button>
                      </div>
                    )}
                    <Table
                      columns={abcXyzColumns}
                      dataSource={filteredDetails}
                      rowKey="product_id"
                      size="small"
                      pagination={{ pageSize: 10 }}
                      scroll={{ x: 800 }}
                    />
                  </div>
                ),
              },
            ]}
          />
        </div>
      );
    }
    
    // 周转率分析视图
    if (config.analysis_type === 'turnover') {
      const turnoverResult = result as TurnoverResult;
      return (
        <div>
          <InventoryStatsCards analysisType="turnover" data={turnoverResult.summary} />
          <Table
            columns={turnoverColumns}
            dataSource={turnoverResult.details}
            rowKey="product_id"
            size="small"
            style={{ marginTop: 16 }}
            pagination={{ pageSize: 10 }}
          />
        </div>
      );
    }
    
    // 安全库存视图
    if (config.analysis_type === 'safety_stock') {
      const safetyResult = result as SafetyStockResult;
      return (
        <div>
          <InventoryStatsCards analysisType="safety_stock" data={safetyResult.summary} />
          <Card size="small" style={{ marginTop: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: '#666' }}>
              <strong>统计依据:</strong> {safetyResult.statistical_basis.formula} | 
              Z值: {safetyResult.statistical_basis.z_score} | 
              前置时间: {safetyResult.statistical_basis.lead_time}天 | 
              服务水平: {(safetyResult.statistical_basis.service_level * 100).toFixed(0)}%
            </div>
          </Card>
          <Table
            columns={safetyStockColumns}
            dataSource={safetyResult.details}
            rowKey="product_id"
            size="small"
            pagination={{ pageSize: 10 }}
          />
        </div>
      );
    }
    
    // 供应商评估视图
    if (config.analysis_type === 'supplier_eval') {
      const supplierResult = result as SupplierResult;
      return (
        <div>
          <InventoryStatsCards analysisType="supplier_eval" data={supplierResult.summary} />
          <Table
            columns={supplierColumns}
            dataSource={supplierResult.details}
            rowKey="supplier_id"
            size="small"
            style={{ marginTop: 16 }}
            pagination={{ pageSize: 10 }}
          />
        </div>
      );
    }
    
    return null;
  };

  return (
    <Card
      title={
        <Space>
          <span>库存分析</span>
          <Select
            value={config.analysis_type}
            size="small"
            style={{ width: 120 }}
            disabled={!editable}
            onChange={(value) => onConfigChange?.({ ...config, analysis_type: value })}
            options={[
              { label: 'ABC-XYZ', value: 'abc_xyz' },
              { label: '周转率', value: 'turnover' },
              { label: '安全库存', value: 'safety_stock' },
              { label: '供应商评估', value: 'supplier_eval' },
            ]}
          />
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="刷新">
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={runAnalysis}
              loading={loading}
            />
          </Tooltip>
          <Tooltip title="导出">
            <Button size="small" icon={<DownloadOutlined />} onClick={handleExport} />
          </Tooltip>
          {editable && (
            <Tooltip title="配置">
              <Button
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setConfigModalVisible(true)}
              />
            </Tooltip>
          )}
        </Space>
      }
      bodyStyle={{ padding: 16 }}
    >
      {renderContent()}
      
      {/* 配置弹窗 */}
      <Modal
        title="库存分析配置"
        open={configModalVisible}
        onCancel={() => setConfigModalVisible(false)}
        footer={null}
        width={600}
      >
        <InventoryAnalysisConfigForm
          config={config}
          onSave={(newConfig) => {
            onConfigChange?.(newConfig);
            setConfigModalVisible(false);
            message.success('配置已保存');
          }}
        />
      </Modal>
    </Card>
  );
};

/** 配置表单组件 */
interface ConfigFormProps {
  config: InventoryAnalysisConfig;
  onSave: (config: InventoryAnalysisConfig) => void;
}

const InventoryAnalysisConfigForm: React.FC<ConfigFormProps> = ({ config, onSave }) => {
  const [form] = Form.useForm();
  
  useEffect(() => {
    form.setFieldsValue({
      widget_id: config.data_source.widget_id,
      product_column: config.column_mapping.product_column,
      value_column: config.column_mapping.value_column,
      quantity_column: config.column_mapping.quantity_column,
      cogs_column: config.column_mapping.cogs_column,
      inventory_column: config.column_mapping.inventory_column,
      demand_column: config.column_mapping.demand_column,
      period_column: config.column_mapping.period_column,
      supplier_column: config.column_mapping.supplier_column,
      lead_time: config.parameters?.lead_time || 7,
      service_level: config.parameters?.service_level || 0.95,
    });
  }, [config, form]);
  
  const handleSubmit = (values: Record<string, unknown>) => {
    const newConfig: InventoryAnalysisConfig = {
      ...config,
      data_source: {
        widget_id: values.widget_id as number,
      },
      column_mapping: {
        product_column: values.product_column as string,
        value_column: values.value_column as string,
        quantity_column: values.quantity_column as string,
        cogs_column: values.cogs_column as string,
        inventory_column: values.inventory_column as string,
        demand_column: values.demand_column as string,
        period_column: values.period_column as string,
        supplier_column: values.supplier_column as string,
      },
      parameters: {
        lead_time: values.lead_time as number,
        service_level: values.service_level as number,
      },
    };
    onSave(newConfig);
  };
  
  return (
    <Form form={form} layout="vertical" onFinish={handleSubmit}>
      <Form.Item name="widget_id" label="数据源 Widget ID" rules={[{ required: true }]}>
        <InputNumber style={{ width: '100%' }} />
      </Form.Item>
      
      {config.analysis_type === 'abc_xyz' && (
        <>
          <Form.Item name="product_column" label="产品列" rules={[{ required: true }]}>
            <Input placeholder="例如: product_id" />
          </Form.Item>
          <Form.Item name="value_column" label="价值列" rules={[{ required: true }]}>
            <Input placeholder="例如: sales_amount" />
          </Form.Item>
          <Form.Item name="quantity_column" label="数量列" rules={[{ required: true }]}>
            <Input placeholder="例如: quantity" />
          </Form.Item>
        </>
      )}
      
      {config.analysis_type === 'safety_stock' && (
        <>
          <Form.Item name="lead_time" label="前置时间（天）" rules={[{ required: true }]}>
            <InputNumber min={1} max={365} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="service_level" label="服务水平" rules={[{ required: true }]}>
            <InputNumber min={0.5} max={0.99} step={0.01} style={{ width: '100%' }} />
          </Form.Item>
        </>
      )}
      
      <Form.Item>
        <Button type="primary" htmlType="submit">
          保存配置
        </Button>
      </Form.Item>
    </Form>
  );
};

export default InventoryAnalysisWidget;
