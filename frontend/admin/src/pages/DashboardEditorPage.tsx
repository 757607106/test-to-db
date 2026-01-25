/**
 * DashboardEditorPage - 全新的仪表盘编辑器
 * 支持 react-grid-layout 拖拽布局、图表配置面板、AI 智能推荐
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Dropdown,
  Tooltip,
  Badge,
  Segmented,
  FloatButton,
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
  SyncOutlined,
  SaveOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  DragOutlined,
  EyeOutlined,
  RobotOutlined,
  LockOutlined,
  UnlockOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
// @ts-ignore - WidthProvider 类型定义问题
import GridLayout, { WidthProvider } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { dashboardService, widgetService } from '../services/dashboardService';
import type {
  DashboardDetail,
  Widget,
  WidgetUpdate,
  InsightConditions,
  InsightResult,
  LayoutUpdateRequest,
} from '../types/dashboard';
import { DashboardInsightWidget } from '../components/DashboardInsightWidget';
import { InsightConditionPanel } from '../components/InsightConditionPanel';
import { AddWidgetForm } from '../components/AddWidgetForm';
import { SmartChart } from '../components/SmartChart';
import { ChartConfigPanel, ChartConfig } from '../components/ChartConfigPanel';
import { GuidedMiningWizard } from '../components/GuidedMiningWizard';

const ReactGridLayout = WidthProvider(GridLayout);

// Layout 类型定义
interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
  static?: boolean;
}

const { Title, Text } = Typography;
const { Option } = Select;

// 编辑模式类型
type EditorMode = 'edit' | 'preview';

// 样式定义
const styles = {
  container: {
    padding: '16px 24px',
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%)',
  },
  header: {
    marginBottom: 16,
    background: '#fff',
    padding: '16px 20px',
    borderRadius: 12,
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
  },
  gridContainer: {
    background: '#fff',
    borderRadius: 12,
    padding: 16,
    minHeight: 'calc(100vh - 200px)',
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
  },
  widgetCard: {
    height: '100%',
    borderRadius: 8,
    overflow: 'hidden',
    transition: 'all 0.3s ease',
  },
  widgetCardHover: {
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
  },
  dragHandle: {
    cursor: 'move',
    padding: '4px 8px',
    marginRight: 8,
    borderRadius: 4,
    background: '#f0f0f0',
    display: 'inline-flex',
    alignItems: 'center',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 400,
    background: 'repeating-linear-gradient(45deg, #fafafa, #fafafa 10px, #fff 10px, #fff 20px)',
    borderRadius: 8,
    border: '2px dashed #d9d9d9',
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap' as const,
    gap: 12,
  },
  statusBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    fontSize: 12,
    color: '#8c8c8c',
  },
};

// 默认网格配置
const GRID_CONFIG = {
  cols: 12,
  rowHeight: 80,
  margin: [12, 12] as [number, number],
  containerPadding: [0, 0] as [number, number],
  compactType: 'vertical' as const,
  preventCollision: false,
};

// 默认Widget尺寸
const DEFAULT_WIDGET_SIZE = {
  w: 4,
  h: 4,
  minW: 2,
  minH: 2,
  maxW: 12,
  maxH: 10,
};

const DashboardEditorPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const dashboardId = Number(id);

  // 核心状态
  const [dashboard, setDashboard] = useState<DashboardDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<Record<number, boolean>>({});
  
  // 编辑器状态
  const [editorMode, setEditorMode] = useState<EditorMode>('edit');
  const [isLayoutDirty, setIsLayoutDirty] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [gridLocked, setGridLocked] = useState<boolean>(false);
  
  // 布局状态
  const [layouts, setLayouts] = useState<LayoutItem[]>([]);
  
  // Modal状态
  const [addWidgetModalVisible, setAddWidgetModalVisible] = useState<boolean>(false);
  const [editWidgetModalVisible, setEditWidgetModalVisible] = useState<boolean>(false);
  const [editingWidget, setEditingWidget] = useState<Widget | null>(null);
  const [chartConfigVisible, setChartConfigVisible] = useState<boolean>(false);
  const [configWidget, setConfigWidget] = useState<Widget | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState<boolean>(false);
  const [detailWidget, setDetailWidget] = useState<Widget | null>(null);
  const [conditionPanelVisible, setConditionPanelVisible] = useState<boolean>(false);
  const [currentInsightWidget, setCurrentInsightWidget] = useState<Widget | null>(null);
  const [miningWizardVisible, setMiningWizardVisible] = useState<boolean>(false);
  const [generatingInsights, setGeneratingInsights] = useState<boolean>(false);
  
  const [form] = Form.useForm();

  // 加载Dashboard数据
  useEffect(() => {
    if (dashboardId) {
      fetchDashboard();
    }
  }, [dashboardId]);

  // 同步Widgets到Layout
  useEffect(() => {
    if (dashboard?.widgets) {
      const newLayouts = dashboard.widgets.map((widget) => ({
        i: String(widget.id),
        x: widget.position_config?.x ?? 0,
        y: widget.position_config?.y ?? 0,
        w: widget.position_config?.w ?? DEFAULT_WIDGET_SIZE.w,
        h: widget.position_config?.h ?? DEFAULT_WIDGET_SIZE.h,
        minW: widget.position_config?.minW ?? DEFAULT_WIDGET_SIZE.minW,
        minH: widget.position_config?.minH ?? DEFAULT_WIDGET_SIZE.minH,
        maxW: widget.position_config?.maxW ?? DEFAULT_WIDGET_SIZE.maxW,
        maxH: widget.position_config?.maxH ?? DEFAULT_WIDGET_SIZE.maxH,
        static: widget.widget_type === 'insight_analysis', // 洞察组件固定
      }));
      setLayouts(newLayouts);
    }
  }, [dashboard?.widgets]);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const data = await dashboardService.getDashboardDetail(dashboardId);
      setDashboard(data);
      setIsLayoutDirty(false);
    } catch (error) {
      message.error('获取Dashboard详情失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // 布局变更处理
  const handleLayoutChange = useCallback((newLayout: LayoutItem[]) => {
    setLayouts(newLayout);
    setIsLayoutDirty(true);
  }, []);

  // 保存布局
  const handleSaveLayout = async () => {
    if (!dashboard || !isLayoutDirty) return;
    
    setSaving(true);
    try {
      const layoutData: LayoutUpdateRequest = {
        layout: layouts.map((item) => ({
          widget_id: Number(item.i),
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h,
        })),
      };
      
      await dashboardService.updateDashboardLayout(dashboardId, layoutData);
      message.success('布局保存成功');
      setIsLayoutDirty(false);
    } catch (error) {
      message.error('保存布局失败');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  // Widget操作
  const handleRefreshWidget = async (widgetId: number) => {
    setRefreshing((prev) => ({ ...prev, [widgetId]: true }));
    try {
      const response = await widgetService.refreshWidget(widgetId);
      message.success(`数据刷新成功，耗时 ${response.refresh_duration_ms}ms`);
      
      if (dashboard) {
        const updatedWidgets = dashboard.widgets.map((w) =>
          w.id === widgetId
            ? { ...w, data_cache: response.data_cache, last_refresh_at: response.last_refresh_at }
            : w
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

  // 图表配置
  const handleOpenChartConfig = (widget: Widget) => {
    setConfigWidget(widget);
    setChartConfigVisible(true);
  };

  const handleApplyChartConfig = async (config: ChartConfig) => {
    if (!configWidget) return;
    
    try {
      await widgetService.updateWidget(configWidget.id, {
        chart_config: config,
      });
      message.success('图表配置已更新');
      fetchDashboard();
    } catch (error) {
      message.error('更新图表配置失败');
      console.error(error);
    }
  };

  // AI智能推荐
  const handleAIRecommend = async (): Promise<ChartConfig | null> => {
    if (!configWidget?.data_cache) return null;
    
    try {
      // 调用后端 AI 推荐 API
      const response = await widgetService.getAIChartRecommendation(
        configWidget.id,
        configWidget.data_cache,
        configWidget.title
      );
      
      if (response?.chart_config) {
        message.success(`AI 推荐: ${response.reasoning || '已分析数据特征'}`);
        return response.chart_config;
      }
      return null;
    } catch (error: any) {
      // 如果后端 API 不可用，使用前端智能推荐
      console.warn('AI API unavailable, using frontend recommendation');
      const columns = getWidgetColumns(configWidget);
      
      // 前端简单推荐逻辑
      const data = configWidget.data_cache;
      let recommendedType = 'bar';
      
      if (columns.length >= 2) {
        const hasDateCol = columns.some(c => /date|time|日期|时间/i.test(c));
        const numericCols = columns.filter(c => {
          if (!data?.rows?.[0]) return false;
          const val = data.rows[0][columns.indexOf(c)];
          return typeof val === 'number' || !isNaN(Number(val));
        });
        
        if (hasDateCol && numericCols.length > 0) {
          recommendedType = 'line';
        } else if (numericCols.length === 1 && columns.length === 2) {
          recommendedType = 'pie';
        }
      }
      
      return {
        chart_type: recommendedType,
        title: configWidget.title,
        color_scheme: '默认',
        legend: { show: true, position: 'bottom' },
        series_config: { smooth: true, label: false },
      };
    }
  };

  // 编辑Widget
  const showEditWidgetModal = (widget: Widget) => {
    setEditingWidget(widget);
    form.resetFields();
    form.setFieldsValue({
      title: widget.title,
      refresh_interval: widget.refresh_interval,
    });
    setEditWidgetModalVisible(true);
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

  // 洞察相关
  const handleGenerateInsights = async (conditions?: InsightConditions) => {
    const dataWidgets = dashboard?.widgets.filter((w) => w.widget_type !== 'insight_analysis') || [];
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
      await fetchDashboard();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '生成洞察分析失败');
      console.error(error);
    } finally {
      setGeneratingInsights(false);
    }
  };

  const handleRefreshInsights = async (widgetId: number, conditions?: InsightConditions) => {
    setRefreshing((prev) => ({ ...prev, [widgetId]: true }));
    try {
      const response = await widgetService.refreshInsightWidget(widgetId, conditions);
      message.success('洞察分析刷新成功');
      if (dashboard) {
        const updatedWidgets = dashboard.widgets.map((w) =>
          w.id === widgetId
            ? { ...w, data_cache: response.insights, last_refresh_at: response.generated_at }
            : w
        );
        setDashboard({ ...dashboard, widgets: updatedWidgets });
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '刷新洞察失败');
      console.error(error);
    } finally {
      setRefreshing((prev) => ({ ...prev, [widgetId]: false }));
    }
  };

  // 获取Widget的数据列
  const getWidgetColumns = (widget: Widget): string[] => {
    if (!widget.data_cache) return [];
    
    const data = widget.data_cache;
    if (data.columns) return data.columns;
    if (data.data && data.data[0]) return Object.keys(data.data[0]);
    if (Array.isArray(data) && data[0]) return Object.keys(data[0]);
    return [];
  };

  // 渲染Widget
  const renderWidget = (widget: Widget) => {
    const isRefreshing = refreshing[widget.id] || false;

    // 洞察组件单独渲染
    if (widget.widget_type === 'insight_analysis') {
      return (
        <DashboardInsightWidget
          widgetId={widget.id}
          insights={widget.data_cache as InsightResult}
          loading={isRefreshing}
          onRefresh={() => handleRefreshInsights(widget.id)}
          onOpenConditionPanel={() => {
            setCurrentInsightWidget(widget);
            setConditionPanelVisible(true);
          }}
        />
      );
    }

    const menuItems = [
      {
        key: 'refresh',
        icon: <ReloadOutlined />,
        label: '刷新数据',
        onClick: () => handleRefreshWidget(widget.id),
      },
      {
        key: 'config',
        icon: <SettingOutlined />,
        label: '图表配置',
        onClick: () => handleOpenChartConfig(widget),
      },
      {
        key: 'detail',
        icon: <CodeOutlined />,
        label: '查看详情',
        onClick: () => {
          setDetailWidget(widget);
          setDetailModalVisible(true);
        },
      },
      {
        key: 'edit',
        icon: <EditOutlined />,
        label: '编辑配置',
        onClick: () => showEditWidgetModal(widget),
      },
      { type: 'divider' as const },
      {
        key: 'delete',
        icon: <DeleteOutlined />,
        label: '删除组件',
        danger: true,
        onClick: () => {
          Modal.confirm({
            title: '确定要删除这个组件吗？',
            content: '删除后无法恢复',
            okText: '删除',
            okType: 'danger',
            cancelText: '取消',
            onOk: () => handleDeleteWidget(widget.id),
          });
        },
      },
    ];

    return (
      <Card
        title={
          <Space>
            {editorMode === 'edit' && !gridLocked && (
              <span style={styles.dragHandle} className="drag-handle">
                <DragOutlined />
              </span>
            )}
            <Text strong ellipsis style={{ maxWidth: 150 }}>
              {widget.title}
            </Text>
          </Space>
        }
        extra={
          <Space size="small">
            {widget.last_refresh_at && (
              <Tooltip title={`最后刷新: ${new Date(widget.last_refresh_at).toLocaleString()}`}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  <SyncOutlined spin={isRefreshing} />
                </Text>
              </Tooltip>
            )}
            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
              <Button type="text" size="small" icon={<MoreOutlined />} />
            </Dropdown>
          </Space>
        }
        style={styles.widgetCard}
        bodyStyle={{ padding: 8, height: 'calc(100% - 57px)', overflow: 'hidden' }}
        size="small"
      >
        {widget.data_cache ? (
          <SmartChart
            data={widget.data_cache}
            height={280}
            chartType={widget.chart_config?.chart_type}
          />
        ) : (
          <Empty description="暂无数据" style={{ marginTop: 60 }} />
        )}
      </Card>
    );
  };

  // 权限检查
  const canEdit = dashboard?.permission_level === 'owner' || dashboard?.permission_level === 'editor';

  // 分离洞察组件和普通组件
  const insightWidgets = dashboard?.widgets.filter((w) => w.widget_type === 'insight_analysis') || [];
  const normalWidgets = dashboard?.widgets.filter((w) => w.widget_type !== 'insight_analysis') || [];

  if (loading) {
    return (
      <div style={{ ...styles.container, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div style={styles.container}>
        <Empty description="Dashboard不存在" />
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* 头部 */}
      <div style={styles.header}>
        <div style={styles.toolbar}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/dashboards')}>
              返回
            </Button>
            <div>
              <Title level={4} style={{ margin: 0, display: 'inline' }}>
                {dashboard.name}
              </Title>
              {dashboard.description && (
                <Text type="secondary" style={{ marginLeft: 12 }}>
                  {dashboard.description}
                </Text>
              )}
            </div>
          </Space>

          {canEdit && (
            <Space wrap>
              <Segmented
                value={editorMode}
                onChange={(v) => setEditorMode(v as EditorMode)}
                options={[
                  { value: 'edit', icon: <EditOutlined />, label: '编辑' },
                  { value: 'preview', icon: <EyeOutlined />, label: '预览' },
                ]}
              />
              
              <Tooltip title={gridLocked ? '解锁布局' : '锁定布局'}>
                <Button
                  icon={gridLocked ? <LockOutlined /> : <UnlockOutlined />}
                  onClick={() => setGridLocked(!gridLocked)}
                />
              </Tooltip>

              <Tooltip title={isFullscreen ? '退出全屏' : '全屏'}>
                <Button
                  icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                  onClick={() => setIsFullscreen(!isFullscreen)}
                />
              </Tooltip>

              <Button
                type="primary"
                icon={<BulbOutlined />}
                onClick={() => setMiningWizardVisible(true)}
              >
                智能挖掘
              </Button>

              <Button
                icon={<BulbOutlined />}
                onClick={() => {
                  setCurrentInsightWidget(null);
                  setConditionPanelVisible(true);
                }}
                loading={generatingInsights}
              >
                生成洞察
              </Button>

              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setAddWidgetModalVisible(true)}
              >
                添加组件
              </Button>

              {isLayoutDirty && (
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSaveLayout}
                  loading={saving}
                  danger
                >
                  保存布局
                </Button>
              )}

              <Button
                icon={<SettingOutlined />}
                onClick={() => navigate(`/dashboards/${dashboardId}/settings`)}
              >
                设置
              </Button>
            </Space>
          )}
        </div>

        {/* 状态栏 */}
        <div style={{ ...styles.statusBar, marginTop: 12 }}>
          <span>组件数: {dashboard.widgets.length}</span>
          <span>更新时间: {new Date(dashboard.updated_at).toLocaleString()}</span>
          {isLayoutDirty && <Badge status="warning" text="布局未保存" />}
        </div>
      </div>

      {/* 洞察组件区域 */}
      {insightWidgets.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {insightWidgets.map((widget) => (
            <div key={widget.id} style={{ marginBottom: 12 }}>
              {renderWidget(widget)}
            </div>
          ))}
        </div>
      )}

      {/* Grid布局区域 */}
      <div style={styles.gridContainer}>
        {normalWidgets.length === 0 ? (
          <div style={styles.emptyState}>
            <Empty
              description="暂无组件，点击下方按钮添加"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              {canEdit && (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setAddWidgetModalVisible(true)}
                >
                  添加第一个组件
                </Button>
              )}
            </Empty>
          </div>
        ) : (
          <ReactGridLayout
            className="layout"
            layout={layouts.filter((l) => !insightWidgets.find((w) => String(w.id) === l.i))}
            cols={GRID_CONFIG.cols}
            rowHeight={GRID_CONFIG.rowHeight}
            margin={GRID_CONFIG.margin}
            containerPadding={GRID_CONFIG.containerPadding}
            compactType={GRID_CONFIG.compactType}
            preventCollision={GRID_CONFIG.preventCollision}
            isDraggable={editorMode === 'edit' && canEdit && !gridLocked}
            isResizable={editorMode === 'edit' && canEdit && !gridLocked}
            draggableHandle=".drag-handle"
            onLayoutChange={handleLayoutChange}
          >
            {normalWidgets.map((widget) => (
              <div key={widget.id} data-grid={layouts.find((l) => l.i === String(widget.id))}>
                {renderWidget(widget)}
              </div>
            ))}
          </ReactGridLayout>
        )}
      </div>

      {/* 浮动按钮 */}
      <FloatButton.Group shape="circle" style={{ right: 24 }}>
        <FloatButton
          icon={<PlusOutlined />}
          tooltip="添加组件"
          onClick={() => setAddWidgetModalVisible(true)}
        />
        <FloatButton
          icon={<RobotOutlined />}
          tooltip="智能挖掘"
          onClick={() => setMiningWizardVisible(true)}
        />
        <FloatButton.BackTop visibilityHeight={200} />
      </FloatButton.Group>

      {/* Modals */}
      {/* 编辑Widget Modal */}
      <Modal
        title="编辑组件"
        open={editWidgetModalVisible}
        onOk={handleEditWidgetSubmit}
        onCancel={() => {
          setEditWidgetModalVisible(false);
          setEditingWidget(null);
        }}
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

      {/* 详情Modal */}
      <Modal
        title="组件详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {detailWidget && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Text strong>SQL查询：</Text>
              <pre
                style={{
                  background: '#f5f5f5',
                  padding: 10,
                  maxHeight: 200,
                  overflow: 'auto',
                  borderRadius: 4,
                }}
              >
                {detailWidget.query_config?.generated_sql}
              </pre>
            </div>
            <div>
              <Text strong>数据预览：</Text>
              <pre
                style={{
                  background: '#f5f5f5',
                  padding: 10,
                  maxHeight: 300,
                  overflow: 'auto',
                  borderRadius: 4,
                }}
              >
                {JSON.stringify(detailWidget.data_cache, null, 2)}
              </pre>
            </div>
          </Space>
        )}
      </Modal>

      {/* 添加Widget Modal */}
      <Modal
        title="添加组件"
        open={addWidgetModalVisible}
        onCancel={() => setAddWidgetModalVisible(false)}
        footer={null}
        width={700}
      >
        <AddWidgetForm
          dashboardId={dashboardId}
          onSuccess={() => {
            setAddWidgetModalVisible(false);
            fetchDashboard();
          }}
          onCancel={() => setAddWidgetModalVisible(false)}
        />
      </Modal>

      {/* 图表配置面板 */}
      <ChartConfigPanel
        visible={chartConfigVisible}
        onClose={() => {
          setChartConfigVisible(false);
          setConfigWidget(null);
        }}
        config={configWidget?.chart_config}
        columns={configWidget ? getWidgetColumns(configWidget) : []}
        onApply={handleApplyChartConfig}
        onAIRecommend={handleAIRecommend}
      />

      {/* 洞察条件面板 */}
      <InsightConditionPanel
        visible={conditionPanelVisible}
        currentConditions={currentInsightWidget?.query_config?.parameters as InsightConditions}
        onSubmit={async (conditions) => {
          if (currentInsightWidget) {
            await handleRefreshInsights(currentInsightWidget.id, conditions);
          } else {
            await handleGenerateInsights(conditions);
          }
          setConditionPanelVisible(false);
          setCurrentInsightWidget(null);
        }}
        onCancel={() => {
          setConditionPanelVisible(false);
          setCurrentInsightWidget(null);
        }}
      />

      {/* 智能挖掘向导 */}
      <GuidedMiningWizard
        visible={miningWizardVisible}
        dashboardId={dashboardId}
        connectionId={dashboard?.widgets.find((w) => w.connection_id)?.connection_id}
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
