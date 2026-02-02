import React, { useState, useEffect } from 'react';
import { 
  Table, Card, Button, Modal, Form, Input, 
  Select, Switch, Space, Tag, message, Tooltip, Popconfirm, Badge 
} from 'antd';
import { 
  PlusOutlined, EditOutlined, DeleteOutlined, 
  ApiOutlined, CheckCircleOutlined, CloseCircleOutlined, StarOutlined, StarFilled 
} from '@ant-design/icons';
import { 
  getLLMConfigs, createLLMConfig, updateLLMConfig, 
  deleteLLMConfig, testLLMConfig, LLMConfig,
  getAgentProfileByName, createAgentProfile, updateAgentProfile
} from '../../services/llmConfig';
import { 
  getDefaultEmbeddingModel, setDefaultEmbeddingModel, clearDefaultEmbeddingModel 
} from '../../services/systemConfig';
import { Divider, Typography, Row, Col } from 'antd';

const { Option } = Select;
const { Title, Text } = Typography;

const CORE_AGENTS = [
  { 
    name: 'sql_generator_core', 
    label: 'SQL 生成专家 (SQL Generator)', 
    desc: '负责将自然语言转换为 SQL。推荐使用逻辑能力强的模型 (如 DeepSeek-V3, GPT-4o)。' 
  },
  { 
    name: 'chart_analyst_core', 
    label: '数据分析专家 (Data Analyst)', 
    desc: '系统默认分析师。负责数据解读与可视化。当未指定行业专家时使用。' 
  },
  {
    name: 'router_core',
    label: '意图识别路由 (Router)',
    desc: '负责判断用户意图（闲聊 vs 查询）。推荐使用轻量级快速模型 (如 GPT-4o-mini)。'
  }
];

