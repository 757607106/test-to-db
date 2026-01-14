import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Space,
  message,
  Typography,
  Spin,
  Empty,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
} from 'antd';
import {
  ArrowLeftOutlined,
  PlusOutlined,
  SaveOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
  BulbOutlined,
  DownOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { dashboardService, widgetService } from '../services/dashboardService';
import type {
  DashboardDetail,
  Widget,
  WidgetCreate,
  WidgetUpdate,
  InsightConditions,
  InsightResult,
} from '../types/dashboard';
import { DashboardInsightWidget } from '../components/DashboardInsightWidget';
import { InsightConditionPanel } from '../components/InsightConditionPanel';
import { AddWidgetForm } from '../components/AddWidgetForm';
import { SmartChart } from '../components/SmartChart';
import { ChartTypeSelector } from '../components/ChartTypeSelector';
import { GuidedMiningWizard } from '../components/GuidedMiningWizard';

const { Title, Text } = Typography;
const { Option } = Select;

const DashboardEditorPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const dashboardId = Number(id);

  const [dashboard, setDashboard] = useState<DashboardDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<Record<number, boolean>>({});
  const [addWidgetModalVisible, setAddWidgetModalVisible] = useState<boolean>(false);
  const [editWidgetModalVisible, setEditWidgetModalVisible] = useState<boolean>(false);
  const [editingWidget, setEditingWidget] = useState<Widget | null>(null);
  const [form] = Form.useForm();
  const [generatingInsights, setGeneratingInsights] = useState<boolean>(false);
  const [conditionPanelVisible, setConditionPanelVisible] = useState<boolean>(false);
  const [currentInsightWidget, setCurrentInsightWidget] = useState<Widget | null>(null);
  const [miningWizardVisible, setMiningWizardVisible] = useState<boolean>(false);
  const [sqlCollapsed, setSqlCollapsed] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (dashboardId) {
      fetchDashboard();
    }
  }, [dashboardId]);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const data = await dashboardService.getDashboardDetail(dashboardId);
      setDashboard(data);
    } catch (error) {
      message.error('获取Dashboard详情失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/dashboards');
  };

  const handleRefreshWidget = async (widgetId: number) => {
    setRefreshing((prev) => ({ ...prev, [widgetId]: true }));
    try {
      const response = await widgetService.refreshWidget(widgetId);
      message.success(`数据刷新成功，耗时 ${response.refresh_duration_ms}ms`);
      
      // 更新widget的data_cache
      if (dashboard) {
        const updatedWidgets = dashboard.widgets.map((w) =>
          w.id === widgetId ? { ...w, data_cache: response.data_cache, last_refresh_at: response.last_refresh_at } : w
        );
        setDashboard({ ...dashboard, widgets: updatedWidgets });
      }
    } catch (error) {
      message.error('刷新数据失败');
      console.error(error);
    } finally {
      setRefreshing((prev) => ({ ...prev, [widgetId]: false }));
    }
  };

  const handleDeleteWidget = async (widgetId: number) => {
    try {
      await widgetService.deleteWidget(widgetId);
      message.success('组件删除成功');
      fetchDashboard();
    } catch (error) {
      message.error('删除组件失败');
      console.error(error);
    }
  };

  const showAddWidgetModal = () => {
    form.resetFields();
    setAddWidgetModalVisible(true);
  };

  const showEditWidgetModal = (widget: Widget) => {
    setEditingWidget(widget);
    form.resetFields();
    form.setFieldsValue({
      title: widget.title,
      refresh_interval: widget.refresh_interval,
    });
    setEditWidgetModalVisible(true);
  };

  const handleAddWidgetCancel = () => {
    setAddWidgetModalVisible(false);
  };

  const handleEditWidgetCancel = () => {
    setEditWidgetModalVisible(false);
    setEditingWidget(null);
  };

  const handleEditWidgetSubmit = async () => {
    if (!editingWidget) return;

    try {
      const values = await form.validateFields();
      const updateData: WidgetUpdate = {
        title: values.title,
        refresh_interval: values.refresh_interval,
      };

      await widgetService.updateWidget(editingWidget.id, updateData);
      message.success('组件更新成功');
      setEditWidgetModalVisible(false);
      setEditingWidget(null);
      fetchDashboard();
    } catch (error) {
      message.error('更新组件失败');
      console.error(error);
    }
  };

  // 生成洞察分析
  const handleGenerateInsights = async (conditions?: InsightConditions) => {
    // 检查是否有数据Widget（排除insight_analysis类型）
    const dataWidgets = dashboard?.widgets.filter(w => w.widget_type !== 'insight_analysis') || [];
    if (dataWidgets.length === 0) {
      message.warning('请先添加数据组件后再生成洞察分析');
      return;
    }
    
    setGeneratingInsights(true);
    try {
      const response = await dashboardService.generateDashboardInsights(dashboardId, {
        conditions,
        use_graph_relationships: true,
      });
      message.success('洞察分析生成成功');
      // 刷新Dashboard获取最新数据
      await fetchDashboard();
    } catch (error: any) {
      message.error(
        error?.response?.data?.detail || '生成洞察分析失败'
      );
      console.error(error);
    } finally {
      setGeneratingInsights(false);
    }
  };

  // 刷新洞察Widget
  const handleRefreshInsights = async (widgetId: number, conditions?: InsightConditions) => {
    setRefreshing((prev) => ({ ...prev, [widgetId]: true }));
    try {
      const response = await widgetService.refreshInsightWidget(widgetId, conditions);
      message.success('洞察分析刷新成功');
      // 更新dashboard中的widget
      if (dashboard) {
        const updatedWidgets = dashboard.widgets.map((w) =>
          w.id === widgetId
            ? { ...w, data_cache: response.insights, last_refresh_at: response.generated_at }
            : w
        );
        setDashboard({ ...dashboard, widgets: updatedWidgets });
      }
    } catch (error: any) {
      message.error(
        error?.response?.data?.detail || '刷新洞察失败'
      );
      console.error(error);
    } finally {
      setRefreshing((prev) => ({ ...prev, [widgetId]: false }));
    }
  };

  // 打开条件面板
  const handleOpenConditionPanel = (widget?: Widget) => {
    setCurrentInsightWidget(widget || null);
    setConditionPanelVisible(true);
  };

  // 关闭条件面板
  const handleCloseConditionPanel = () => {
    setConditionPanelVisible(false);
    setCurrentInsightWidget(null);
  };

  // 提交条件
  const handleConditionSubmit = async (conditions: InsightConditions) => {
    if (currentInsightWidget) {
      // 刷新现有洞察Widget
      await handleRefreshInsights(currentInsightWidget.id, conditions);
    } else {
      // 生成新的洞察
      await handleGenerateInsights(conditions);
    }
    handleCloseConditionPanel();
  };

  const renderWidgetCard = (widget: Widget) => {
    const isRefreshing = refreshing[widget.id] || false;

    // 如果是洞察类型Widget，使用特殊组件渲染
    if (widget.widget_type === 'insight_analysis') {
      return (
        <DashboardInsightWidget
          key={widget.id}
          widgetId={widget.id}
          insights={widget.data_cache as InsightResult}
          loading={isRefreshing}
          onRefresh={() => handleRefreshInsights(widget.id)}
          onOpenConditionPanel={() => handleOpenConditionPanel(widget)}
        />
      );
    }

    return (
      <Card
        key={widget.id}
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text strong>{widget.title}</Text>
            <Space>
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                loading={isRefreshing}
                onClick={() => handleRefreshWidget(widget.id)}
              >
                刷新
              </Button>
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={() => showEditWidgetModal(widget)}
              >
                编辑
              </Button>
              <Popconfirm
                title="确定要删除这个组件吗？"
                onConfirm={() => handleDeleteWidget(widget.id)}
                okText="是"
                cancelText="否"
              >
                <Button type="text" size="small" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            </Space>
          </div>
        }
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text type="secondary">类型：</Text>
            <Text>{widget.widget_type}</Text>
          </div>
          <div>
            <Text type="secondary">数据库连接：</Text>
            <Text>{widget.connection_name || `Connection #${widget.connection_id}`}</Text>
          </div>
          <div>
            <Text type="secondary">刷新间隔：</Text>
            <Text>{widget.refresh_interval > 0 ? `${widget.refresh_interval}秒` : '手动刷新'}</Text>
          </div>
          {widget.last_refresh_at && (
            <div>
              <Text type="secondary">最后刷新：</Text>
              <Text>{new Date(widget.last_refresh_at).toLocaleString()}</Text>
            </div>
          )}
          <div>
            <div 
              style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                cursor: 'pointer',
                marginBottom: '8px'
              }}
              onClick={() => {
                const newState = {...sqlCollapsed};
                newState[widget.id] = !newState[widget.id];
                setSqlCollapsed(newState);
              }}
            >
              <Text type="secondary">查询SQL：</Text>
              <Button 
                type="link" 
                size="small"
                icon={sqlCollapsed[widget.id] ? <DownOutlined /> : <UpOutlined />}
              >
                {sqlCollapsed[widget.id] ? '展开' : '收起'}
              </Button>
            </div>
            {!sqlCollapsed[widget.id] && (
              <pre
                style={{
                  background: '#f5f5f5',
                  padding: '8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                  overflow: 'auto',
                  maxHeight: '200px',
                }}
              >
                {widget.query_config.generated_sql}
              </pre>
            )}
          </div>
          {widget.data_cache && (
            <div>
              {widget.widget_type === 'chart' ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <Text type="secondary">图表展示：</Text>
                    <ChartTypeSelector
                      widgetId={widget.id}
                      currentChartType={widget.chart_config?.chart_type}
                      onChartTypeChange={() => fetchDashboard()}
                    />
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <SmartChart 
                      data={widget.data_cache} 
                      height={300}
                      chartType={widget.chart_config?.chart_type}
                    />
                  </div>
                </>
              ) : (
                <>
                  <Text type="secondary">数据预览：</Text>
                  <pre
                    style={{
                      background: '#f5f5f5',
                      padding: '8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      overflow: 'auto',
                      maxHeight: '300px',
                    }}
                  >
                    {JSON.stringify(widget.data_cache, null, 2)}
                  </pre>
                </>
              )}
            </div>
          )}
        </Space>
      </Card>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div style={{ padding: '24px' }}>
        <Empty description="Dashboard不存在" />
      </div>
    );
  }

  const canEdit = dashboard.permission_level === 'owner' || dashboard.permission_level === 'editor';

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: 24 }}>
          <Space style={{ marginBottom: 16 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
              返回列表
            </Button>
          </Space>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Title level={3} style={{ margin: 0 }}>
                {dashboard.name}
              </Title>
              {dashboard.description && (
                <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  {dashboard.description}
                </Text>
              )}
            </div>

            {canEdit && (
              <Space>
                <Button
                  type="primary"
                  icon={<BulbOutlined />}
                  onClick={() => setMiningWizardVisible(true)}
                >
                  智能挖掘
                </Button>
                <Button
                  icon={<BulbOutlined />}
                  onClick={() => handleOpenConditionPanel()}
                  loading={generatingInsights}
                >
                  生成洞察
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={showAddWidgetModal}>
                  添加组件
                </Button>
                <Button icon={<SettingOutlined />} onClick={() => navigate(`/dashboards/${dashboardId}/settings`)}>
                  设置
                </Button>
              </Space>
            )}
          </div>
        </div>

        {/* 只展示非洞察类型Widget，如果没有则显示空状态 */}
        {dashboard.widgets.filter(w => w.widget_type !== 'insight_analysis').length === 0 ? (
          <Empty
            description="暂无组件"
            style={{ margin: '60px 0' }}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            {canEdit && (
              <Button type="primary" icon={<PlusOutlined />} onClick={showAddWidgetModal}>
                添加第一个组件
              </Button>
            )}
          </Empty>
        ) : (
          <div>
            {dashboard.widgets.map((widget) => renderWidgetCard(widget))}
          </div>
        )}
      </Card>

      {/* 编辑Widget Modal */}
      <Modal
        title="编辑组件"
        open={editWidgetModalVisible}
        onOk={handleEditWidgetSubmit}
        onCancel={handleEditWidgetCancel}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入组件标题' }]}
          >
            <Input placeholder="例如：销售趋势图" />
          </Form.Item>

          <Form.Item
            name="refresh_interval"
            label="刷新间隔（秒）"
            rules={[{ required: true, message: '请输入刷新间隔' }]}
          >
            <Select>
              <Option value={0}>手动刷新</Option>
              <Option value={30}>30秒</Option>
              <Option value={60}>1分钟</Option>
              <Option value={300}>5分钟</Option>
              <Option value={600}>10分钟</Option>
              <Option value={1800}>30分钟</Option>
              <Option value={3600}>1小时</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加Widget Modal - 完整功能 */}
      <Modal
        title="添加组件"
        open={addWidgetModalVisible}
        onCancel={handleAddWidgetCancel}
        footer={null}
        width={700}
      >
        <AddWidgetForm
          dashboardId={dashboardId}
          onSuccess={() => {
            setAddWidgetModalVisible(false);
            fetchDashboard();
          }}
          onCancel={handleAddWidgetCancel}
        />
      </Modal>

      {/* 洞察条件面板 */}
      <InsightConditionPanel
        visible={conditionPanelVisible}
        currentConditions={
          currentInsightWidget?.query_config?.parameters as InsightConditions
        }
        onSubmit={handleConditionSubmit}
        onCancel={handleCloseConditionPanel}
      />

      {/* 智能挖掘向导 */}
      <GuidedMiningWizard
        visible={miningWizardVisible}
        dashboardId={dashboardId}
        connectionId={dashboard?.widgets[0]?.connection_id}  // 从第一个widget获取，如果没有则让用户选择
        onClose={() => setMiningWizardVisible(false)}
        onSuccess={() => {
          setMiningWizardVisible(false);
          fetchDashboard();
        }}
      />
    </div>
  );
};

export default DashboardEditorPage;
