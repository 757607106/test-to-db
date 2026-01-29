/**
 * GuidedMiningWizard 组件
 * 智能挖掘向导：基于业务数据、指标、语义等多维度挖掘数据洞察
 * 支持可解释性展示：推荐理由、数据来源、SQL逻辑
 */
import React, { useState, useEffect } from 'react';
import {
  Modal,
  Steps,
  Button,
  Input,
  Select,
  Card,
  Checkbox,
  message,
  Spin,
  Row,
  Col,
  Typography,
  Empty,
  Space,
  Tag,
  Tooltip,
  Collapse,
  Progress,
  Divider,
  Slider,
} from 'antd';
import {
  DatabaseOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  QuestionCircleOutlined,
  CodeOutlined,
  TableOutlined,
  RightOutlined,
  DownOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  LineChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
  DotChartOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { dashboardService } from '../services/dashboardService';
import { getConnections } from '../services/api';

const { Step } = Steps;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

// 挖掘建议类型
interface MiningSuggestion {
  title: string;
  description: string;
  sql: string;
  chart_type: string;
  analysis_intent: string;
  reasoning?: string;
  mining_dimension?: string;
  confidence?: number;
  source_tables?: string[];
  key_fields?: string[];
  business_value?: string;
  suggested_actions?: string[];
}

interface GuidedMiningWizardProps {
  visible: boolean;
  dashboardId: number;
  connectionId?: number;
  onClose: () => void;
  onSuccess: () => void;
}

// 挖掘维度配置
const MINING_DIMENSIONS = [
  { value: 'business', label: '业务数据', color: 'blue', icon: <BarChartOutlined /> },
  { value: 'metric', label: '指标分析', color: 'green', icon: <LineChartOutlined /> },
  { value: 'trend', label: '趋势分析', color: 'orange', icon: <LineChartOutlined /> },
  { value: 'semantic', label: '语义关联', color: 'purple', icon: <BulbOutlined /> },
];

// 图表类型图标映射
const CHART_ICONS: Record<string, React.ReactNode> = {
  bar: <BarChartOutlined />,
  line: <LineChartOutlined />,
  pie: <PieChartOutlined />,
  scatter: <DotChartOutlined />,
  table: <UnorderedListOutlined />,
};

export const GuidedMiningWizard: React.FC<GuidedMiningWizardProps> = ({
  visible,
  dashboardId,
  connectionId: initialConnectionId,
  onClose,
  onSuccess,
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | undefined>(initialConnectionId);
  const [connections, setConnections] = useState<any[]>([]);
  const [intent, setIntent] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<MiningSuggestion[]>([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState<number[]>([]);
  const [expandedCards, setExpandedCards] = useState<number[]>([]);
  const [recommendCount, setRecommendCount] = useState(10);

  useEffect(() => {
    if (visible && currentStep === 0) {
      fetchConnections();
    }
  }, [visible, currentStep]);

  useEffect(() => {
    if (initialConnectionId) {
      setSelectedConnectionId(initialConnectionId);
    }
  }, [initialConnectionId]);

  const fetchConnections = async () => {
    try {
      const response = await getConnections();
      const data = response.data;
      if (Array.isArray(data)) {
        setConnections(data);
      } else if (data && Array.isArray(data.items)) {
        setConnections(data.items);
      } else {
        setConnections([]);
      }
    } catch (error) {
      message.error('获取数据库连接失败');
      setConnections([]);
    }
  };

  const handleGenerate = async () => {
    if (!selectedConnectionId) {
      message.error('请选择数据库连接');
      return;
    }

    setLoading(true);
    try {
      const res = await dashboardService.generateMiningSuggestions(
        dashboardId,
        selectedConnectionId,
        intent,
        recommendCount
      );
      setSuggestions(res.suggestions);
      setCurrentStep(2);
    } catch (error) {
      message.error('生成建议失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (selectedSuggestions.length === 0) {
      message.warning('请至少选择一个建议');
      return;
    }

    const selectedItems = suggestions.filter((_, index) => selectedSuggestions.includes(index));

    setLoading(true);
    try {
      await dashboardService.applyMiningSuggestions(dashboardId, selectedConnectionId!, selectedItems);
      message.success(`成功创建 ${selectedItems.length} 个组件`);
      onSuccess();
      handleReset();
    } catch (error) {
      message.error('创建组件失败');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setCurrentStep(0);
    setSuggestions([]);
    setSelectedSuggestions([]);
    setExpandedCards([]);
    setIntent('');
    onClose();
  };

  const toggleCardExpand = (index: number) => {
    setExpandedCards((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const getDimensionConfig = (dimension?: string) => {
    return MINING_DIMENSIONS.find((d) => d.value === dimension) || MINING_DIMENSIONS[0];
  };

  // 步骤1：选择数据源
  const renderStep1 = () => (
    <div style={{ padding: '20px 0' }}>
      <Title level={5}>选择数据源</Title>
      <Text type="secondary">请选择要分析的数据库连接</Text>
      <div style={{ marginTop: 20 }}>
        <Select
          style={{ width: '100%' }}
          placeholder="选择数据库连接"
          value={selectedConnectionId}
          onChange={setSelectedConnectionId}
          loading={connections.length === 0}
        >
          {connections.map((conn) => (
            <Select.Option key={conn.id} value={conn.id}>
              <DatabaseOutlined /> {conn.name} ({conn.db_type})
            </Select.Option>
          ))}
        </Select>
      </div>
    </div>
  );

  // 步骤2：分析目标
  const renderStep2 = () => (
    <div style={{ padding: '20px 0' }}>
      <Title level={5}>分析目标与配置</Title>
      <Text type="secondary">描述您的分析需求，或留空让 AI 自动发现</Text>

      <div style={{ marginTop: 20 }}>
        <TextArea
          rows={3}
          placeholder="例如：我想了解销售趋势、客户分布、库存周转率等..."
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
        />
      </div>

      <Divider />

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Text strong>推荐数量</Text>
          <Text type="secondary">{recommendCount} 个</Text>
        </div>
        <Slider
          min={3}
          max={20}
          value={recommendCount}
          onChange={setRecommendCount}
          marks={{ 3: '3', 10: '10', 20: '20' }}
        />
      </div>

      <div style={{ marginTop: 20 }}>
        <Text strong>挖掘维度</Text>
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {MINING_DIMENSIONS.map((dim) => (
            <Tag key={dim.value} color={dim.color} icon={dim.icon}>
              {dim.label}
            </Tag>
          ))}
        </div>
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          AI 将从以上维度综合分析，挖掘有价值的数据洞察
        </Text>
      </div>
    </div>
  );

  // 步骤3：推荐结果
  const renderStep3 = () => (
    <div style={{ padding: '20px 0' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={5} style={{ margin: 0 }}>
            为您推荐的分析图表
          </Title>
          <Text type="secondary">共 {suggestions.length} 个推荐，点击展开查看详情</Text>
        </div>
        <Checkbox
          checked={selectedSuggestions.length === suggestions.length && suggestions.length > 0}
          indeterminate={selectedSuggestions.length > 0 && selectedSuggestions.length < suggestions.length}
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedSuggestions(suggestions.map((_, i) => i));
            } else {
              setSelectedSuggestions([]);
            }
          }}
        >
          全选
        </Checkbox>
      </div>

      {suggestions.length === 0 ? (
        <Empty description="未生成任何建议，请重试" />
      ) : (
        <div style={{ maxHeight: '450px', overflowY: 'auto' }}>
          <Row gutter={[12, 12]}>
            {suggestions.map((item, index) => {
              const isSelected = selectedSuggestions.includes(index);
              const isExpanded = expandedCards.includes(index);
              const dimConfig = getDimensionConfig(item.mining_dimension);

              return (
                <Col span={12} key={index}>
                  <Card
                    hoverable
                    size="small"
                    style={{
                      border: isSelected ? '2px solid #1890ff' : '1px solid #e8e8e8',
                      backgroundColor: isSelected ? '#f0f7ff' : '#fff',
                      borderRadius: 10,
                      height: '100%',
                    }}
                    styles={{ body: { padding: '12px 16px', height: '100%', display: 'flex', flexDirection: 'column' } }}
                  >
                    {/* 卡片头部：基础信息 */}
                    <div
                      style={{ display: 'flex', alignItems: 'flex-start', cursor: 'pointer', flex: 1 }}
                      onClick={() => {
                        const newSelected = isSelected
                          ? selectedSuggestions.filter((i) => i !== index)
                          : [...selectedSuggestions, index];
                        setSelectedSuggestions(newSelected);
                      }}
                    >
                      <Checkbox checked={isSelected} style={{ marginTop: 4, marginRight: 12 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <Text strong style={{ fontSize: 14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }} title={item.title}>
                            {item.title}
                          </Text>
                          <Tag color={dimConfig.color} style={{ marginLeft: 'auto', marginRight: 0, fontSize: 10, transform: 'scale(0.9)' }}>
                            {dimConfig.label}
                          </Tag>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                           <Tag style={{ marginRight: 0, fontSize: 10, transform: 'scale(0.9)' }}>{CHART_ICONS[item.chart_type]} {item.chart_type}</Tag>
                        </div>

                        <Text type="secondary" style={{ fontSize: 12, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', minHeight: '36px' }} title={item.description}>
                          {item.description}
                        </Text>
                        
                        {/* 置信度和数据来源（直接显示） */}
                        {(item.confidence || item.source_tables?.length) && (
                          <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {item.confidence && (
                              <Tooltip title="AI 推荐置信度">
                                <span style={{ fontSize: 12, color: '#666' }}>
                                  <ThunderboltOutlined style={{ color: '#faad14', marginRight: 4 }} />
                                  {Math.round(item.confidence * 100)}%
                                </span>
                              </Tooltip>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 展开/收起按钮 */}
                    <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
                      <Button
                        type="link"
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleCardExpand(index);
                        }}
                        icon={isExpanded ? <DownOutlined /> : <RightOutlined />}
                        style={{ padding: 0 }}
                      >
                        {isExpanded ? '收起详情' : '查看详情'}
                      </Button>
                    </div>

                    {/* 展开的详细信息 */}
                    {isExpanded && (
                      <div
                        style={{
                          marginTop: 12,
                          padding: 12,
                          background: '#f9fafb',
                          borderRadius: 8,
                        }}
                      >
                        {/* 推荐理由 */}
                        {item.reasoning && (
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                              <BulbOutlined style={{ color: '#faad14' }} />
                              <Text strong style={{ fontSize: 13 }}>
                                推荐理由
                              </Text>
                            </div>
                            <Paragraph
                              style={{ margin: 0, fontSize: 12, color: '#555', paddingLeft: 20 }}
                            >
                              {item.reasoning}
                            </Paragraph>
                          </div>
                        )}

                        {/* 业务价值 */}
                        {item.business_value && (
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                              <InfoCircleOutlined style={{ color: '#1890ff' }} />
                              <Text strong style={{ fontSize: 13 }}>
                                业务价值
                              </Text>
                            </div>
                            <Paragraph
                              style={{ margin: 0, fontSize: 12, color: '#555', paddingLeft: 20 }}
                            >
                              {item.business_value}
                            </Paragraph>
                          </div>
                        )}

                        {/* 关键字段 */}
                        {item.key_fields && item.key_fields.length > 0 && (
                          <div style={{ marginBottom: 12 }}>
                            <Text strong style={{ fontSize: 13 }}>
                              关键字段：
                            </Text>
                            <span style={{ marginLeft: 8 }}>
                              {item.key_fields.map((field, i) => (
                                <Tag key={i} style={{ marginRight: 4 }}>
                                  {field}
                                </Tag>
                              ))}
                            </span>
                          </div>
                        )}

                        {/* 建议动作 */}
                        {item.suggested_actions && item.suggested_actions.length > 0 && (
                          <div style={{ marginBottom: 12 }}>
                            <Text strong style={{ fontSize: 13 }}>
                              建议动作：
                            </Text>
                            <ul style={{ margin: '4px 0 0 20px', paddingLeft: 0, fontSize: 12 }}>
                              {item.suggested_actions.map((action, i) => (
                                <li key={i} style={{ color: '#555' }}>
                                  {action}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* SQL 预览 */}
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <CodeOutlined style={{ color: '#52c41a' }} />
                            <Text strong style={{ fontSize: 13 }}>
                              SQL 查询
                            </Text>
                          </div>
                          <pre
                            style={{
                              background: '#1e293b',
                              color: '#e2e8f0',
                              padding: 10,
                              borderRadius: 6,
                              fontSize: 11,
                              overflow: 'auto',
                              maxHeight: 120,
                              margin: 0,
                            }}
                          >
                            {item.sql}
                          </pre>
                        </div>
                      </div>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        </div>
      )}
    </div>
  );

  return (
    <Modal
      title={
        <Space>
          <BulbOutlined style={{ color: '#faad14' }} />
          智能挖掘向导
        </Space>
      }
      open={visible}
      onCancel={handleReset}
      width={800}
      footer={[
        <Button
          key="back"
          onClick={() => currentStep > 0 && setCurrentStep(currentStep - 1)}
          disabled={currentStep === 0 || loading}
        >
          上一步
        </Button>,
        currentStep < 2 ? (
          <Button
            key="next"
            type="primary"
            onClick={() => {
              if (currentStep === 0 && !selectedConnectionId) {
                message.error('请选择连接');
                return;
              }
              if (currentStep === 1) {
                handleGenerate();
              } else {
                setCurrentStep(currentStep + 1);
              }
            }}
            loading={loading}
          >
            {currentStep === 1 ? '开始挖掘' : '下一步'}
          </Button>
        ) : (
          <Button key="submit" type="primary" onClick={handleApply} loading={loading}>
            应用所选 ({selectedSuggestions.length})
          </Button>
        ),
      ]}
    >
      <Steps current={currentStep} style={{ marginBottom: 8 }}>
        <Step title="选择数据源" icon={<DatabaseOutlined />} />
        <Step title="分析目标" icon={<SearchOutlined />} />
        <Step title="生成建议" icon={<CheckCircleOutlined />} />
      </Steps>

      <div style={{ minHeight: '300px' }}>
        {loading && currentStep === 1 ? (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 20, color: '#666' }}>
              AI 正在从多个维度分析数据库结构...
            </div>
            <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
              业务数据 · 指标分析 · 趋势分析 · 语义关联
            </div>
          </div>
        ) : (
          <>
            {currentStep === 0 && renderStep1()}
            {currentStep === 1 && renderStep2()}
            {currentStep === 2 && renderStep3()}
          </>
        )}
      </div>
    </Modal>
  );
};