const LLMConfigPage: React.FC = () => {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 系统组件配置状态
  const [coreAgentConfigs, setCoreAgentConfigs] = useState<Record<string, number | null>>({});
  const [agentLoading, setAgentLoading] = useState(false);
  
  // Embedding默认模型配置
  const [defaultEmbeddingId, setDefaultEmbeddingId] = useState<number | null>(null);

  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [form] = Form.useForm();

  const extractApiErrorMessage = (error: any): string | undefined => {
    const responseData = error?.response?.data;
    const detail = responseData?.detail ?? responseData?.message;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first?.msg === 'string') return first.msg;
      if (typeof first === 'string') return first;
    }
    if (typeof error?.message === 'string') return error.message;
    return undefined;
  };

  const normalizeProvider = (provider: unknown): string | undefined => {
    const raw = Array.isArray(provider) ? provider[0] : provider;
    const s = typeof raw === 'string' ? raw.trim() : '';
    return s ? s.toLowerCase() : undefined;
  };

  const normalizeOptionalString = (value: unknown): string | undefined => {
    const s = typeof value === 'string' ? value.trim() : '';
    return s ? s : undefined;
  };

  const normalizeFormValues = (values: any, isEditing: boolean) => {
    const normalized: any = {
      ...values,
      provider: normalizeProvider(values?.provider),
      model_name: normalizeOptionalString(values?.model_name),
      base_url: normalizeOptionalString(values?.base_url),
      api_key: normalizeOptionalString(values?.api_key),
    };

    if (isEditing && !normalized.api_key) {
      delete normalized.api_key;
    }

    return normalized;
  };

  // 加载配置列表
  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const response = await getLLMConfigs();
      // axios 响应结构处理，如果 api.ts 返回的是 response.data
      setConfigs(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to load configs:', error);
      message.error(extractApiErrorMessage(error) || '加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载系统组件配置
  const fetchCoreAgentConfigs = async () => {
    setAgentLoading(true);
    const newConfigs: Record<string, number | null> = {};
    
    try {
      for (const agent of CORE_AGENTS) {
        const profile = await getAgentProfileByName(agent.name);
        if (profile && profile.llm_config_id) {
          newConfigs[agent.name] = profile.llm_config_id;
        } else {
          newConfigs[agent.name] = null; // 默认为 null (使用全局)
        }
      }
      setCoreAgentConfigs(newConfigs);
    } catch (error) {
      console.error('Failed to load core agent configs:', error);
    } finally {
      setAgentLoading(false);
    }
  };

  // 加载默认Embedding配置
  const fetchDefaultEmbedding = async () => {
    try {
      const response = await getDefaultEmbeddingModel();
      if (response.data.source === 'database' && response.data.llm_config_id) {
        setDefaultEmbeddingId(response.data.llm_config_id);
      } else {
        setDefaultEmbeddingId(null);
      }
    } catch (error) {
      console.error('Failed to load default embedding config:', error);
    }
  };

  useEffect(() => {
    fetchConfigs();
    fetchCoreAgentConfigs();
    fetchDefaultEmbedding();
  }, []);

  // 处理系统组件模型变更
  const handleCoreAgentChange = async (agentName: string, llmConfigId: number | null) => {
    setAgentLoading(true);
    try {
      // 1. 检查是否存在 Profile
      let profile = await getAgentProfileByName(agentName);
      
      if (profile) {
        // 更新
        await updateAgentProfile(profile.id, { llm_config_id: llmConfigId });
      } else {
        // 创建
        const agentDef = CORE_AGENTS.find(a => a.name === agentName);
        await createAgentProfile({
          name: agentName,
          role_description: agentDef?.label || 'System Core Agent',
          system_prompt: 'System Internal Agent',
          is_active: true,
          is_system: true,
          llm_config_id: llmConfigId
        });
      }
      
      message.success('设置已更新');
      // 更新本地状态
      setCoreAgentConfigs(prev => ({ ...prev, [agentName]: llmConfigId }));
      
    } catch (error) {
      console.error('Failed to update agent config:', error);
      message.error('更新失败');
    } finally {
      setAgentLoading(false);
    }
  };

  // 处理表单提交
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const payload = normalizeFormValues(values, Boolean(editingId));
      
      if (editingId) {
        await updateLLMConfig(editingId, payload);
        message.success('配置更新成功');
      } else {
        await createLLMConfig(payload);
        message.success('配置创建成功');
      }
      
      setModalVisible(false);
      form.resetFields();
      setEditingId(null);
      fetchConfigs();
    } catch (error: any) {
      console.error('Operation failed:', error);
      if (Array.isArray(error?.errorFields) && error.errorFields.length > 0) {
        message.error('请检查表单填写项');
        return;
      }
      message.error(extractApiErrorMessage(error) || '操作失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 处理编辑
  const handleEdit = (record: LLMConfig) => {
    setEditingId(record.id);
    form.setFieldsValue({
      ...record,
      provider: record.provider ? [record.provider] : [], // Adapt for Select mode="tags"
      api_key: undefined, // 编辑时不显示原有 API Key，除非用户想重置
    });
    setModalVisible(true);
  };

  // 处理删除
  const handleDelete = async (id: number) => {
    try {
      await deleteLLMConfig(id);
      message.success('删除成功');
      fetchConfigs();
      // 重新加载系统智能体配置，因为可能有智能体使用了被删除的配置
      fetchCoreAgentConfigs();
      fetchDefaultEmbedding();
    } catch (error: any) {
      console.error('Delete failed:', error);
      // 显示详细的错误信息
      if (error.response?.status === 400) {
        message.error(error.response.data.detail || '该配置正在被使用，请先解除绑定');
      } else if (error.response?.status === 404) {
        message.error('配置不存在');
      } else {
        message.error('删除失败，请稍后重试');
      }
    }
  };

  // 处理设置默认Embedding
  const handleSetDefaultEmbedding = async (id: number) => {
    try {
      await setDefaultEmbeddingModel(id);
      message.success('已设置为默认Embedding模型');
      setDefaultEmbeddingId(id);
    } catch (error: any) {
      console.error('Set default embedding failed:', error);
      message.error(error.response?.data?.detail || '设置失败');
    }
  };

  // 处理清除默认Embedding
  const handleClearDefaultEmbedding = async () => {
    try {
      await clearDefaultEmbeddingModel();
      message.success('已清除默认Embedding模型，将使用环境变量配置');
      setDefaultEmbeddingId(null);
    } catch (error: any) {
      console.error('Clear default embedding failed:', error);
      message.error('清除失败');
    }
  };

  // 测试连接
  const handleTestConnection = async () => {
    try {
      const values = await form.getFieldsValue();
      const payload = normalizeFormValues(values, Boolean(editingId));
      if (!payload.provider || !payload.model_name) {
        message.warning('请先填写提供商和模型名称');
        return;
      }
      if (!payload.api_key) {
        message.warning('请先填写 API Key');
        return;
      }
      
      setTestingConnection(true);
      const res = await testLLMConfig(payload);
      if (res.data && res.data.success) {
        message.success(`连接成功: ${res.data.message}`);
      } else {
        message.error(`连接失败: ${res.data?.message || '未知错误'}`);
      }
    } catch (error: any) {
      message.error(extractApiErrorMessage(error) || `连接测试出错: ${error.message || '网络错误'}`);
    } finally {
      setTestingConnection(false);
    }
  };

  const columns = [
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '模型名称',
      dataIndex: 'model_name',
      key: 'model_name',
      render: (text: string, record: LLMConfig) => (
        <Space>
          <strong>{text}</strong>
          {record.model_type === 'embedding' && record.id === defaultEmbeddingId && (
            <Badge count="默认" style={{ backgroundColor: '#52c41a' }} />
          )}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'model_type',
      key: 'model_type',
      render: (text: string) => (
        <Tag color={text === 'chat' ? 'green' : 'orange'}>
          {text === 'chat' ? '对话 (Chat)' : '嵌入 (Embedding)'}
        </Tag>
      ),
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      key: 'base_url',
      render: (text: string) => text || <span style={{ color: '#ccc' }}>默认</span>,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean) => (
        isActive ? 
          <Tag icon={<CheckCircleOutlined />} color="success">启用</Tag> : 
          <Tag icon={<CloseCircleOutlined />} color="default">禁用</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: LLMConfig) => (
        <Space size="middle">
          {record.model_type === 'embedding' && record.is_active && (
            record.id === defaultEmbeddingId ? (
              <Tooltip title="清除默认">
                <Popconfirm
                  title="确定清除默认Embedding模型吗？系统将使用环境变量配置。"
                  onConfirm={handleClearDefaultEmbedding}
                  okText="是"
                  cancelText="否"
                >
                  <Button 
                    type="text" 
                    icon={<StarFilled style={{ color: '#faad14' }} />}
                  />
                </Popconfirm>
              </Tooltip>
            ) : (
              <Tooltip title="设为默认">
                <Button 
                  type="text" 
                  icon={<StarOutlined />} 
                  onClick={() => handleSetDefaultEmbedding(record.id)} 
                />
              </Tooltip>
            )
          )}
          <Tooltip title="编辑">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => handleEdit(record)} 
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除此配置吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Tooltip title="删除">
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card
        title="模型配置管理 (LLM Configuration)"
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={() => {
              setEditingId(null);
              form.resetFields();
              form.setFieldsValue({ 
                model_type: 'chat', 
                is_active: true,
                provider: ['OpenAI']
              });
              setModalVisible(true);
            }}
          >
            新建配置
          </Button>
        }
      >
        <Table 
          columns={columns} 
          dataSource={configs} 
          rowKey="id" 
          loading={loading}
          pagination={false}
        />
        
        <Divider style={{ margin: '32px 0' }} />
        
        <Title level={4}>系统核心组件模型绑定 (System Agent Binding)</Title>
        <Text type="secondary">在此处为系统的核心功能指定专用的模型。未指定时将使用系统默认模型。</Text>
        
        <div style={{ marginTop: 24 }}>
          <Row gutter={[24, 24]}>
            {CORE_AGENTS.map(agent => (
              <Col span={8} key={agent.name}>
                <Card title={agent.label} size="small" hoverable>
                  <p style={{ height: 60, color: '#666', fontSize: 13 }}>{agent.desc}</p>
                  <div style={{ marginTop: 16 }}>
                    <Text strong>绑定模型: </Text>
                    <Select
                      style={{ width: '100%', marginTop: 8 }}
                      placeholder="使用全局默认"
                      allowClear
                      loading={agentLoading}
                      value={coreAgentConfigs[agent.name]}
                      onChange={(val) => handleCoreAgentChange(agent.name, val)}
                    >
                      {configs
                        .filter(c => c.is_active && c.model_type === 'chat')
                        .map(c => (
                          <Option key={c.id} value={c.id}>
                            {c.provider} - {c.model_name}
                          </Option>
                      ))}
                    </Select>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      </Card>

      <Modal
        title={editingId ? "编辑模型配置" : "新建模型配置"}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={[
          <Button key="test" icon={<ApiOutlined />} loading={testingConnection} onClick={handleTestConnection}>
            测试连接
          </Button>,
          <Button key="cancel" onClick={() => setModalVisible(false)}>
            取消
          </Button>,
          <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
            保存
          </Button>,
        ]}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ model_type: 'chat', is_active: true }}
        >
          <Form.Item
            name="provider"
            label="提供商 (Provider)"
            rules={[{ required: true, message: '请输入提供商名称' }]}
          >
            <Select placeholder="选择或输入提供商" mode="tags" maxTagCount={1}>
              {/* OpenAI 兼容层 - 国内外主流模型 */}
              <Option value="OpenAI">OpenAI</Option>
              <Option value="DeepSeek">DeepSeek (深度求索)</Option>
              <Option value="Aliyun">Aliyun (通义千问)</Option>
              <Option value="Volcengine">Volcengine (火山引擎/豆包)</Option>
              <Option value="Moonshot">Moonshot (月之暗面)</Option>
              <Option value="Zhipu">Zhipu (智谱AI)</Option>
              <Option value="Baichuan">Baichuan (百川)</Option>
              <Option value="MiniMax">MiniMax</Option>
              <Option value="SiliconFlow">SiliconFlow (硅基流动)</Option>
              {/* 其他平台 */}
              <Option value="Azure">Azure OpenAI</Option>
              <Option value="OpenRouter">OpenRouter (聚合平台)</Option>
              <Option value="Ollama">Ollama (本地部署)</Option>
              {/* 需要专用SDK的模型 */}
              <Option value="Baidu">Baidu (百度千帆)</Option>
              <Option value="Google">Google (Gemini)</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="model_name"
            label="模型名称 (Model Name)"
            rules={[{ required: true, message: '请输入模型名称，如 gpt-4o' }]}
            tooltip="例如: gpt-3.5-turbo, gpt-4, claude-3-opus"
          >
            <Input placeholder="gpt-3.5-turbo" />
          </Form.Item>

          <Form.Item
            name="model_type"
            label="模型类型"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="chat">对话模型 (Chat)</Option>
              <Option value="embedding">向量模型 (Embedding)</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: !editingId, message: '请输入 API Key' }]}
            tooltip={editingId ? "留空则不修改原 API Key" : undefined}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Form.Item
            name="base_url"
            label="Base URL (可选)"
            tooltip="如果是代理地址或本地模型(如Ollama)，请填写完整的 API 基础路径"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="是否启用"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default LLMConfigPage;
