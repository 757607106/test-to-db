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
  Row,
  Col,
  Dropdown,
  Menu,
  Tooltip
} from 'antd';
import {
  ArrowLeftOutlined,
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
  BulbOutlined,
  MoreOutlined,
  CodeOutlined,
  SyncOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { dashboardService, widgetService } from '../services/dashboardService';
import type {
  DashboardDetail,
  Widget,
  WidgetUpdate,
  InsightConditions,
  InsightResult,
} from '../types/dashboard';
import { DashboardInsightWidget } from '../components/DashboardInsightWidget';
import { InsightConditionPanel } from '../components/InsightConditionPanel';
import { AddWidgetForm } from '../components/AddWidgetForm';
import { SmartChart } from '../components/SmartChart';
// import { ChartTypeSelector } from '../components/ChartTypeSelector';
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
  
  // 详情弹窗状态
  const [detailModalVisible, setDetailModalVisible] = useState<boolean>(false);
  const [detailWidget, setDetailWidget] = useState<Widget | null>(null);

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
  
  const showDetailModal = (widget: Widget) => {
      setDetailWidget(widget);
      setDetailModalVisible(true);
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
      await dashboardService.generateDashboardInsights(dashboardId, {
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
        <Col span={24} key={widget.id}>
            <DashboardInsightWidget
            widgetId={widget.id}
            insights={widget.data_cache as InsightResult}
            loading={isRefreshing}
            onRefresh={() => handleRefreshInsights(widget.id)}
            onOpenConditionPanel={() => handleOpenConditionPanel(widget)}
            />
        </Col>
      );
    }
    
    const menu = (
        <Menu>
            <Menu.Item key="refresh" icon={<ReloadOutlined />} onClick={() => handleRefreshWidget(widget.id)}>
                刷新数据
            </Menu.Item>
            <Menu.Item key="detail" icon={<CodeOutlined />} onClick={() => showDetailModal(widget)}>
                查看详情
            </Menu.Item>
            <Menu.Item key="edit" icon={<EditOutlined />} onClick={() => showEditWidgetModal(widget)}>
                编辑配置
            </Menu.Item>
            <Menu.Item key="delete" icon={<DeleteOutlined />} danger>
                <Popconfirm
                    title="确定要删除这个组件吗？"
                    onConfirm={() => handleDeleteWidget(widget.id)}
                    okText="是"
                    cancelText="否"
                    placement="left"
                >
                    删除组件
                </Popconfirm>
            </Menu.Item>
        </Menu>
    );

    return (
      <Col xs={24} sm={24} md={12} lg={12} xl={8} key={widget.id}>
        <Card
            title={widget.title}
            extra={
                <Space>
                    {widget.last_refresh_at && (
                        <Tooltip title={`最后刷新: ${new Date(widget.last_refresh_at).toLocaleString()}`}>
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                                <SyncOutlined spin={isRefreshing} />
                            </Text>
                        </Tooltip>
                    )}
                    <Dropdown overlay={menu} trigger={['click']}>
                        <Button type="text" icon={<MoreOutlined />} />
                    </Dropdown>
                </Space>
            }
            bodyStyle={{ padding: '12px', height: '350px', overflow: 'hidden' }}
            hoverable
        >
            {widget.data_cache ? (
                <SmartChart 
                    data={widget.data_cache} 
                    height={326}
                    chartType={widget.chart_config?.chart_type}
                    debug={true} // 开启调试模式以便排查问题
                />
            ) : (
                <Empty description="暂无数据" style={{ marginTop: 80 }} />
            )}
        </Card>
      </Col>
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

        {/* 使用 Grid 布局展示组件 */}
        {dashboard.widgets.filter(w => w.widget_type !== 'insight_analysis').length === 0 ? (
          <Card>
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
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {/* 先渲染洞察组件（通常占满一行） */}
            {dashboard.widgets
                .filter(w => w.widget_type === 'insight_analysis')
                .map(renderWidgetCard)}
            
            {/* 再渲染普通组件 */}
            {dashboard.widgets
                .filter(w => w.widget_type !== 'insight_analysis')
                .map(renderWidgetCard)}
          </Row>
        )}

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
      
      {/* 详情查看 Modal */}
      <Modal
        title="组件详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
            <Button key="close" onClick={() => setDetailModalVisible(false)}>关闭</Button>
        ]}
        width={800}
      >
          {detailWidget && (
              <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                      <Text strong>SQL查询：</Text>
                      <pre style={{ background: '#f5f5f5', padding: '10px', maxHeight: '200px', overflow: 'auto' }}>
                          {detailWidget.query_config?.generated_sql}
                      </pre>
                  </div>
                  <div>
                      <Text strong>数据预览：</Text>
                      <pre style={{ background: '#f5f5f5', padding: '10px', maxHeight: '300px', overflow: 'auto' }}>
                          {JSON.stringify(detailWidget.data_cache, null, 2)}
                      </pre>
                  </div>
              </Space>
          )}
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
        connectionId={dashboard?.widgets.find(w => w.connection_id)?.connection_id}
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