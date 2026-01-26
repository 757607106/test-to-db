/**
 * JOIN 规则管理页面
 * 预定义表之间的关联规则，减少LLM生成SQL时的错误
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
  Switch,
  InputNumber,
  Tooltip,
  Empty,
  Badge,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  ApiOutlined,
  SwapOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { getConnections } from '../services/api';
import { joinRuleService, JoinRule, JoinRuleCreate } from '../services/joinRuleService';

const { Title, Text } = Typography;

// JOIN 类型选项
const JOIN_TYPE_OPTIONS = [
  { value: 'INNER', label: 'INNER JOIN', description: '只返回匹配的行' },
  { value: 'LEFT', label: 'LEFT JOIN', description: '返回左表所有行' },
  { value: 'RIGHT', label: 'RIGHT JOIN', description: '返回右表所有行' },
  { value: 'FULL', label: 'FULL JOIN', description: '返回两表所有行' },
];

const JoinRulesPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<JoinRule[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<JoinRule | null>(null);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();

  useEffect(() => {
    fetchConnections();
  }, []);

  useEffect(() => {
    if (selectedConnection) {
      fetchRules();
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

  const fetchRules = async () => {
    if (!selectedConnection) return;
    setLoading(true);
    try {
      const data = await joinRuleService.listRules(selectedConnection);
      setRules(data);
    } catch (error) {
      message.error('获取规则列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({ 
      join_type: 'INNER', 
      priority: 5,
      is_active: true 
    });
    setModalVisible(true);
  };

  const handleEdit = (record: JoinRule) => {
    setEditingRule(record);
    form.setFieldsValue({
      ...record,
      tags: record.tags?.join(','),
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await joinRuleService.deleteRule(id);
      message.success('删除成功');
      fetchRules();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleToggle = async (id: string, isActive: boolean) => {
    try {
      await joinRuleService.updateRule(id, { is_active: isActive });
      message.success(isActive ? '已启用' : '已禁用');
      fetchRules();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      const ruleData: JoinRuleCreate = {
        ...values,
        connection_id: selectedConnection!,
        tags: values.tags ? values.tags.split(',').map((t: string) => t.trim()) : [],
      };

      if (editingRule) {
        await joinRuleService.updateRule(editingRule.id, ruleData);
        message.success('更新成功');
      } else {
        await joinRuleService.createRule(ruleData);
        message.success('创建成功');
      }

      setModalVisible(false);
      fetchRules();
    } catch (error) {
      console.error('提交失败:', error);
    }
  };

  const filteredRules = rules.filter((r) =>
    r.name.toLowerCase().includes(searchText.toLowerCase()) ||
    r.left_table.toLowerCase().includes(searchText.toLowerCase()) ||
    r.right_table.toLowerCase().includes(searchText.toLowerCase())
  );

  const getJoinTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      'INNER': 'blue',
      'LEFT': 'green',
      'RIGHT': 'orange',
      'FULL': 'purple',
    };
    return colors[type] || 'default';
  };

  const columns = [
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: JoinRule) => (
        <Space>
          <Text strong>{text}</Text>
          {!record.is_active && <Tag color="default">已禁用</Tag>}
        </Space>
      ),
    },
    {
      title: '关联关系',
      key: 'relation',
      render: (_: any, record: JoinRule) => (
        <Space>
          <Tag color="cyan">{record.left_table}</Tag>
          <Text type="secondary">.{record.left_column}</Text>
          <SwapOutlined />
          <Tag color="cyan">{record.right_table}</Tag>
          <Text type="secondary">.{record.right_column}</Text>
        </Space>
      ),
    },
    {
      title: 'JOIN类型',
      dataIndex: 'join_type',
      key: 'join_type',
      width: 120,
      render: (type: string) => (
        <Tag color={getJoinTypeColor(type)}>{type} JOIN</Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: number) => (
        <Badge 
          count={priority} 
          style={{ backgroundColor: priority >= 7 ? '#52c41a' : priority >= 4 ? '#1890ff' : '#d9d9d9' }}
        />
      ),
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      key: 'usage_count',
      width: 90,
      render: (count: number) => <Text type="secondary">{count}</Text>,
    },
    {
      title: '状态',
      key: 'is_active',
      width: 80,
      render: (_: any, record: JoinRule) => (
        <Switch
          size="small"
          checked={record.is_active}
          onChange={(checked) => handleToggle(record.id, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, record: JoinRule) => (
        <Space>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此规则?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '0 0 24px 0' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          <ApiOutlined style={{ marginRight: 8 }} />
          JOIN 规则管理
        </Title>
        <Text type="secondary">
          预定义表关联规则，提高SQL生成准确性
        </Text>
      </div>

      <Card>
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
              placeholder="搜索规则..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchRules}>
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
                disabled={!selectedConnection}
              >
                新建规则
              </Button>
            </Space>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={filteredRules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{
            emptyText: (
              <Empty
                description={
                  selectedConnection
                    ? '暂无规则，点击"新建规则"创建'
                    : '请先选择数据源'
                }
              />
            ),
          }}
        />
      </Card>

      <Modal
        title={editingRule ? '编辑规则' : '新建JOIN规则'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={600}
        okText={editingRule ? '保存' : '创建'}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="规则名称"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="如：订单-用户关联" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="规则用途说明..." />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="left_table"
                label="左表"
                rules={[{ required: true }]}
              >
                <Input placeholder="如：orders" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="left_column"
                label="左表字段"
                rules={[{ required: true }]}
              >
                <Input placeholder="如：user_id" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="right_table"
                label="右表"
                rules={[{ required: true }]}
              >
                <Input placeholder="如：users" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="right_column"
                label="右表字段"
                rules={[{ required: true }]}
              >
                <Input placeholder="如：id" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="join_type" label="JOIN类型">
                <Select options={JOIN_TYPE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                name="priority" 
                label="优先级"
                tooltip="1-10，数值越大优先级越高"
              >
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="extra_conditions"
            label="附加条件"
            tooltip="可选的额外JOIN条件"
          >
            <Input placeholder="如：AND orders.status = 'completed'" />
          </Form.Item>

          <Form.Item
            name="tags"
            label="标签"
            tooltip="多个标签用逗号分隔"
          >
            <Input placeholder="如：核心关联,订单业务" />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="启用状态"
            valuePropName="checked"
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default JoinRulesPage;
