/**
 * 指标库管理页面
 * 提供指标的CRUD操作和可视化管理
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Space,
  message,
  Popconfirm,
  Typography,
  Row,
  Col,
  Tooltip,
  Empty,
  Spin,
  Divider,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FunctionOutlined,
  TableOutlined,
  TagOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  BellOutlined,
} from '@ant-design/icons';
import { getConnections } from '../services/api';
import { metricService, Metric, MetricCreate } from '../services/metricService';
import MetricAlertPanel from '../components/MetricAlertPanel';

const { Title, Text } = Typography;
const { TextArea } = Input;

// 聚合类型选项
const AGGREGATION_OPTIONS = [
  { value: 'SUM', label: 'SUM - 求和' },
  { value: 'AVG', label: 'AVG - 平均值' },
  { value: 'COUNT', label: 'COUNT - 计数' },
  { value: 'MAX', label: 'MAX - 最大值' },
  { value: 'MIN', label: 'MIN - 最小值' },
  { value: 'COUNT_DISTINCT', label: 'COUNT_DISTINCT - 去重计数' },
];

// 分类选项
const CATEGORY_OPTIONS = [
  { value: '销售', label: '销售' },
  { value: '用户', label: '用户' },
  { value: '运营', label: '运营' },
  { value: '财务', label: '财务' },
  { value: '库存', label: '库存' },
  { value: '其他', label: '其他' },
];

// 内容组件 - 供复用（无外层 padding）
export const MetricsContent: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingMetric, setEditingMetric] = useState<Metric | null>(null);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();
  const [alertPanelVisible, setAlertPanelVisible] = useState(false);
  const [selectedMetricForAlert, setSelectedMetricForAlert] = useState<Metric | null>(null);

  const handleOpenAlertPanel = (metric: Metric) => {
    setSelectedMetricForAlert(metric);
    setAlertPanelVisible(true);
  };

  // 加载连接列表
  useEffect(() => {
    fetchConnections();
  }, []);

  // 加载指标列表
  useEffect(() => {
    if (selectedConnection) {
      fetchMetrics();
    }
  }, [selectedConnection]);

  const fetchConnections = async () => {
    try {
      const response = await getConnections();
      const data = Array.isArray(response.data) ? response.data : response.data?.items || [];
      setConnections(data);
      if (data.length > 0) {
        setSelectedConnection(data[0].id);
      }
    } catch (error) {
      message.error('获取连接列表失败');
    }
  };

  const fetchMetrics = async () => {
    if (!selectedConnection) return;
    setLoading(true);
    try {
      const data = await metricService.listMetrics(selectedConnection);
      setMetrics(data);
    } catch (error) {
      message.error('获取指标列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingMetric(null);
    form.resetFields();
    form.setFieldsValue({ aggregation: 'SUM', decimal_places: 2 });
    setModalVisible(true);
  };

  const handleEdit = (record: Metric) => {
    setEditingMetric(record);
    form.setFieldsValue({
      ...record,
      tags: record.tags?.join(','),
      dimension_columns: record.dimension_columns?.join(','),
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await metricService.deleteMetric(id);
      message.success('删除成功');
      fetchMetrics();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      const metricData: MetricCreate = {
        ...values,
        connection_id: selectedConnection!,
        tags: values.tags ? values.tags.split(',').map((t: string) => t.trim()) : [],
        dimension_columns: values.dimension_columns 
          ? values.dimension_columns.split(',').map((c: string) => c.trim()) 
          : [],
      };

      if (editingMetric) {
        await metricService.updateMetric(editingMetric.id, metricData);
        message.success('更新成功');
      } else {
        await metricService.createMetric(metricData);
        message.success('创建成功');
      }

      setModalVisible(false);
      fetchMetrics();
    } catch (error) {
      console.error('提交失败:', error);
    }
  };

  // 过滤指标
  const filteredMetrics = metrics.filter((m) =>
    m.name.toLowerCase().includes(searchText.toLowerCase()) ||
    m.business_name?.toLowerCase().includes(searchText.toLowerCase()) ||
    m.category?.toLowerCase().includes(searchText.toLowerCase())
  );

  const columns = [
    {
      title: '指标名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Metric) => (
        <div>
          <Text strong>{text}</Text>
          {record.business_name && (
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
              ({record.business_name})
            </Text>
          )}
        </div>
      ),
    },
    {
      title: '计算公式',
      dataIndex: 'formula',
      key: 'formula',
      render: (text: string) => (
        <Tag icon={<FunctionOutlined />} color="blue">
          {text}
        </Tag>
      ),
    },
    {
      title: '来源',
      key: 'source',
      render: (_: any, record: Metric) => (
        <Tooltip title={`${record.source_table}.${record.source_column}`}>
          <Tag icon={<TableOutlined />}>
            {record.source_table}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      render: (text: string) => text && <Tag color="purple">{text}</Tag>,
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 80,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: string[]) => (
        <Space size={4} wrap>
          {tags?.slice(0, 2).map((tag) => (
            <Tag key={tag} color="cyan">{tag}</Tag>
          ))}
          {tags?.length > 2 && <Tag>+{tags.length - 2}</Tag>}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: any, record: Metric) => (
        <Space>
          <Tooltip title="告警设置">
            <Button
              type="text"
              icon={<BellOutlined />}
              onClick={() => handleOpenAlertPanel(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此指标?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          <FunctionOutlined style={{ marginRight: 8 }} />
          指标库管理
        </Title>
        <Text type="secondary">
          定义业务指标，支持语义层查询和智能分析
        </Text>
      </div>

      <Card>
        {/* 工具栏 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex="200px">
            <Select
              style={{ width: '100%' }}
              placeholder="选择数据源"
              value={selectedConnection}
              onChange={setSelectedConnection}
            >
              {connections.map((conn) => (
                <Select.Option key={conn.id} value={conn.id}>
                  {conn.name}
                </Select.Option>
              ))}
            </Select>
          </Col>
          <Col flex="auto">
            <Input
              placeholder="搜索指标..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchMetrics}>
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
                disabled={!selectedConnection}
              >
                新建指标
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 指标列表 */}
        <Table
          columns={columns}
          dataSource={filteredMetrics}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{
            emptyText: (
              <Empty
                description={
                  selectedConnection
                    ? '暂无指标，点击"新建指标"创建'
                    : '请先选择数据源'
                }
              />
            ),
          }}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editingMetric ? '编辑指标' : '新建指标'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
        okText={editingMetric ? '保存' : '创建'}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="指标名称"
                rules={[{ required: true, message: '请输入指标名称' }]}
              >
                <Input placeholder="如：销售额" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="business_name" label="业务别名">
                <Input placeholder="如：GMV" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="指标用途说明..." />
          </Form.Item>

          <Divider>计算逻辑</Divider>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="source_table"
                label="来源表"
                rules={[{ required: true }]}
              >
                <Input placeholder="表名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="source_column"
                label="来源字段"
                rules={[{ required: true }]}
              >
                <Input placeholder="字段名" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="formula"
                label="计算公式"
                rules={[{ required: true }]}
              >
                <Input placeholder="如：SUM(amount)" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="aggregation" label="聚合方式">
                <Select options={AGGREGATION_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>

          <Divider>分类与显示</Divider>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="category" label="分类">
                <Select options={CATEGORY_OPTIONS} allowClear />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="unit" label="单位">
                <Input placeholder="如：元、个、%" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="decimal_places" label="小数位">
                <Select>
                  {[0, 1, 2, 3, 4].map((n) => (
                    <Select.Option key={n} value={n}>{n}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="tags"
            label="标签"
            tooltip="多个标签用逗号分隔"
          >
            <Input placeholder="如：核心指标,财务,月报" />
          </Form.Item>

          <Form.Item
            name="dimension_columns"
            label="可用维度字段"
            tooltip="多个字段用逗号分隔"
          >
            <Input placeholder="如：region,product_category" />
          </Form.Item>

          <Form.Item name="time_column" label="时间字段">
            <Input placeholder="如：order_date" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 告警管理面板 */}
      <MetricAlertPanel
        visible={alertPanelVisible}
        metricId={selectedMetricForAlert?.id || ''}
        metricName={selectedMetricForAlert?.name || ''}
        onClose={() => setAlertPanelVisible(false)}
      />
    </div>
  );
};

// 独立页面组件 - 保持向后兼容
const MetricsPage: React.FC = () => {
  return (
    <div style={{ padding: '0 0 24px 0' }}>
      <MetricsContent />
    </div>
  );
};

export default MetricsPage;
