import React, { useState, useEffect } from 'react';
import { 
  Table, Card, Button, Modal, Form, Input, 
  Select, Switch, Space, Tag, message, Tooltip, Popconfirm 
} from 'antd';
import { 
  PlusOutlined, EditOutlined, DeleteOutlined, 
  CheckCircleOutlined, CloseCircleOutlined, UserOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import { 
  getAgentProfiles, createAgentProfile, updateAgentProfile, 
  deleteAgentProfile, optimizeAgentPrompt, AgentProfile 
} from '../../services/agentProfile';
import { getLLMConfigs, LLMConfig } from '../../services/llmConfig';

const { Option } = Select;
const { TextArea } = Input;

const AgentProfilePage: React.FC = () => {
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [llmConfigs, setLlmConfigs] = useState<LLMConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [form] = Form.useForm();

  // 加载数据
  const fetchData = async () => {
    setLoading(true);
    try {
      const [profilesRes, llmRes] = await Promise.all([
        getAgentProfiles({ is_system: false }),
        getLLMConfigs()
      ]);
      setProfiles(Array.isArray(profilesRes.data) ? profilesRes.data : []);
      setLlmConfigs(Array.isArray(llmRes.data) ? llmRes.data : []);
    } catch (error) {
      console.error('Failed to load data:', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // 处理表单提交
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      
      if (editingId) {
        await updateAgentProfile(editingId, values);
        message.success('配置更新成功');
      } else {
        await createAgentProfile(values);
        message.success('配置创建成功');
      }
      
      setModalVisible(false);
      form.resetFields();
      setEditingId(null);
      fetchData();
    } catch (error) {
      console.error('Operation failed:', error);
      message.error('操作失败，请检查输入');
    } finally {
      setLoading(false);
    }
  };

  // 处理编辑
  const handleEdit = (record: AgentProfile) => {
    setEditingId(record.id);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  // 处理删除
  const handleDelete = async (id: number) => {
    try {
      await deleteAgentProfile(id);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 处理智能优化
  const handleOptimize = async () => {
    const description = form.getFieldValue('role_description');
    if (!description) {
      message.warning('请先填写角色描述，以便生成更准确的提示词');
      return;
    }
    
    setOptimizing(true);
    try {
      const res = await optimizeAgentPrompt(description);
      form.setFieldsValue({ system_prompt: res.data });
      message.success('提示词优化成功');
    } catch (error) {
      console.error('Optimization failed:', error);
      message.error('优化失败，请稍后重试');
    } finally {
      setOptimizing(false);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Space>
          <UserOutlined />
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: '角色描述',
      dataIndex: 'role_description',
      key: 'role_description',
      ellipsis: true,
    },
    {
      title: '绑定模型',
      dataIndex: 'llm_config_id',
      key: 'llm_config_id',
      render: (id: number) => {
        const config = llmConfigs.find(c => c.id === id);
        return config ? <Tag color="blue">{config.model_name}</Tag> : <Tag>默认</Tag>;
      },
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
      render: (_: any, record: AgentProfile) => (
        <Space size="middle">
          <Tooltip title="编辑">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => handleEdit(record)} 
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除此智能体吗？"
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
        title="智能体配置 (Agent Configuration)"
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={() => {
              setEditingId(null);
              form.resetFields();
              form.setFieldsValue({ 
                is_active: true,
                tools: ['chart_analyst_core']
              });
              setModalVisible(true);
            }}
          >
            新建智能体
          </Button>
        }
      >
        <Table 
          columns={columns} 
          dataSource={profiles} 
          rowKey="id" 
          loading={loading}
        />
      </Card>

      <Modal
        title={editingId ? "编辑智能体配置" : "新建智能体配置"}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        confirmLoading={loading}
        width={700}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ is_active: true }}
        >
          <Form.Item
            name="name"
            label="智能体名称 (Agent Name)"
            rules={[{ required: true, message: '请输入智能体名称' }]}
          >
            <Input placeholder="例如：销售数据分析师" />
          </Form.Item>

          <Form.Item
            name="role_description"
            label="角色描述"
            rules={[{ required: true, message: '请输入角色描述' }]}
          >
            <Input placeholder="例如：负责分析销售数据，生成销售报表" />
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label={
              <Space>
                <span>系统提示词 (System Prompt)</span>
                <Button 
                  type="link" 
                  size="small" 
                  icon={<ThunderboltOutlined />} 
                  loading={optimizing}
                  onClick={handleOptimize}
                >
                  一键优化
                </Button>
              </Space>
            }
            tooltip="定义智能体的行为、语气和限制"
          >
            <TextArea rows={6} placeholder="你是一个专业的销售数据分析师..." />
          </Form.Item>
          
          <Form.Item
            name="llm_config_id"
            label="绑定模型配置 (可选)"
            tooltip="如果不选择，将使用系统默认模型"
          >
            <Select placeholder="使用系统默认" allowClear>
              {llmConfigs.filter(c => c.is_active && c.model_type === 'chat').map(config => (
                <Option key={config.id} value={config.id}>
                  {config.provider} - {config.model_name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="tools"
            label="专家能力配置 (Capabilities)"
          >
            <Select mode="multiple" placeholder="请选择专家具备的能力">
              <Option value="chart_analyst_core">图表生成与可视化分析</Option>
            </Select>
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

export default AgentProfilePage;
