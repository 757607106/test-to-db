import React, { useState, useEffect } from 'react';
import { Modal, Steps, Button, Input, Select, Card, Checkbox, message, Spin, Row, Col, Typography, Empty, Space } from 'antd';
import { DatabaseOutlined, BulbOutlined, CheckCircleOutlined, SearchOutlined } from '@ant-design/icons';
import { dashboardService } from '../services/dashboardService';
import axios from 'axios';

const { Step } = Steps;
const { TextArea } = Input;
const { Title, Text } = Typography;

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

interface GuidedMiningWizardProps {
  visible: boolean;
  dashboardId: number;
  connectionId?: number;
  onClose: () => void;
  onSuccess: () => void;
}

export const GuidedMiningWizard: React.FC<GuidedMiningWizardProps> = ({
  visible,
  dashboardId,
  connectionId: initialConnectionId,
  onClose,
  onSuccess
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | undefined>(initialConnectionId);
  const [connections, setConnections] = useState<any[]>([]);
  const [intent, setIntent] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [selectedSuggestions, setSelectedSuggestions] = useState<number[]>([]);

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
      const response = await axios.get(`${API_URL}/connections/`);
      setConnections(response.data);
    } catch (error) {
      console.error('获取连接失败', error);
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
        intent
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
      await dashboardService.applyMiningSuggestions(
        dashboardId,
        selectedConnectionId!,
        selectedItems
      );
      message.success(`成功创建 ${selectedItems.length} 个组件`);
      onSuccess();
      onClose();
      // Reset state
      setCurrentStep(0);
      setSuggestions([]);
      setSelectedSuggestions([]);
      setIntent('');
    } catch (error) {
      message.error('创建组件失败');
    } finally {
      setLoading(false);
    }
  };

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
          {connections.map(conn => (
            <Select.Option key={conn.id} value={conn.id}>
              <DatabaseOutlined /> {conn.name} ({conn.db_type})
            </Select.Option>
          ))}
        </Select>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div style={{ padding: '20px 0' }}>
      <Title level={5}>您的分析目标是什么？</Title>
      <Text type="secondary">简单描述您想了解的业务问题，或者留空让 AI 自动发现</Text>
      <div style={{ marginTop: 20 }}>
        <TextArea
          rows={4}
          placeholder="例如：我想了解过去一年的销售趋势，以及哪些产品的利润率最高..."
          value={intent}
          onChange={e => setIntent(e.target.value)}
        />
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div style={{ padding: '20px 0' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Title level={5}>为您推荐的分析图表</Title>
        <Checkbox
          checked={selectedSuggestions.length === suggestions.length && suggestions.length > 0}
          indeterminate={selectedSuggestions.length > 0 && selectedSuggestions.length < suggestions.length}
          onChange={e => {
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
          <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
            <Row gutter={[16, 16]}>
              {suggestions.map((item, index) => (
                <Col span={24} key={index}>
                  <Card
                    hoverable
                    onClick={() => {
                      const newSelected = selectedSuggestions.includes(index)
                        ? selectedSuggestions.filter(i => i !== index)
                        : [...selectedSuggestions, index];
                      setSelectedSuggestions(newSelected);
                    }}
                    style={{ 
                        border: selectedSuggestions.includes(index) ? '1px solid #1890ff' : undefined,
                        backgroundColor: selectedSuggestions.includes(index) ? '#e6f7ff' : undefined
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                      <Checkbox checked={selectedSuggestions.includes(index)} style={{ marginTop: 4, marginRight: 12 }} />
                      <div style={{ flex: 1 }}>
                        <Text strong>{item.title}</Text>
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>{item.description}</Text>
                        </div>
                        <div style={{ marginTop: 8 }}>
                            <Text code>{item.chart_type}</Text>
                        </div>
                      </div>
                    </div>
                  </Card>
                </Col>
              ))}
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
      onCancel={onClose}
      width={700}
      footer={[
        <Button key="back" onClick={() => currentStep > 0 && setCurrentStep(currentStep - 1)} disabled={currentStep === 0 || loading}>
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
      <Steps current={currentStep}>
        <Step title="选择数据源" icon={<DatabaseOutlined />} />
        <Step title="分析目标" icon={<SearchOutlined />} />
        <Step title="生成建议" icon={<CheckCircleOutlined />} />
      </Steps>

      <div style={{ minHeight: '200px' }}>
        {loading && currentStep === 1 ? (
            <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <Spin size="large" tip="AI 正在分析数据库结构并生成建议..." />
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
