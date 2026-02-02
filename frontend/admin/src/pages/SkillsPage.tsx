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
  BulbOutlined,
  RocketOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { getConnections } from '../services/api';
import { 
  skillService, 
  Skill, 
  SkillCreate, 
  SkillUpdate, 
  JoinRuleItem,
  OptimizationSuggestion,
  SkillSuggestion,
} from '../services/skillService';
import { useGlobalConnection } from '../contexts/GlobalConnectionContext';

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
  const { selectedConnectionId } = useGlobalConnection();
  const [loading, setLoading] = useState(false);
  const [skills, setSkills] = useState<Skill[]>([]);
  // const [connections, setConnections] = useState<any[]>([]); // 使用全局 Context
  // const [selectedConnection, setSelectedConnection] = useState<number | null>(null); // 使用全局 Context
  const [modalVisible, setModalVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null);
  const [hasSkillsConfigured, setHasSkillsConfigured] = useState(false);
  const [form] = Form.useForm();
  
  // 新增状态：页面 Tab
  const [activeTab, setActiveTab] = useState<'list' | 'discover' | 'optimize'>('list');
  
  // 自动发现状态
  const [discoverLoading, setDiscoverLoading] = useState(false);
  const [discoverSuggestions, setDiscoverSuggestions] = useState<SkillSuggestion[]>([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState<string[]>([]);
  const [discoverStats, setDiscoverStats] = useState<{ analyzed: number; grouped: number; ungrouped: string[] }>({ 
    analyzed: 0, grouped: 0, ungrouped: [] 
  });
  
  // 优化建议状态
  const [optimizeLoading, setOptimizeLoading] = useState(false);
  const [optimizeSuggestions, setOptimizeSuggestions] = useState<OptimizationSuggestion[]>([]);

  // 加载 Skills 列表
  useEffect(() => {
    if (selectedConnectionId) {
      fetchSkills();
    } else {
      setSkills([]);
      setHasSkillsConfigured(false);
    }
  }, [selectedConnectionId]);

  /* fetchConnections removed as it is handled globally */

  const fetchSkills = async () => {
    if (!selectedConnectionId) return;
    setLoading(true);
    try {
      const response = await skillService.listSkills(selectedConnectionId, true);
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
    if (!selectedConnectionId) {
      message.error('请先选择数据库连接');
      return;
    }

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
        connection_id: selectedConnectionId,
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

  // 自动发现 Skills
  const handleDiscover = async (useLlm = false) => {
    if (!selectedConnectionId) return;
    setDiscoverLoading(true);
    try {
      const result = await skillService.discoverSkills(selectedConnectionId, useLlm);
      setDiscoverSuggestions(result.suggestions);
      setDiscoverStats({
        analyzed: result.analyzed_tables,
        grouped: result.grouped_tables,
        ungrouped: result.ungrouped_tables,
      });
      if (result.suggestions.length === 0) {
        message.info('未发现可分组的表，请手动创建 Skill');
      } else {
        message.success(`发现 ${result.suggestions.length} 个 Skill 建议`);
      }
    } catch (error) {
      message.error('自动发现失败');
    } finally {
      setDiscoverLoading(false);
    }
  };

  // 应用发现的 Skills
  const handleApplyDiscovered = async () => {
    if (!selectedConnectionId || selectedSuggestions.length === 0) return;
    setDiscoverLoading(true);
    try {
      const result = await skillService.applyDiscoveredSkills(selectedConnectionId, selectedSuggestions);
      if (result.success) {
        message.success(`成功创建 ${result.created_count} 个 Skills`);
        setSelectedSuggestions([]);
        setDiscoverSuggestions([]);
        setActiveTab('list');
        fetchSkills();
      } else {
        message.error('应用失败');
      }
    } catch (error) {
      message.error('应用发现的 Skills 失败');
    } finally {
      setDiscoverLoading(false);
    }
  };

  // 获取优化建议
  const handleFetchOptimizations = async (forceRefresh = false) => {
    if (!selectedConnectionId) return;
    setOptimizeLoading(true);
    try {
      const result = await skillService.getOptimizationSuggestions(selectedConnectionId, 7, forceRefresh);
      setOptimizeSuggestions(result.suggestions);
      if (result.suggestions.length === 0) {
        message.info('暂无优化建议');
      }
    } catch (error) {
      message.error('获取优化建议失败');
    } finally {
      setOptimizeLoading(false);
    }
  };

  // 应用优化建议
  const handleApplyOptimization = async (suggestionId: string) => {
    if (!selectedConnectionId) return;
    try {
      const result = await skillService.applyOptimizationSuggestion(suggestionId, selectedConnectionId);
      if (result.success) {
        message.success(result.message || '应用成功');
        handleFetchOptimizations(true);
        fetchSkills();
      } else {
        message.error(result.error || '应用失败');
      }
    } catch (error) {
      message.error('应用优化建议失败');
    }
  };

  // ===== 渲染函数 =====

  // 渲染 Skills 列表
  const renderSkillsList = () => {
    const activeSkillsCount = skills.filter(s => s.is_active).length;
    
    return (
    <>
      <Row justify="space-between" style={{ marginBottom: 16 }}>
        <Col>
          {selectedConnectionId && !hasSkillsConfigured && (
            <Alert
              message="零配置模式"
              description="当前连接未配置 Skills，系统将使用默认的全库检索模式。"
              type="info"
              showIcon
              icon={<ThunderboltOutlined />}
              style={{ marginBottom: 0 }}
            />
          )}
          {selectedConnectionId && hasSkillsConfigured && activeSkillsCount > 0 && (
            <Alert
              message="Skill 模式已启用"
              description={`已配置 ${activeSkillsCount} 个活跃的 Skills`}
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              style={{ marginBottom: 0 }}
            />
          )}
          {selectedConnectionId && hasSkillsConfigured && activeSkillsCount === 0 && (
            <Alert
              message="Skill 未激活"
              description={`已配置 ${skills.length} 个 Skills，但均未启用。请启用至少一个 Skill 以使用 Skill 模式。`}
              type="warning"
              showIcon
              icon={<CloseCircleOutlined />}
              style={{ marginBottom: 0 }}
            />
          )}
          {!selectedConnectionId && (
            <Alert
              message="请选择数据库连接"
              description="请在顶部导航栏选择一个数据库连接以管理 Skills。"
              type="info"
              showIcon
              style={{ marginBottom: 0 }}
            />
          )}
        </Col>
        <Col>
          <Space>
            <Input
              placeholder="搜索..."
              prefix={<SearchOutlined />}
              style={{ width: 200 }}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
              disabled={!selectedConnectionId}
            >
              创建 Skill
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchSkills}
              loading={loading}
              disabled={!selectedConnectionId}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={skills}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
    </>
    );
  };

  // 渲染自动发现
  const renderDiscover = () => (
    <>
      <Alert
        message="自动发现 Skills"
        description="基于数据库表结构分析，按表名前缀和外键关系自动分组，生成 Skill 配置建议。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      <Row justify="space-between" style={{ marginBottom: 16 }}>
        <Col>
          {discoverStats.analyzed > 0 && (
            <Text type="secondary">
              已分析 {discoverStats.analyzed} 个表，{discoverStats.grouped} 个已分组，
              {discoverStats.ungrouped.length} 个未分组
            </Text>
          )}
        </Col>
        <Col>
          <Space>
            <Button icon={<SearchOutlined />} onClick={() => handleDiscover(false)} loading={discoverLoading}>
              快速发现
            </Button>
            <Tooltip title="使用 LLM 增强分析，生成更准确的描述和关键词">
              <Button icon={<ExperimentOutlined />} onClick={() => handleDiscover(true)} loading={discoverLoading}>
                LLM 增强发现
              </Button>
            </Tooltip>
            <Button
              type="primary"
              onClick={handleApplyDiscovered}
              disabled={selectedSuggestions.length === 0}
              loading={discoverLoading}
            >
              应用选中 ({selectedSuggestions.length})
            </Button>
          </Space>
        </Col>
      </Row>
      <Table
        dataSource={discoverSuggestions}
        rowKey="name"
        loading={discoverLoading}
        rowSelection={{
          selectedRowKeys: selectedSuggestions,
          onChange: (keys) => setSelectedSuggestions(keys as string[]),
        }}
        columns={[
          { title: '名称', dataIndex: 'display_name', key: 'display_name' },
          { title: '标识', dataIndex: 'name', key: 'name', render: (t: string) => <Text code>{t}</Text> },
          { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
          {
            title: '关键词',
            dataIndex: 'keywords',
            key: 'keywords',
            render: (kws: string[]) => (kws || []).slice(0, 3).map((k, i) => <Tag key={i}>{k}</Tag>),
          },
          {
            title: '关联表',
            dataIndex: 'table_names',
            key: 'table_names',
            render: (tables: string[]) => <Text>{tables?.length || 0} 个表</Text>,
          },
          {
            title: '置信度',
            dataIndex: 'confidence',
            key: 'confidence',
            render: (c: number) => <Tag color={c > 0.7 ? 'green' : c > 0.5 ? 'orange' : 'default'}>{(c * 100).toFixed(0)}%</Tag>,
          },
        ]}
        locale={{ emptyText: <Empty description='点击"快速发现"开始分析' /> }}
      />
    </>
  );

  // 渲染优化建议
  const renderOptimize = () => (
    <>
      <Alert
        message="智能优化建议"
        description="基于用户查询历史分析，生成 Skill 配置优化建议。建议需管理员确认后应用。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      <Row justify="end" style={{ marginBottom: 16 }}>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => handleFetchOptimizations(true)} loading={optimizeLoading}>
            刷新分析
          </Button>
        </Space>
      </Row>
      <Table
        dataSource={optimizeSuggestions}
        rowKey="id"
        loading={optimizeLoading}
        columns={[
          {
            title: '优先级',
            dataIndex: 'priority',
            key: 'priority',
            width: 80,
            render: (p: string) => (
              <Tag color={p === 'high' ? 'red' : p === 'medium' ? 'orange' : 'default'}>
                {p === 'high' ? '高' : p === 'medium' ? '中' : '低'}
              </Tag>
            ),
          },
          { title: '建议', dataIndex: 'title', key: 'title' },
          { title: '说明', dataIndex: 'description', key: 'description', ellipsis: true },
          {
            title: '查询数',
            dataIndex: 'query_count',
            key: 'query_count',
            width: 80,
          },
          {
            title: '示例',
            dataIndex: 'example_queries',
            key: 'example_queries',
            render: (examples: string[]) => (
              <Tooltip title={examples?.join('\n')}>
                <Text type="secondary">{examples?.length || 0} 个示例</Text>
              </Tooltip>
            ),
          },
          {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, record: OptimizationSuggestion) => (
              <Button type="link" size="small" onClick={() => handleApplyOptimization(record.id)}>
                应用
              </Button>
            ),
          },
        ]}
        locale={{ emptyText: <Empty description='点击"刷新分析"获取优化建议' /> }}
      />
    </>
  );

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
            {/* Connection Selector Removed - handled globally */}
          </Col>
        </Row>

        {/* 顶级 Tab 切换 */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as any)}
          items={[
            {
              key: 'list',
              label: (
                <Space>
                  <TableOutlined />
                  Skills 列表
                </Space>
              ),
              children: renderSkillsList(),
            },
            {
              key: 'discover',
              label: (
                <Space>
                  <RocketOutlined />
                  自动发现
                </Space>
              ),
              children: renderDiscover(),
            },
            {
              key: 'optimize',
              label: (
                <Space>
                  <BulbOutlined />
                  优化建议
                </Space>
              ),
              children: renderOptimize(),
            },
          ]}
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
