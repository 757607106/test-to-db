/**
 * ChartConfigPanel - 图表配置面板
 * 支持图表类型选择、样式配置、数据映射等
 */
import React, { useState, useEffect, useMemo } from 'react';
import {
  Drawer,
  Form,
  Select,
  Input,
  Switch,
  Collapse,
  Space,
  Button,
  Divider,
  Tag,
  Radio,
  message,
} from 'antd';
import {
  BarChartOutlined,
  LineChartOutlined,
  PieChartOutlined,
  DotChartOutlined,
  HeatMapOutlined,
  RadarChartOutlined,
  FunnelPlotOutlined,
  AreaChartOutlined,
  TableOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons';

const { Option } = Select;

// 支持的图表类型
export const CHART_TYPES = [
  { value: 'bar', label: '柱状图', icon: <BarChartOutlined />, category: '基础' },
  { value: 'line', label: '折线图', icon: <LineChartOutlined />, category: '基础' },
  { value: 'pie', label: '饼图', icon: <PieChartOutlined />, category: '基础' },
  { value: 'scatter', label: '散点图', icon: <DotChartOutlined />, category: '基础' },
  { value: 'area', label: '面积图', icon: <AreaChartOutlined />, category: '基础' },
  { value: 'table', label: '表格', icon: <TableOutlined />, category: '基础' },
  { value: 'heatmap', label: '热力图', icon: <HeatMapOutlined />, category: '高级' },
  { value: 'radar', label: '雷达图', icon: <RadarChartOutlined />, category: '高级' },
  { value: 'funnel', label: '漏斗图', icon: <FunnelPlotOutlined />, category: '高级' },
  { value: 'treemap', label: '矩形树图', icon: <BarChartOutlined />, category: '高级' },
  { value: 'sunburst', label: '旭日图', icon: <PieChartOutlined />, category: '高级' },
  { value: 'gauge', label: '仪表盘', icon: <SettingOutlined />, category: '高级' },
  { value: 'map', label: '地图', icon: <HeatMapOutlined />, category: '地图' },
  { value: 'graph', label: '关系图', icon: <DotChartOutlined />, category: '关系' },
  { value: 'sankey', label: '桑基图', icon: <FunnelPlotOutlined />, category: '流量' },
];

// 预设配色方案
export const COLOR_SCHEMES = [
  { name: '默认', colors: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'] },
  { name: '科技蓝', colors: ['#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b'] },
  { name: '商务灰', colors: ['#37474f', '#455a64', '#546e7a', '#607d8b', '#78909c', '#90a4ae', '#b0bec5', '#cfd8dc'] },
  { name: '暖色调', colors: ['#f44336', '#e91e63', '#ff5722', '#ff9800', '#ffc107', '#ffeb3b', '#ff7043', '#ff8a65'] },
  { name: '冷色调', colors: ['#3f51b5', '#5c6bc0', '#7986cb', '#9fa8da', '#c5cae9', '#8c9eff', '#536dfe', '#304ffe'] },
  { name: '渐变紫', colors: ['#6a1b9a', '#7b1fa2', '#8e24aa', '#9c27b0', '#ab47bc', '#ba68c8', '#ce93d8', '#e1bee7'] },
];

export interface ChartConfig {
  chart_type: string;
  title?: string;
  color_scheme?: string;
  custom_colors?: string[];
  legend?: {
    show: boolean;
    position: 'top' | 'bottom' | 'left' | 'right';
  };
  axis?: {
    xAxisName?: string;
    yAxisName?: string;
    showGrid?: boolean;
  };
  tooltip?: {
    show: boolean;
    trigger: 'item' | 'axis';
  };
  series_config?: {
    smooth?: boolean; // 折线图平滑
    stack?: boolean; // 堆叠
    label?: boolean; // 显示标签
    radius?: [string, string]; // 饼图半径
  };
  data_mapping?: {
    x_column?: string;
    y_columns?: string[];
    category_column?: string;
  };
}

interface ChartConfigPanelProps {
  visible: boolean;
  onClose: () => void;
  config?: ChartConfig;
  columns?: string[];
  onApply: (config: ChartConfig) => void;
  onAIRecommend?: () => Promise<ChartConfig | null>;
  loading?: boolean;
}

export const ChartConfigPanel: React.FC<ChartConfigPanelProps> = ({
  visible,
  onClose,
  config,
  columns = [],
  onApply,
  onAIRecommend,
  loading = false,
}) => {
  const [form] = Form.useForm();
  const [aiLoading, setAiLoading] = useState(false);
  const [selectedType, setSelectedType] = useState<string>(config?.chart_type || 'bar');

  useEffect(() => {
    if (config) {
      form.setFieldsValue({
        chart_type: config.chart_type,
        title: config.title,
        color_scheme: config.color_scheme || '默认',
        legend_show: config.legend?.show ?? true,
        legend_position: config.legend?.position || 'bottom',
        x_axis_name: config.axis?.xAxisName,
        y_axis_name: config.axis?.yAxisName,
        show_grid: config.axis?.showGrid ?? true,
        tooltip_show: config.tooltip?.show ?? true,
        tooltip_trigger: config.tooltip?.trigger || 'axis',
        smooth: config.series_config?.smooth ?? true,
        stack: config.series_config?.stack ?? false,
        show_label: config.series_config?.label ?? false,
        x_column: config.data_mapping?.x_column,
        y_columns: config.data_mapping?.y_columns,
        category_column: config.data_mapping?.category_column,
      });
      setSelectedType(config.chart_type);
    }
  }, [config, form]);

  const handleTypeChange = (value: string) => {
    setSelectedType(value);
    form.setFieldValue('chart_type', value);
  };

  const handleAIRecommend = async () => {
    if (!onAIRecommend) return;
    setAiLoading(true);
    try {
      const recommended = await onAIRecommend();
      if (recommended) {
        form.setFieldsValue({
          chart_type: recommended.chart_type,
          title: recommended.title,
          x_column: recommended.data_mapping?.x_column,
          y_columns: recommended.data_mapping?.y_columns,
        });
        setSelectedType(recommended.chart_type);
        message.success('AI 已推荐最佳图表配置');
      }
    } catch (error) {
      message.error('AI 推荐失败');
    } finally {
      setAiLoading(false);
    }
  };

  const handleApply = () => {
    const values = form.getFieldsValue();
    const newConfig: ChartConfig = {
      chart_type: values.chart_type || selectedType,
      title: values.title,
      color_scheme: values.color_scheme,
      legend: {
        show: values.legend_show,
        position: values.legend_position,
      },
      axis: {
        xAxisName: values.x_axis_name,
        yAxisName: values.y_axis_name,
        showGrid: values.show_grid,
      },
      tooltip: {
        show: values.tooltip_show,
        trigger: values.tooltip_trigger,
      },
      series_config: {
        smooth: values.smooth,
        stack: values.stack,
        label: values.show_label,
      },
      data_mapping: {
        x_column: values.x_column,
        y_columns: values.y_columns,
        category_column: values.category_column,
      },
    };
    onApply(newConfig);
    onClose();
  };

  const groupedChartTypes = useMemo(() => {
    const groups: Record<string, typeof CHART_TYPES> = {};
    CHART_TYPES.forEach((type) => {
      if (!groups[type.category]) {
        groups[type.category] = [];
      }
      groups[type.category].push(type);
    });
    return groups;
  }, []);

  return (
    <Drawer
      title="图表配置"
      placement="right"
      width={400}
      onClose={onClose}
      open={visible}
      extra={
        <Space>
          {onAIRecommend && (
            <Button
              icon={<RobotOutlined />}
              onClick={handleAIRecommend}
              loading={aiLoading}
            >
              AI 推荐
            </Button>
          )}
          <Button type="primary" onClick={handleApply} loading={loading}>
            应用
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" size="small">
        {/* 图表类型选择 */}
        <Form.Item label="图表类型" name="chart_type">
          <div style={{ marginBottom: 12 }}>
            {Object.entries(groupedChartTypes).map(([category, types]) => (
              <div key={category} style={{ marginBottom: 8 }}>
                <Tag color="blue" style={{ marginBottom: 4 }}>{category}</Tag>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {types.map((type) => (
                    <Button
                      key={type.value}
                      type={selectedType === type.value ? 'primary' : 'default'}
                      icon={type.icon}
                      size="small"
                      onClick={() => handleTypeChange(type.value)}
                      style={{ marginBottom: 4 }}
                    >
                      {type.label}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Form.Item>

        <Divider />

        <Collapse 
          defaultActiveKey={['basic', 'data']} 
          ghost
          items={[
            {
              key: 'basic',
              label: '基础设置',
              children: (
                <>
                  <Form.Item label="图表标题" name="title">
                    <Input placeholder="输入图表标题" />
                  </Form.Item>

                  <Form.Item label="配色方案" name="color_scheme">
                    <Select>
                      {COLOR_SCHEMES.map((scheme) => (
                        <Option key={scheme.name} value={scheme.name}>
                          <Space>
                            {scheme.name}
                            <div style={{ display: 'flex', gap: 2 }}>
                              {scheme.colors.slice(0, 5).map((color, i) => (
                                <div
                                  key={i}
                                  style={{
                                    width: 12,
                                    height: 12,
                                    background: color,
                                    borderRadius: 2,
                                  }}
                                />
                              ))}
                            </div>
                          </Space>
                        </Option>
                      ))}
                    </Select>
                  </Form.Item>
                </>
              )
            },
            {
              key: 'data',
              label: '数据映射',
              children: (
                <>
                  {columns.length > 0 && (
                    <>
                      <Form.Item label="X轴/分类字段" name="x_column">
                        <Select placeholder="选择字段" allowClear>
                          {columns.map((col) => (
                            <Option key={col} value={col}>{col}</Option>
                          ))}
                        </Select>
                      </Form.Item>

                      <Form.Item label="Y轴/数值字段" name="y_columns">
                        <Select mode="multiple" placeholder="选择字段" allowClear>
                          {columns.map((col) => (
                            <Option key={col} value={col}>{col}</Option>
                          ))}
                        </Select>
                      </Form.Item>

                      <Form.Item label="分组字段" name="category_column">
                        <Select placeholder="选择字段" allowClear>
                          {columns.map((col) => (
                            <Option key={col} value={col}>{col}</Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </>
                  )}
                </>
              )
            },
            {
              key: 'legend',
              label: '图例',
              children: (
                <>
                  <Form.Item label="显示图例" name="legend_show" valuePropName="checked">
                    <Switch />
                  </Form.Item>

                  <Form.Item label="图例位置" name="legend_position">
                    <Radio.Group>
                      <Radio.Button value="top">上</Radio.Button>
                      <Radio.Button value="bottom">下</Radio.Button>
                      <Radio.Button value="left">左</Radio.Button>
                      <Radio.Button value="right">右</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </>
              )
            },
            ...(!['pie', 'radar', 'funnel', 'gauge', 'sunburst', 'treemap'].includes(selectedType) ? [{
              key: 'axis',
              label: '坐标轴',
              children: (
                <>
                  <Form.Item label="X轴名称" name="x_axis_name">
                    <Input placeholder="输入X轴名称" />
                  </Form.Item>

                  <Form.Item label="Y轴名称" name="y_axis_name">
                    <Input placeholder="输入Y轴名称" />
                  </Form.Item>

                  <Form.Item label="显示网格线" name="show_grid" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </>
              )
            }] : []),
            {
              key: 'series',
              label: '系列配置',
              children: (
                <>
                  {['line', 'area'].includes(selectedType) && (
                    <Form.Item label="平滑曲线" name="smooth" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  )}

                  {['bar', 'line', 'area'].includes(selectedType) && (
                    <Form.Item label="堆叠显示" name="stack" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  )}

                  <Form.Item label="显示数据标签" name="show_label" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </>
              )
            },
            {
              key: 'tooltip',
              label: '提示框',
              children: (
                <>
                  <Form.Item label="显示提示框" name="tooltip_show" valuePropName="checked">
                    <Switch />
                  </Form.Item>

                  <Form.Item label="触发方式" name="tooltip_trigger">
                    <Radio.Group>
                      <Radio.Button value="item">数据项</Radio.Button>
                      <Radio.Button value="axis">坐标轴</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                </>
              )
            }
          ]}
        />
      </Form>
    </Drawer>
  );
};

export default ChartConfigPanel;
