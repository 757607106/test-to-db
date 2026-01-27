/**
 * Skills 管理页面
 * 
 * Skills-SQL-Assistant 架构的管理界面
 * 提供 Skills 的 CRUD 操作和可视化管理
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
  Switch,
  Badge,
  Divider,
  Alert,
  Tabs,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  AppstoreOutlined,
  TableOutlined,
  TagOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
  LinkOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { getConnections } from '../services/api';
import { skillService, Skill, SkillCreate, SkillUpdate, JoinRuleItem } from '../services/skillService';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// 优先级选项
const PRIORITY_OPTIONS = [
  { value: 0, label: '低 (0)' },
  { value: 5, label: '中 (5)' },
  { value: 10, label: '高 (10)' },
  { value: 20, label: '最高 (20)' },
];

// 颜色选项
const COLOR_OPTIONS = [
  { value: '#1890ff', label: '蓝色' },
  { value: '#52c41a', label: '绿色' },
  { value: '#faad14', label: '橙色' },
  { value: '#f5222d', label: '红色' },
  { value: '#722ed1', label: '紫色' },
  { value: '#13c2c2', label: '青色' },
];

// JOIN 类型选项
const JOIN_TYPE_OPTIONS = [
  { value: 'INNER', label: 'INNER JOIN' },
  { value: 'LEFT', label: 'LEFT JOIN' },
  { value: 'RIGHT', label: 'RIGHT JOIN' },
  { value: 'FULL', label: 'FULL JOIN' },
];

const SkillsPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [connections, setConnections] = useState<any[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
  const [hasSkillsConfigured, setHasSkillsConfigured] = useState(false);
  const [form] = Form.useForm();

  // 加载连接列表
  useEffect(() => {
    fetchConnections();
  }, []);

  // 加载 Skills 列表
  useEffect(() => {
    if (selectedConnection) {
      fetchSkills();
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

  const fetchSkills = async () => {
    if (!selectedConnection) return;
    setLoading(true);
    try {
      const response = await skillService.listSkills(selectedConnection, true);
      setSkills(response.skills);
      setHasSkillsConfigured(response.has_skills_configured);
    } catch (error) {
      message.error('获取 Skills 列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingSkill(null);
    form.resetFields();
    form.setFieldsValue({
      priority: 5,
      is_active: true,
      color: '#1890ff',
    });
    setModalVisible(true);
  };

  const handleEdit = (record: Skill) => {
    setEditingSkill(record);
    form.setFieldsValue({
      ...record,
      keywords: record.keywords?.join(', '),
      table_names: record.table_names?.join(', '),
      intent_examples: record.intent_examples?.join('\n'),
      join_rules: record.join_rules || [],
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await skillService.deleteSkill(id);
      message.success('删除成功');
      fetchSkills();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleToggleActive = async (record: Skill) => {
    try {
      await skillService.toggleSkillActive(record.id, !record.is_active);
      message.success(record.is_active ? '已禁用' : '已启用');
      fetchSkills();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // 处理数组字段
      const data: SkillCreate | SkillUpdate = {
        name: values.name,
        display_name: values.display_name,
        description: values.description,
        keywords: values.keywords?.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean) || [],
        table_names: values.table_names?.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean) || [],
        intent_examples: values.intent_examples?.split('\n').map((s: string) => s.trim()).filter(Boolean) || [],
        business_rules: values.business_rules,
        join_rules: values.join_rules || [],
        priority: values.priority,
        is_active: values.is_active,
        color: values.color,
        connection_id: selectedConnection!,
      };

      if (editingSkill) {
        await skillService.updateSkill(editingSkill.id, data);
        message.success('更新成功');
      } else {
        await skillService.createSkill(data as SkillCreate);
        message.success('创建成功');
      }
      
      setModalVisible(false);
      fetchSkills();
    } catch (error: any) {
      if (error.response?.data?.detail) {
        message.error(error.response.data.detail);
      } else {
        message.error('操作失败');
      }
    }
  };

  const columns = [
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Badge
          status={active ? 'success' : 'default'}
          text={active ? '启用' : '禁用'}
        />
      ),
    },
    {
      title: 'Skill',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (text: string, record: Skill) => (
        <Space direction="vertical" size={0}>
          <Space>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: record.color || '#1890ff',
                display: 'inline-block',
              }}
            />
            <Text strong>{text}</Text>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>{record.name}</Text>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '关键词',
      dataIndex: 'keywords',
      key: 'keywords',
      width: 200,
      render: (keywords: string[]) => (
        <Space size={[0, 4]} wrap>
          {(keywords || []).slice(0, 4).map((keyword, index) => (
            <Tag key={index} color="blue">{keyword}</Tag>
          ))}
          {keywords?.length > 4 && (
            <Tag>+{keywords.length - 4}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '关联表',
      dataIndex: 'table_names',
      key: 'table_names',
      width: 150,
      render: (tables: string[]) => (
        <Tooltip title={tables?.join(', ')}>
          <Space>
            <TableOutlined />
            <Text>{tables?.length || 0} 个表</Text>
          </Space>
        </Tooltip>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: Skill, b: Skill) => a.priority - b.priority,
    },
    {
      title: '使用统计',
      key: 'usage',
      width: 120,
      render: (_: any, record: Skill) => (
        <Space direction="vertical" size={0}>
          <Text style={{ fontSize: 12 }}>调用: {record.usage_count}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            命中率: {(record.hit_rate * 100).toFixed(1)}%
          </Text>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: Skill) => (
        <Space size="small">
          <Tooltip title={record.is_active ? '禁用' : '启用'}>
            <Switch
              size="small"
              checked={record.is_active}
              onChange={() => handleToggleActive(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此 Skill?"
            description="删除后无法恢复，相关路由规则将失效"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col>
            <Space>
              <AppstoreOutlined style={{ fontSize: 24, color: '#1890ff' }} />
              <Title level={4} style={{ margin: 0 }}>Skills 管理</Title>
              <Tooltip title="Skills 是业务领域的抽象，用于将复杂的数据库表组织成易于理解的业务模块">
                <InfoCircleOutlined style={{ color: '#999' }} />
              </Tooltip>
            </Space>
          </Col>
          <Col>
            <Space>
              <Select
                style={{ width: 200 }}
                placeholder="选择数据库连接"
                value={selectedConnection}
                onChange={setSelectedConnection}
                options={connections.map(c => ({
                  value: c.id,
                  label: c.name || c.database,
                }))}
              />
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchSkills}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
                disabled={!selectedConnection}
              >
                创建 Skill
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 状态提示 */}
        {selectedConnection && !hasSkillsConfigured && (
          <Alert
            message="零配置模式"
            description="当前连接未配置 Skills，系统将使用默认的全库检索模式。配置 Skills 可以显著提升大型数据库的查询效率和准确性。"
            type="info"
            showIcon
            icon={<ThunderboltOutlined />}
            style={{ marginBottom: 16 }}
          />
        )}

        {selectedConnection && hasSkillsConfigured && (
          <Alert
            message="Skill 模式已启用"
            description={`已配置 ${skills.filter(s => s.is_active).length} 个活跃的 Skills，系统将根据用户查询智能路由到对应的业务领域。`}
            type="success"
            showIcon
            icon={<CheckCircleOutlined />}
            style={{ marginBottom: 16 }}
          />
        )}

        <Table
          columns={columns}
          dataSource={skills}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个 Skills`,
          }}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  selectedConnection
                    ? '暂无 Skills，点击"创建 Skill"开始配置'
                    : '请先选择数据库连接'
                }
              />
            ),
          }}
        />
      </Card>

      {/* 创建/编辑 Modal */}
      <Modal
        title={editingSkill ? '编辑 Skill' : '创建 Skill'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={800}
        okText={editingSkill ? '保存' : '创建'}
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          requiredMark="optional"
        >
          <Tabs
            defaultActiveKey="basic"
            items={[
              {
                key: 'basic',
                label: '基础配置',
                children: (
                  <>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item
                          name="name"
                          label="Skill 标识"
                          rules={[
                            { required: true, message: '请输入 Skill 标识' },
                            { pattern: /^[a-z][a-z0-9_]*$/, message: '只能包含小写字母、数字和下划线，且以字母开头' },
                          ]}
                          tooltip="唯一标识，用于系统内部引用"
                        >
                          <Input placeholder="如: sales_order" disabled={!!editingSkill} />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item
                          name="display_name"
                          label="显示名称"
                          rules={[{ required: true, message: '请输入显示名称' }]}
                        >
                          <Input placeholder="如: 销售订单" />
                        </Form.Item>
                      </Col>
                    </Row>

                    <Form.Item
                      name="description"
                      label="描述"
                      tooltip="告诉 AI 这个 Skill 处理什么类型的查询"
                    >
                      <TextArea
                        rows={2}
                        placeholder="如: 处理销售订单相关的查询，包括订单明细、客户信息、销售统计等"
                      />
                    </Form.Item>

                    <Form.Item
                      name="keywords"
                      label="触发关键词"
                      tooltip="用户查询中包含这些词时，会优先匹配此 Skill"
                    >
                      <Input placeholder="多个关键词用逗号分隔，如: 销售, 订单, 客户, 金额" />
                    </Form.Item>

                    <Form.Item
                      name="table_names"
                      label="关联表"
                      tooltip="此 Skill 涉及的数据库表"
                      rules={[{ required: true, message: '请输入至少一个关联表' }]}
                    >
                      <Input placeholder="多个表名用逗号分隔，如: orders, order_items, customers" />
                    </Form.Item>

                    <Form.Item
                      name="business_rules"
                      label="业务规则"
                      tooltip="生成 SQL 时需要遵守的业务规则，会注入到 AI 的提示词中"
                    >
                      <TextArea
                        rows={3}
                        placeholder="如: 订单金额使用 total_amount 字段；已取消的订单（status='cancelled'）不计入统计"
                      />
                    </Form.Item>

                    <Form.Item
                      name="intent_examples"
                      label="意图示例"
                      tooltip="帮助 AI 理解哪些查询适合使用此 Skill"
                    >
                      <TextArea
                        rows={3}
                        placeholder="每行一个示例，如:&#10;查询本月销售额&#10;统计各客户的订单数量&#10;分析销售趋势"
                      />
                    </Form.Item>

                    <Row gutter={16}>
                      <Col span={8}>
                        <Form.Item name="priority" label="优先级">
                          <Select options={PRIORITY_OPTIONS} />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="color" label="主题色">
                          <Select options={COLOR_OPTIONS} />
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item name="is_active" label="启用状态" valuePropName="checked">
                          <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                ),
              },
              {
                key: 'join_rules',
                label: (
                  <Space>
                    <LinkOutlined />
                    JOIN 规则
                  </Space>
                ),
                children: (
                  <>
                    <Alert
                      message="JOIN 规则用于定义表之间的关联关系"
                      description="当 AI 生成涉及多表查询的 SQL 时，会使用这些规则来正确关联表。"
                      type="info"
                      showIcon
                      style={{ marginBottom: 16 }}
                    />
                    <Form.List name="join_rules">
                      {(fields, { add, remove }) => (
                        <>
                          {fields.map(({ key, name, ...restField }) => (
                            <Card
                              key={key}
                              size="small"
                              style={{ marginBottom: 12 }}
                              extra={
                                <Button
                                  type="text"
                                  danger
                                  icon={<MinusCircleOutlined />}
                                  onClick={() => remove(name)}
                                />
                              }
                            >
                              <Row gutter={12}>
                                <Col span={6}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'left_table']}
                                    rules={[{ required: true, message: '必填' }]}
                                  >
                                    <Input placeholder="左表" />
                                  </Form.Item>
                                </Col>
                                <Col span={6}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'left_column']}
                                    rules={[{ required: true, message: '必填' }]}
                                  >
                                    <Input placeholder="左表列" />
                                  </Form.Item>
                                </Col>
                                <Col span={6}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'right_table']}
                                    rules={[{ required: true, message: '必填' }]}
                                  >
                                    <Input placeholder="右表" />
                                  </Form.Item>
                                </Col>
                                <Col span={6}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'right_column']}
                                    rules={[{ required: true, message: '必填' }]}
                                  >
                                    <Input placeholder="右表列" />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={12}>
                                <Col span={6}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'join_type']}
                                    initialValue="INNER"
                                  >
                                    <Select options={JOIN_TYPE_OPTIONS} placeholder="JOIN 类型" />
                                  </Form.Item>
                                </Col>
                                <Col span={18}>
                                  <Form.Item
                                    {...restField}
                                    name={[name, 'description']}
                                  >
                                    <Input placeholder="规则描述（可选）" />
                                  </Form.Item>
                                </Col>
                              </Row>
                            </Card>
                          ))}
                          <Button
                            type="dashed"
                            onClick={() => add({ join_type: 'INNER' })}
                            block
                            icon={<PlusOutlined />}
                          >
                            添加 JOIN 规则
                          </Button>
                        </>
                      )}
                    </Form.List>
                  </>
                ),
              },
            ]}
          />
        </Form>
      </Modal>
    </div>
  );
};

export default SkillsPage;
