
// 混合问答对管理页面

import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Switch,
  message,
  Tabs,
  Row,
  Col,
  Statistic,
  Progress,
  Tooltip,
  Divider,
  Slider
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  ExportOutlined,
  ImportOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  RobotOutlined,
  DatabaseOutlined,
  BulbOutlined,
  QuestionCircleOutlined,
  SettingOutlined
} from '@ant-design/icons';
import '../../styles/HybridQA.css';
import { hybridQAService } from '../../services/hybridQA';
import { getConnections } from '../../services/api';
import { getQASampleConfig, updateQASampleConfig, type QASampleConfig } from '../../services/systemConfig';
import QAFeedbackModal from '../../components/QAFeedbackModal';
import type { QAPair, SimilarQAPair, QAPairCreate } from '../../types/hybridQA';
import type { DBConnection } from '../../types/api';

const { TextArea } = Input;
const { Option } = Select;

// 内容组件 - 供复用（无外层 padding）
export const HybridQAContent: React.FC = () => {
  const [qaPairs, setQaPairs] = useState<QAPair[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [searchModalVisible, setSearchModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [feedbackModalVisible, setFeedbackModalVisible] = useState(false);
  const [selectedQAPair, setSelectedQAPair] = useState<QAPair | null>(null);
  const [editingQAPair, setEditingQAPair] = useState<any>(null);
  const [searchResults, setSearchResults] = useState<SimilarQAPair[]>([]);
  const [stats, setStats] = useState<any>({});
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [loadingConnections, setLoadingConnections] = useState(false);
  
  // QA 样本检索配置状态
  const [qaSampleConfig, setQaSampleConfig] = useState<QASampleConfig>({
    enabled: true,
    top_k: 3,
    min_similarity: 0.6,
    timeout_seconds: 5
  });
  const [configLoading, setConfigLoading] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [searchForm] = Form.useForm();
  const [configForm] = Form.useForm();

  useEffect(() => {
    loadConnections();
    loadStats();
    loadQAPairs();
    loadQASampleConfig();
  }, []);

  useEffect(() => {
    if (selectedConnectionId) {
      loadStats(selectedConnectionId);
      loadQAPairs(selectedConnectionId);
    } else {
      loadQAPairs();
    }
  }, [selectedConnectionId]);

  const loadQAPairs = async (connectionId?: number) => {
    try {
      setLoading(true);
      const response = await hybridQAService.getQAPairs(connectionId, 100);
      setQaPairs(response);
    } catch (error) {
      console.error('加载问答对列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadConnections = async () => {
    try {
      setLoadingConnections(true);
      const response = await getConnections();
      setConnections(response.data);
    } catch (error) {
      message.error('获取数据库连接失败');
      console.error('获取连接失败:', error);
    } finally {
      setLoadingConnections(false);
    }
  };

  const loadStats = async (connectionId?: number) => {
    try {
      const response = await hybridQAService.getStats(connectionId);
      setStats(response);
    } catch (error) {
      console.error('加载统计信息失败:', error);
    }
  };

  const loadQASampleConfig = async () => {
    try {
      setConfigLoading(true);
      const response = await getQASampleConfig();
      setQaSampleConfig(response.data);
    } catch (error) {
      console.error('加载QA样本配置失败:', error);
    } finally {
      setConfigLoading(false);
    }
  };

  const handleUpdateConfig = async (values: QASampleConfig) => {
    try {
      setConfigLoading(true);
      await updateQASampleConfig(values);
      setQaSampleConfig(values);
      message.success('QA样本检索配置已更新');
      setShowConfigModal(false);
    } catch (error) {
      message.error('更新配置失败');
      console.error('更新QA样本配置失败:', error);
    } finally {
      setConfigLoading(false);
    }
  };

  const handleToggleEnabled = async (enabled: boolean) => {
    const newConfig = { ...qaSampleConfig, enabled };
    await handleUpdateConfig(newConfig);
  };

  const handleCreateQAPair = async (values: QAPairCreate) => {
    try {
      setLoading(true);
      await hybridQAService.createQAPair(values);
      message.success('问答对创建成功');
      setCreateModalVisible(false);
      form.resetFields();
      loadStats(selectedConnectionId || undefined); // 重新加载统计信息
      loadQAPairs(selectedConnectionId || undefined); // 重新加载问答对列表
    } catch (error) {
      message.error('创建失败');
      console.error('创建问答对失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSimilar = async (values: any) => {
    try {
      setLoading(true);
      const results = await hybridQAService.searchSimilar({
        question: values.question,
        connection_id: values.connection_id || selectedConnectionId,
        top_k: values.top_k || 5
      });
      setSearchResults(results);
    } catch (error) {
      message.error('搜索失败');
      console.error('搜索相似问答对失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = (qaPair: QAPair) => {
    setSelectedQAPair(qaPair);
    setDetailModalVisible(true);
  };

  const handleEditQAPair = (record: any) => {
    setEditingQAPair(record);
    editForm.setFieldsValue({
      question: record.question,
      sql: record.sql,
      query_type: record.query_type,
      difficulty_level: record.difficulty_level,
      verified: record.verified
    });
    setEditModalVisible(true);
  };

  const handleUpdateQAPair = async (values: any) => {
    if (!editingQAPair) return;
    
    try {
      setLoading(true);
      await hybridQAService.updateQAPair(editingQAPair.id, values);
      message.success('问答对更新成功');
      setEditModalVisible(false);
      editForm.resetFields();
      setEditingQAPair(null);
      loadStats(selectedConnectionId || undefined);
      loadQAPairs(selectedConnectionId || undefined);
    } catch (error) {
      message.error('更新失败');
      console.error('更新问答对失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteQAPair = async (qaId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个问答对吗？此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          setLoading(true);
          await hybridQAService.deleteQAPair(qaId);
          message.success('删除成功');
          loadStats(selectedConnectionId || undefined);
          loadQAPairs(selectedConnectionId || undefined);
        } catch (error) {
          message.error('删除失败');
          console.error('删除问答对失败:', error);
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const getQueryTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      'SELECT': 'blue',
      'JOIN': 'green',
      'AGGREGATE': 'orange',
      'GROUP_BY': 'purple',
      'ORDER_BY': 'cyan'
    };
    return colors[type] || 'default';
  };

  const getDifficultyColor = (level: number) => {
    const colors = ['#52c41a', '#1890ff', '#faad14', '#ff7a45', '#f5222d'];
    return colors[level - 1] || '#d9d9d9';
  };

  // 问答对列表的列定义
  const listColumns = [
    {
      title: '问题',
      dataIndex: 'question',
      key: 'question',
      ellipsis: true,
      width: 300,
    },
    {
      title: 'SQL',
      dataIndex: 'sql',
      key: 'sql',
      ellipsis: true,
      width: 400,
      render: (sql: string) => (
        <code className="hybrid-qa-code-block">
          {sql}
        </code>
      ),
    },
    {
      title: '查询类型',
      dataIndex: 'query_type',
      key: 'query_type',
      width: 100,
      render: (type: string) => (
        <Tag color={getQueryTypeColor(type)}>{type}</Tag>
      ),
    },
    {
      title: '难度',
      dataIndex: 'difficulty_level',
      key: 'difficulty_level',
      width: 80,
      render: (level: number) => (
        <Tag color={getDifficultyColor(level)} className="hybrid-qa-tag-difficulty">
          {level}
        </Tag>
      ),
    },
    {
      title: '已验证',
      dataIndex: 'verified',
      key: 'verified',
      width: 80,
      render: (verified: boolean) => (
        <Tag color={verified ? 'green' : 'default'}>
          {verified ? '是' : '否'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: any) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => {
                const qaPair: QAPair = {
                  id: record.id,
                  question: record.question,
                  sql: record.sql,
                  connection_id: record.connection_id,
                  query_type: record.query_type,
                  difficulty_level: record.difficulty_level,
                  success_rate: record.success_rate || 0,
                  verified: record.verified || false,
                  created_at: record.created_at || new Date().toISOString(),
                  used_tables: [],
                  mentioned_entities: []
                };
                handleViewDetail(qaPair);
              }}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEditQAPair(record)}
            />
          </Tooltip>
          <Tooltip title="删除">
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteQAPair(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const searchColumns = [
    {
      title: '问题',
      dataIndex: ['qa_pair', 'question'],
      key: 'question',
      ellipsis: true,
      width: 300,
    },
    {
      title: 'SQL',
      dataIndex: ['qa_pair', 'sql'],
      key: 'sql',
      ellipsis: true,
      width: 400,
      render: (sql: string) => (
        <code className="hybrid-qa-code-block">
          {sql}
        </code>
      ),
    },
    {
      title: '查询类型',
      dataIndex: ['qa_pair', 'query_type'],
      key: 'query_type',
      width: 100,
      render: (type: string) => (
        <Tag color={getQueryTypeColor(type)}>{type}</Tag>
      ),
    },
    {
      title: '数据库连接',
      dataIndex: ['qa_pair', 'connection_id'],
      key: 'connection_id',
      width: 120,
      render: (connectionId: number) => {
        const connection = connections.find(conn => conn.id === connectionId);
        return connection ? (
          <Tooltip title={`${connection.db_type} - ${connection.database_name}`}>
            <Tag color="blue">{connection.name}</Tag>
          </Tooltip>
        ) : (
          <Tag color="default">ID: {connectionId}</Tag>
        );
      },
    },
    {
      title: '相关度',
      dataIndex: 'final_score',
      key: 'final_score',
      width: 120,
      render: (score: number) => (
        <Progress
          percent={Math.round(score * 100)}
          size="small"
          status={score > 0.8 ? 'success' : score > 0.6 ? 'normal' : 'exception'}
        />
      ),
    },
    {
      title: '推荐理由',
      dataIndex: 'explanation',
      key: 'explanation',
      ellipsis: true,
      width: 200,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: SimilarQAPair) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record.qa_pair)}
            />
          </Tooltip>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setSelectedQAPair(record.qa_pair);
              setFeedbackModalVisible(true);
            }}
          >
            反馈
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="hybrid-qa-container">
      <Card title="混合检索问答对管理" className="hybrid-qa-card">
        {/* 数据库连接选择器 */}
        <div className="hybrid-qa-db-selector-container">
          <div>
            <span className="hybrid-qa-db-selector-label">数据库连接:</span>
            <Select
              placeholder="选择数据库连接（可选）"
              value={selectedConnectionId}
              onChange={setSelectedConnectionId}
              loading={loadingConnections}
              className="hybrid-qa-db-selector"
              allowClear
            >
              {connections.map(conn => (
                <Option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.db_type} - {conn.database_name})
                </Option>
              ))}
            </Select>
          </div>
          <Tooltip title="选择数据库连接后，统计信息和搜索结果将仅显示该连接下的问答对">
            <QuestionCircleOutlined className="hybrid-qa-icon-help" />
          </Tooltip>
        </div>

        <Row gutter={16} className="hybrid-qa-stats-row">
          <Col span={6}>
            <Statistic
              title="总问答对数"
              value={stats.total_qa_pairs || 0}
              prefix={<DatabaseOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="已验证数"
              value={stats.verified_qa_pairs || 0}
              prefix={<BulbOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="平均成功率"
              value={stats.average_success_rate || 0}
              precision={2}
              suffix="%"
              prefix={<RobotOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="验证率"
              value={stats.total_qa_pairs > 0 ?
                ((stats.verified_qa_pairs / stats.total_qa_pairs) * 100) : 0}
              precision={1}
              suffix="%"
            />
          </Col>
        </Row>

        {/* QA 样本检索配置 */}
        <Card 
          size="small" 
          className="hybrid-qa-config-card"
          title={
            <Space>
              <SettingOutlined />
              <span>QA 样本检索配置</span>
            </Space>
          }
          extra={
            <Button 
              type="link" 
              size="small"
              onClick={() => {
                configForm.setFieldsValue(qaSampleConfig);
                setShowConfigModal(true);
              }}
            >
              高级配置
            </Button>
          }
        >
          <Space size="large">
            <Space>
              <span>启用样本检索:</span>
              <Switch 
                checked={qaSampleConfig.enabled}
                onChange={handleToggleEnabled}
                loading={configLoading}
                checkedChildren="开"
                unCheckedChildren="关"
              />
            </Space>
            <Tooltip title="检索数量">
              <Tag color="blue">Top-K: {qaSampleConfig.top_k}</Tag>
            </Tooltip>
            <Tooltip title="最低相似度阈值">
              <Tag color="green">相似度: {(qaSampleConfig.min_similarity * 100).toFixed(0)}%</Tag>
            </Tooltip>
            <Tooltip title="检索超时时间">
              <Tag color="orange">超时: {qaSampleConfig.timeout_seconds}s</Tag>
            </Tooltip>
          </Space>
        </Card>

        <Space className="hybrid-qa-action-bar">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateModalVisible(true);
              // 如果选择了连接，设置为默认值
              if (selectedConnectionId) {
                form.setFieldsValue({ connection_id: selectedConnectionId });
              }
            }}
          >
            创建问答对
          </Button>
          <Button
            icon={<SearchOutlined />}
            onClick={() => {
              setSearchModalVisible(true);
              // 如果选择了连接，设置为默认值
              if (selectedConnectionId) {
                searchForm.setFieldsValue({ connection_id: selectedConnectionId });
              }
            }}
          >
            智能搜索
          </Button>
          <Button icon={<ImportOutlined />}>
            批量导入
          </Button>
          <Button icon={<ExportOutlined />}>
            导出数据
          </Button>
        </Space>

        <Tabs 
          defaultActiveKey="list"
          items={[
            {
              key: 'list',
              label: '问答对列表',
              children: (
                <Table
                  columns={listColumns}
                  dataSource={qaPairs}
                  loading={loading}
                  rowKey={(record) => record.id}
                  pagination={{
                    pageSize: 10,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条记录`,
                  }}
                  scroll={{ x: 1000 }}
                />
              )
            },
            {
              key: 'search',
              label: '智能搜索',
              children: (
                <>
                  <Card size="small" className="hybrid-qa-search-card">
                    <Form
                      form={searchForm}
                      layout="inline"
                      onFinish={handleSearchSimilar}
                    >
                      <Form.Item
                        name="question"
                        rules={[{ required: true, message: '请输入问题' }]}
                      >
                        <Input
                          placeholder="输入自然语言问题"
                          className="hybrid-qa-search-input"
                        />
                      </Form.Item>
                      <Form.Item name="connection_id">
                        <Select
                          placeholder="选择数据库连接"
                          className="hybrid-qa-search-select"
                          allowClear
                        >
                          {connections.map(conn => (
                            <Option key={conn.id} value={conn.id}>
                              {conn.name}
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                      <Form.Item name="top_k" initialValue={5}>
                        <InputNumber
                          placeholder="返回数量"
                          min={1}
                          max={20}
                          className="hybrid-qa-search-number"
                        />
                      </Form.Item>
                      <Form.Item>
                        <Button
                          type="primary"
                          htmlType="submit"
                          loading={loading}
                          icon={<SearchOutlined />}
                        >
                          搜索
                        </Button>
                      </Form.Item>
                    </Form>
                  </Card>

                  <Table
                    columns={searchColumns}
                    dataSource={searchResults}
                    loading={loading}
                    rowKey={(record) => record.qa_pair.id}
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: true,
                      showQuickJumper: true,
                      showTotal: (total) => `共 ${total} 条记录`,
                    }}
                    scroll={{ x: 1200 }}
                  />
                </>
              )
            },
            {
              key: 'stats',
              label: '统计分析',
              children: (
                <Row gutter={16}>
                  <Col span={12}>
                    <Card title="查询类型分布" size="small">
                      {stats.query_types && Object.entries(stats.query_types).map(([type, count]: [string, any]) => (
                        <div key={type} style={{ marginBottom: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Tag color={getQueryTypeColor(type)} style={{ fontSize: '12px' }}>{type}</Tag>
                            <span>{count}</span>
                          </div>
                          <Progress
                            percent={stats.total_qa_pairs > 0 ? (count / stats.total_qa_pairs) * 100 : 0}
                            size="small"
                            showInfo={false}
                          />
                        </div>
                      ))}
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card title="难度分布" size="small">
                      {stats.difficulty_distribution && Object.entries(stats.difficulty_distribution).map(([level, count]: [string, any]) => (
                        <div key={level} style={{ marginBottom: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>难度 {level}</span>
                            <span>{count}</span>
                          </div>
                          <Progress
                            percent={stats.total_qa_pairs > 0 ? (count / stats.total_qa_pairs) * 100 : 0}
                            size="small"
                            showInfo={false}
                            strokeColor={getDifficultyColor(parseInt(level))}
                          />
                        </div>
                      ))}
                    </Card>
                  </Col>
                </Row>
              )
            }
          ]}
        />
      </Card>

      {/* 创建问答对模态框 */}
      <Modal
        title="创建问答对"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        footer={null}
        width={800}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateQAPair}
        >
          <Form.Item
            name="question"
            label="自然语言问题"
            rules={[{ required: true, message: '请输入问题' }]}
          >
            <TextArea rows={3} placeholder="输入自然语言问题" />
          </Form.Item>

          <Form.Item
            name="sql"
            label="SQL语句"
            rules={[{ required: true, message: '请输入SQL语句' }]}
          >
            <TextArea rows={5} placeholder="输入对应的SQL语句" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="connection_id"
                label="数据库连接"
                rules={[{ required: true, message: '请选择数据库连接' }]}
              >
                <Select
                  style={{ width: '100%' }}
                  placeholder="选择数据库连接"
                  loading={loadingConnections}
                >
                  {connections.map(conn => (
                    <Option key={conn.id} value={conn.id}>
                      {conn.name} ({conn.db_type})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="query_type"
                label="查询类型"
                initialValue="SELECT"
              >
                <Select>
                  <Option value="SELECT">SELECT</Option>
                  <Option value="JOIN">JOIN</Option>
                  <Option value="AGGREGATE">AGGREGATE</Option>
                  <Option value="GROUP_BY">GROUP_BY</Option>
                  <Option value="ORDER_BY">ORDER_BY</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="difficulty_level"
                label="难度等级"
                initialValue={3}
              >
                <InputNumber min={1} max={5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="verified"
            label="已验证"
            valuePropName="checked"
            initialValue={false}
          >
            <Switch />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                创建
              </Button>
              <Button onClick={() => setCreateModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑问答对模态框 */}
      <Modal
        title="编辑问答对"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          editForm.resetFields();
          setEditingQAPair(null);
        }}
        footer={null}
        width={800}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdateQAPair}
        >
          <Form.Item
            name="question"
            label="自然语言问题"
            rules={[{ required: true, message: '请输入问题' }]}
          >
            <TextArea rows={3} placeholder="输入自然语言问题" />
          </Form.Item>

          <Form.Item
            name="sql"
            label="SQL语句"
            rules={[{ required: true, message: '请输入SQL语句' }]}
          >
            <TextArea rows={5} placeholder="输入对应的SQL语句" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="query_type"
                label="查询类型"
              >
                <Select>
                  <Option value="SELECT">SELECT</Option>
                  <Option value="JOIN">JOIN</Option>
                  <Option value="AGGREGATE">AGGREGATE</Option>
                  <Option value="GROUP_BY">GROUP_BY</Option>
                  <Option value="ORDER_BY">ORDER_BY</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="difficulty_level"
                label="难度等级"
              >
                <InputNumber min={1} max={5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="verified"
                label="已验证"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                保存
              </Button>
              <Button onClick={() => {
                setEditModalVisible(false);
                editForm.resetFields();
                setEditingQAPair(null);
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情模态框 */}
      <Modal
        title="问答对详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedQAPair && (
          <div>
            <Divider orientation="left">基本信息</Divider>
            <Row gutter={16}>
              <Col span={12}>
                <p><strong>ID:</strong> {selectedQAPair.id}</p>
                <p><strong>查询类型:</strong> <Tag color={getQueryTypeColor(selectedQAPair.query_type)}>{selectedQAPair.query_type}</Tag></p>
                <p><strong>难度等级:</strong> {selectedQAPair.difficulty_level}</p>
                <p><strong>数据库连接:</strong> {(() => {
                  const connection = connections.find(conn => conn.id === selectedQAPair.connection_id);
                  return connection ? (
                    <Tag color="blue">{connection.name} ({connection.db_type})</Tag>
                  ) : (
                    <Tag color="default">ID: {selectedQAPair.connection_id}</Tag>
                  );
                })()}</p>
              </Col>
              <Col span={12}>
                <p><strong>成功率:</strong> {(selectedQAPair.success_rate * 100).toFixed(1)}%</p>
                <p><strong>已验证:</strong> {selectedQAPair.verified ? '是' : '否'}</p>
                <p><strong>创建时间:</strong> {new Date(selectedQAPair.created_at).toLocaleString()}</p>
              </Col>
            </Row>

            <Divider orientation="left">问题</Divider>
            <p style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px' }}>
              {selectedQAPair.question}
            </p>

            <Divider orientation="left">SQL语句</Divider>
            <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', overflow: 'auto' }}>
              {selectedQAPair.sql}
            </pre>

            <Divider orientation="left">使用的表</Divider>
            <div>
              {selectedQAPair.used_tables?.map((table, index) => (
                <Tag key={index} color="blue">{table}</Tag>
              ))}
            </div>

            <Divider orientation="left">提及的实体</Divider>
            <div>
              {selectedQAPair.mentioned_entities?.map((entity, index) => (
                <Tag key={index} color="green">{entity}</Tag>
              ))}
            </div>
          </div>
        )}
      </Modal>

      {/* 反馈模态框 */}
      <QAFeedbackModal
        visible={feedbackModalVisible}
        onCancel={() => setFeedbackModalVisible(false)}
        qaPair={selectedQAPair}
        onFeedbackSubmitted={() => {
          // 重新加载统计信息
          loadStats(selectedConnectionId || undefined);
        }}
      />

      {/* QA 样本检索配置弹窗 */}
      <Modal
        title="QA 样本检索高级配置"
        open={showConfigModal}
        onCancel={() => setShowConfigModal(false)}
        onOk={() => configForm.submit()}
        confirmLoading={configLoading}
        width={500}
      >
        <Form
          form={configForm}
          layout="vertical"
          onFinish={handleUpdateConfig}
          initialValues={qaSampleConfig}
        >
          <Form.Item
            name="enabled"
            label="启用 QA 样本检索"
            valuePropName="checked"
            extra="开启后，系统会在生成 SQL 时检索相似的历史问答对作为参考"
          >
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>

          <Form.Item
            name="top_k"
            label="检索数量 (Top-K)"
            extra="每次检索返回的最相似样本数量"
            rules={[{ required: true, message: '请输入检索数量' }]}
          >
            <Slider min={1} max={10} marks={{ 1: '1', 3: '3', 5: '5', 10: '10' }} />
          </Form.Item>

          <Form.Item
            name="min_similarity"
            label="最低相似度阈值"
            extra="只返回相似度高于此阈值的样本"
            rules={[{ required: true, message: '请输入相似度阈值' }]}
          >
            <Slider 
              min={0} 
              max={1} 
              step={0.1} 
              marks={{ 0: '0%', 0.5: '50%', 0.6: '60%', 0.8: '80%', 1: '100%' }}
              tooltip={{ formatter: (v) => `${((v || 0) * 100).toFixed(0)}%` }}
            />
          </Form.Item>

          <Form.Item
            name="timeout_seconds"
            label="检索超时时间 (秒)"
            extra="超过此时间未完成检索将跳过样本增强"
            rules={[{ required: true, message: '请输入超时时间' }]}
          >
            <InputNumber min={1} max={30} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// 独立页面组件 - 保持向后兼容
const HybridQAPage: React.FC = () => {
  return (
    <div style={{ padding: '24px' }}>
      <HybridQAContent />
    </div>
  );
};

export default HybridQAPage;
