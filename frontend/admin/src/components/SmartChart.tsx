/**
 * SmartChart 组件 - 增强版
 * 支持完整 ECharts 图表库，包括高级图表类型
 * 自动数据分析和图表类型推荐
 */
import React, { useMemo, useRef, useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { Table, Empty, Alert, Button, Modal, Tooltip, Space, Tag } from 'antd';
import { BugOutlined, FullscreenOutlined, DownloadOutlined } from '@ant-design/icons';
import type { ChartConfig } from './ChartConfigPanel';

interface SmartChartProps {
  data: any;
  title?: string;
  height?: number;
  chartType?: string;
  chartConfig?: ChartConfig;
  debug?: boolean;
  onConfigChange?: (config: Partial<ChartConfig>) => void;
}

// 图表类型定义
type ChartType = 
  | 'bar' | 'line' | 'pie' | 'scatter' | 'area' 
  | 'heatmap' | 'radar' | 'funnel' | 'treemap' 
  | 'sunburst' | 'gauge' | 'sankey' | 'graph' 
  | 'map' | 'table';

// 预设配色方案
const COLOR_SCHEMES: Record<string, string[]> = {
  '默认': ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'],
  '科技蓝': ['#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b'],
  '商务灰': ['#37474f', '#455a64', '#546e7a', '#607d8b', '#78909c', '#90a4ae', '#b0bec5', '#cfd8dc'],
  '暖色调': ['#f44336', '#e91e63', '#ff5722', '#ff9800', '#ffc107', '#ffeb3b', '#ff7043', '#ff8a65'],
  '冷色调': ['#3f51b5', '#5c6bc0', '#7986cb', '#9fa8da', '#c5cae9', '#8c9eff', '#536dfe', '#304ffe'],
  '渐变紫': ['#6a1b9a', '#7b1fa2', '#8e24aa', '#9c27b0', '#ab47bc', '#ba68c8', '#ce93d8', '#e1bee7'],
  '马卡龙': ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00'],
};

// 数据标准化
interface NormalizedData {
  rows: any[];
  columns: string[];
}

function normalizeData(data: any): NormalizedData {
  let rows: any[] = [];
  let columns: string[] = [];

  if (!data) return { rows, columns };

  // 格式1: { rows: [[...], [...]], columns: [...] }
  if (data.rows && Array.isArray(data.rows) && data.columns) {
    columns = data.columns;
    rows = data.rows.map((row: any[]) => {
      const obj: any = {};
      columns.forEach((col, i) => {
        obj[col] = row[i];
      });
      return obj;
    });
  }
  // 格式2: { data: [{...}, {...}], columns: [...] }
  else if (data.data && Array.isArray(data.data)) {
    rows = data.data;
    columns = data.columns || (rows[0] ? Object.keys(rows[0]) : []);
  }
  // 格式3: 直接是数组
  else if (Array.isArray(data)) {
    rows = data;
    columns = rows[0] ? Object.keys(rows[0]) : [];
  }
  // 格式4: { result: [...] }
  else if (data.result && Array.isArray(data.result)) {
    rows = data.result;
    columns = rows[0] ? Object.keys(rows[0]) : [];
  }

  return { rows, columns };
}

// 列类型分析
interface ColumnAnalysis {
  numericColumns: string[];
  stringColumns: string[];
  dateColumns: string[];
}

function analyzeColumns(rows: any[], columns: string[]): ColumnAnalysis {
  const numericColumns: string[] = [];
  const stringColumns: string[] = [];
  const dateColumns: string[] = [];

  columns.forEach((col) => {
    const sampleValues = rows.slice(0, 20).map((row) => row[col]).filter((v) => v !== null && v !== undefined);
    
    if (sampleValues.length === 0) return;

    // 数值类型检测
    if (sampleValues.every((v) => typeof v === 'number' || (!isNaN(Number(v)) && v !== '' && v !== null))) {
      numericColumns.push(col);
    }
    // 日期类型检测
    else if (sampleValues.every((v) => {
      const str = String(v);
      if (/^\d{4}[-/]\d{2}[-/]\d{2}/.test(str)) return true;
      const date = new Date(str);
      return !isNaN(date.getTime()) && str.length > 4;
    }) || /date|time|日期|时间|year|month|day/i.test(col)) {
      dateColumns.push(col);
    }
    else {
      stringColumns.push(col);
    }
  });

  return { numericColumns, stringColumns, dateColumns };
}

// 智能图表类型推荐
function recommendChartType(
  rows: any[],
  analysis: ColumnAnalysis,
  manualType?: string
): ChartType {
  if (manualType && manualType !== 'auto') {
    return manualType as ChartType;
  }

  const { numericColumns, stringColumns, dateColumns } = analysis;
  const rowCount = rows.length;

  // 规则1: 饼图 - 一个数值列 + 一个分类列，数据量少
  if (numericColumns.length === 1 && stringColumns.length === 1 && rowCount <= 15) {
    return 'pie';
  }

  // 规则2: 折线图 - 有日期列
  if (dateColumns.length > 0 && numericColumns.length > 0) {
    return 'line';
  }

  // 规则3: 散点图 - 两个以上数值列，没有分类
  if (numericColumns.length >= 2 && stringColumns.length === 0) {
    return 'scatter';
  }

  // 规则4: 热力图 - 两个分类列 + 一个数值列
  if (stringColumns.length >= 2 && numericColumns.length === 1) {
    return 'heatmap';
  }

  // 规则5: 漏斗图 - 分类有明显层级含义
  if (stringColumns.length === 1 && numericColumns.length === 1) {
    const labels = rows.map((r) => String(r[stringColumns[0]]).toLowerCase());
    const funnelKeywords = ['访问', '注册', '付费', '转化', 'visit', 'register', 'pay', 'convert', '阶段', 'stage'];
    if (labels.some((l) => funnelKeywords.some((k) => l.includes(k)))) {
      return 'funnel';
    }
  }

  // 规则6: 雷达图 - 多个数值指标，分类数量少
  if (numericColumns.length >= 3 && stringColumns.length === 1 && rowCount <= 5) {
    return 'radar';
  }

  // 默认: 柱状图
  if (stringColumns.length > 0 && numericColumns.length > 0) {
    return 'bar';
  }

  // 纯数值，用柱状图
  if (numericColumns.length > 0) {
    return 'bar';
  }

  return 'table';
}

// 生成ECharts配置
function generateChartOption(
  chartType: ChartType,
  rows: any[],
  analysis: ColumnAnalysis,
  config?: ChartConfig,
  title?: string
): EChartsOption | null {
  const { numericColumns, stringColumns, dateColumns } = analysis;
  const colors = COLOR_SCHEMES[config?.color_scheme || '默认'];
  
  // X轴列选择
  const xColumn = config?.data_mapping?.x_column || dateColumns[0] || stringColumns[0];
  // Y轴列选择
  const yColumns = config?.data_mapping?.y_columns?.length 
    ? config.data_mapping.y_columns 
    : numericColumns;

  if (!xColumn && chartType !== 'gauge' && chartType !== 'table') {
    return null;
  }

  // 基础配置
  const baseOption: EChartsOption = {
    color: colors,
    title: title || config?.title ? {
      text: title || config?.title,
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 },
    } : undefined,
    tooltip: config?.tooltip?.show !== false ? {
      trigger: config?.tooltip?.trigger || (chartType === 'pie' ? 'item' : 'axis'),
      confine: true,
    } : undefined,
    toolbox: {
      feature: {
        saveAsImage: { title: '保存' },
        ...(chartType !== 'pie' && chartType !== 'radar' && chartType !== 'funnel' && chartType !== 'gauge' 
          ? { dataZoom: { title: { zoom: '缩放', back: '还原' } } } 
          : {}),
      },
      right: 10,
      top: 0,
    },
    grid: !['pie', 'radar', 'funnel', 'gauge', 'treemap', 'sunburst', 'sankey', 'graph'].includes(chartType)
      ? { left: '3%', right: '4%', bottom: config?.legend?.show !== false ? '15%' : '3%', containLabel: true }
      : undefined,
    legend: config?.legend?.show !== false ? {
      show: true,
      type: 'scroll',
      ...(config?.legend?.position === 'top' ? { top: 30 } :
         config?.legend?.position === 'left' ? { left: 10, orient: 'vertical' as const, top: 'middle' } :
         config?.legend?.position === 'right' ? { right: 10, orient: 'vertical' as const, top: 'middle' } :
         { bottom: 0 })
    } : undefined,
  };

  // 排序数据（如果是日期）
  const sortedRows = xColumn && dateColumns.includes(xColumn)
    ? [...rows].sort((a, b) => new Date(a[xColumn]).getTime() - new Date(b[xColumn]).getTime())
    : rows;

  // 截取数据（避免过多）
  const displayRows = sortedRows.length > 100 ? sortedRows.slice(0, 100) : sortedRows;
  const xAxisData = xColumn ? displayRows.map((row) => String(row[xColumn] || '')) : displayRows.map((_, i) => `数据${i + 1}`);

  switch (chartType) {
    case 'pie':
      const labelCol = stringColumns[0] || xColumn;
      const valueCol = yColumns[0] || numericColumns[0];
      return {
        ...baseOption,
        series: [{
          type: 'pie',
          radius: config?.series_config?.radius || ['40%', '70%'],
          center: ['50%', '55%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
          label: {
            show: config?.series_config?.label !== false,
            formatter: '{b}: {d}%',
          },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: 'bold' },
            itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
          },
          data: displayRows.map((row) => ({
            name: String(row[labelCol] || ''),
            value: Number(row[valueCol]) || 0,
          })),
        }],
      };

    case 'line':
    case 'area':
      return {
        ...baseOption,
        xAxis: {
          type: 'category',
          data: xAxisData,
          boundaryGap: false,
          axisLabel: { interval: 'auto', rotate: xAxisData.length > 10 ? 30 : 0 },
          name: config?.axis?.xAxisName,
        },
        yAxis: {
          type: 'value',
          name: config?.axis?.yAxisName,
          splitLine: { show: config?.axis?.showGrid !== false },
        },
        series: yColumns.map((col) => ({
          name: col,
          type: 'line' as const,
          smooth: config?.series_config?.smooth !== false,
          data: displayRows.map((row) => Number(row[col]) || 0),
          ...(chartType === 'area' ? { areaStyle: { opacity: 0.4 } } : {}),
          ...(config?.series_config?.stack ? { stack: 'total' } : {}),
        })),
      };

    case 'bar':
      return {
        ...baseOption,
        xAxis: {
          type: 'category',
          data: xAxisData,
          axisLabel: {
            interval: 0,
            rotate: xAxisData.length > 8 ? 30 : 0,
            hideOverlap: true,
          },
          name: config?.axis?.xAxisName,
        },
        yAxis: {
          type: 'value',
          name: config?.axis?.yAxisName,
          splitLine: { show: config?.axis?.showGrid !== false },
        },
        series: yColumns.map((col) => ({
          name: col,
          type: 'bar' as const,
          data: displayRows.map((row) => Number(row[col]) || 0),
          barMaxWidth: 50,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
          ...(config?.series_config?.stack ? { stack: 'total' } : {}),
          label: config?.series_config?.label ? {
            show: true,
            position: 'top',
            fontSize: 10,
          } : undefined,
        })),
      };

    case 'scatter':
      const xNumCol = yColumns[0] || numericColumns[0];
      const yNumCol = yColumns[1] || numericColumns[1];
      return {
        ...baseOption,
        xAxis: {
          type: 'value',
          scale: true,
          name: config?.axis?.xAxisName || xNumCol,
        },
        yAxis: {
          type: 'value',
          scale: true,
          name: config?.axis?.yAxisName || yNumCol,
        },
        series: [{
          type: 'scatter',
          data: displayRows.map((row) => [
            Number(row[xNumCol]) || 0,
            Number(row[yNumCol]) || 0,
          ]),
          symbolSize: 12,
          emphasis: {
            focus: 'series',
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
          },
        }],
      };

    case 'radar':
      const indicators = yColumns.map((col) => ({
        name: col,
        max: Math.max(...displayRows.map((row) => Number(row[col]) || 0)) * 1.2 || 100,
      }));
      const categoryCol = stringColumns[0] || xColumn;
      return {
        ...baseOption,
        radar: {
          indicator: indicators,
          center: ['50%', '55%'],
          radius: '65%',
        },
        series: [{
          type: 'radar',
          data: displayRows.map((row) => ({
            value: yColumns.map((col) => Number(row[col]) || 0),
            name: categoryCol ? String(row[categoryCol]) : '',
          })),
          areaStyle: { opacity: 0.3 },
        }],
      };

    case 'funnel':
      const funnelLabelCol = stringColumns[0] || xColumn;
      const funnelValueCol = yColumns[0] || numericColumns[0];
      const maxVal = Math.max(...displayRows.map((row) => Number(row[funnelValueCol]) || 0));
      return {
        ...baseOption,
        series: [{
          type: 'funnel',
          left: '10%',
          top: 60,
          bottom: 60,
          width: '80%',
          minSize: '0%',
          maxSize: '100%',
          sort: 'descending',
          gap: 2,
          label: {
            show: true,
            position: 'inside',
            formatter: '{b}: {c}',
          },
          labelLine: { show: false },
          itemStyle: { borderColor: '#fff', borderWidth: 1 },
          emphasis: {
            label: { fontSize: 14, fontWeight: 'bold' },
          },
          data: displayRows.map((row) => ({
            name: String(row[funnelLabelCol] || ''),
            value: Number(row[funnelValueCol]) || 0,
          })).sort((a, b) => b.value - a.value),
        }],
      };

    case 'heatmap':
      if (stringColumns.length < 2) return null;
      const xCatCol = stringColumns[0];
      const yCatCol = stringColumns[1];
      const heatValCol = numericColumns[0];
      const xCategories = Array.from(new Set(displayRows.map((r) => String(r[xCatCol]))));
      const yCategories = Array.from(new Set(displayRows.map((r) => String(r[yCatCol]))));
      const heatmapData: [number, number, number][] = displayRows.map((row) => [
        xCategories.indexOf(String(row[xCatCol])),
        yCategories.indexOf(String(row[yCatCol])),
        Number(row[heatValCol]) || 0,
      ]);
      const values = heatmapData.map((d) => d[2]);
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xCategories, splitArea: { show: true } },
        yAxis: { type: 'category', data: yCategories, splitArea: { show: true } },
        visualMap: {
          min: Math.min(...values),
          max: Math.max(...values),
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '0%',
          inRange: { color: ['#f7fbff', '#08306b'] },
        },
        series: [{
          type: 'heatmap',
          data: heatmapData,
          label: { show: displayRows.length <= 50 },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' },
          },
        }],
      };

    case 'treemap':
      const treeLabelCol = stringColumns[0] || xColumn;
      const treeValueCol = yColumns[0] || numericColumns[0];
      return {
        ...baseOption,
        series: [{
          type: 'treemap',
          data: displayRows.map((row) => ({
            name: String(row[treeLabelCol] || ''),
            value: Number(row[treeValueCol]) || 0,
          })),
          leafDepth: 1,
          roam: false,
          label: { show: true, formatter: '{b}\n{c}' },
          breadcrumb: { show: false },
        }],
      };

    case 'sunburst':
      // 简化的旭日图，需要层级数据
      const sunLabelCol = stringColumns[0] || xColumn;
      const sunValueCol = yColumns[0] || numericColumns[0];
      return {
        ...baseOption,
        series: [{
          type: 'sunburst',
          data: displayRows.map((row) => ({
            name: String(row[sunLabelCol] || ''),
            value: Number(row[sunValueCol]) || 0,
          })),
          radius: ['15%', '80%'],
          label: { rotate: 'radial' },
          emphasis: { focus: 'ancestor' },
        }],
      };

    case 'gauge':
      const gaugeValue = numericColumns.length > 0
        ? Number(displayRows[0]?.[numericColumns[0]]) || 0
        : 0;
      return {
        ...baseOption,
        series: [{
          type: 'gauge',
          center: ['50%', '60%'],
          radius: '80%',
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: Math.max(100, gaugeValue * 1.5),
          splitNumber: 10,
          axisLine: {
            lineStyle: {
              width: 20,
              color: [
                [0.3, '#67e0e3'],
                [0.7, '#37a2da'],
                [1, '#fd666d'],
              ],
            },
          },
          pointer: { itemStyle: { color: 'auto' } },
          axisTick: { distance: -30, length: 8, lineStyle: { color: '#fff', width: 2 } },
          splitLine: { distance: -30, length: 30, lineStyle: { color: '#fff', width: 4 } },
          axisLabel: { color: 'inherit', distance: 40, fontSize: 12 },
          detail: { valueAnimation: true, formatter: '{value}', color: 'inherit', fontSize: 24 },
          data: [{ value: gaugeValue, name: numericColumns[0] || '值' }],
        }],
      };

    case 'sankey':
      // 桑基图需要特殊的数据格式，这里做简化处理
      if (stringColumns.length < 2 || numericColumns.length < 1) return null;
      const sourceCol = stringColumns[0];
      const targetCol = stringColumns[1];
      const linkValueCol = numericColumns[0];
      const nodes = new Set<string>();
      displayRows.forEach((row) => {
        nodes.add(String(row[sourceCol]));
        nodes.add(String(row[targetCol]));
      });
      return {
        ...baseOption,
        series: [{
          type: 'sankey',
          layout: 'none',
          emphasis: { focus: 'adjacency' },
          data: Array.from(nodes).map((name) => ({ name })),
          links: displayRows.map((row) => ({
            source: String(row[sourceCol]),
            target: String(row[targetCol]),
            value: Number(row[linkValueCol]) || 1,
          })),
          lineStyle: { color: 'gradient', curveness: 0.5 },
        }],
      };

    default:
      return null;
  }
}

export const SmartChart: React.FC<SmartChartProps> = ({
  data,
  title,
  height = 350,
  chartType: manualChartType,
  chartConfig,
  debug = false,
  onConfigChange,
}) => {
  const chartRef = useRef<ReactECharts>(null);
  const [debugVisible, setDebugVisible] = useState(false);
  const [fullscreenVisible, setFullscreenVisible] = useState(false);

  useEffect(() => {
    return () => {
      try {
        if (chartRef.current) {
          const instance = chartRef.current.getEchartsInstance();
          if (instance && !instance.isDisposed()) {
            instance.dispose();
          }
        }
      } catch (e) {
        console.debug('Chart cleanup:', e);
      }
    };
  }, []);

  const { chartOption, normalizedData, detectedType, error } = useMemo(() => {
    if (!data) {
      return { chartOption: null, normalizedData: { rows: [], columns: [] }, detectedType: 'table', error: null };
    }

    if (data.error) {
      return { chartOption: null, normalizedData: { rows: [], columns: [] }, detectedType: 'table', error: data.error };
    }

    try {
      const normalized = normalizeData(data);
      
      if (normalized.rows.length === 0 || normalized.columns.length === 0) {
        return { chartOption: null, normalizedData: normalized, detectedType: 'table', error: null };
      }

      const analysis = analyzeColumns(normalized.rows, normalized.columns);
      const recommendedType = recommendChartType(normalized.rows, analysis, manualChartType || chartConfig?.chart_type);
      
      if (recommendedType === 'table') {
        return { chartOption: null, normalizedData: normalized, detectedType: 'table', error: null };
      }

      const option = generateChartOption(
        recommendedType,
        normalized.rows,
        analysis,
        chartConfig,
        title
      );

      return {
        chartOption: option,
        normalizedData: normalized,
        detectedType: recommendedType,
        error: null,
      };
    } catch (e) {
      console.error('图表生成失败:', e);
      const normalized = normalizeData(data);
      return {
        chartOption: null,
        normalizedData: normalized,
        detectedType: 'table',
        error: String(e),
      };
    }
  }, [data, title, manualChartType, chartConfig]);

  // 下载图表
  const handleDownload = () => {
    if (chartRef.current) {
      const instance = chartRef.current.getEchartsInstance();
      const url = instance.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      });
      const link = document.createElement('a');
      link.download = `${title || 'chart'}.png`;
      link.href = url;
      link.click();
    }
  };

  // 工具栏
  const renderToolbar = () => (
    <div style={{ position: 'absolute', right: 4, top: 4, zIndex: 10, display: 'flex', gap: 4 }}>
      {chartOption && (
        <>
          <Tooltip title="全屏">
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              onClick={() => setFullscreenVisible(true)}
              style={{ opacity: 0.5 }}
            />
          </Tooltip>
          <Tooltip title="下载">
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              style={{ opacity: 0.5 }}
            />
          </Tooltip>
        </>
      )}
      {debug && (
        <Tooltip title="调试">
          <Button
            type="text"
            size="small"
            icon={<BugOutlined />}
            onClick={() => setDebugVisible(true)}
            style={{ opacity: 0.5 }}
          />
        </Tooltip>
      )}
    </div>
  );

  // 错误展示
  if (error) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <Alert message="数据加载失败" description={error} type="error" showIcon />
        {renderToolbar()}
      </div>
    );
  }

  // 降级为表格
  if (!chartOption) {
    if (normalizedData.rows.length > 0 && normalizedData.columns.length > 0) {
      const columns = normalizedData.columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        render: (text: any) => <span title={String(text ?? '')}>{String(text ?? '-')}</span>,
      }));

      return (
        <div style={{ height, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {title && (
            <div style={{ textAlign: 'center', marginBottom: 8, fontWeight: 500 }}>
              {title}
            </div>
          )}
          <Table
            dataSource={normalizedData.rows.map((r, i) => ({ ...r, key: i }))}
            columns={columns}
            pagination={{ pageSize: 5, size: 'small', simple: true }}
            size="small"
            scroll={{ y: height - 100 }}
            style={{ flex: 1, overflow: 'hidden' }}
          />
          {renderToolbar()}
        </div>
      );
    }

    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
        {renderToolbar()}
      </div>
    );
  }

  return (
    <>
      <div style={{ position: 'relative', height }}>
        <ReactECharts
          ref={chartRef}
          option={chartOption}
          style={{ height: '100%', width: '100%' }}
          opts={{ renderer: 'svg', locale: 'ZH' }}
          notMerge={true}
          lazyUpdate={true}
        />
        {renderToolbar()}
      </div>

      {/* 调试Modal */}
      <Modal
        title="数据调试"
        open={debugVisible}
        onCancel={() => setDebugVisible(false)}
        footer={null}
        width={800}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Tag color="blue">检测到的图表类型: {detectedType}</Tag>
            <Tag color="green">数据行数: {normalizedData.rows.length}</Tag>
            <Tag color="orange">数据列数: {normalizedData.columns.length}</Tag>
          </div>
          <div>
            <strong>列名:</strong> {normalizedData.columns.join(', ')}
          </div>
          <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 10, borderRadius: 4 }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </Space>
      </Modal>

      {/* 全屏Modal */}
      <Modal
        title={title || '图表详情'}
        open={fullscreenVisible}
        onCancel={() => setFullscreenVisible(false)}
        footer={null}
        width="90%"
        style={{ top: 20 }}
      >
        <ReactECharts
          option={chartOption}
          style={{ height: '70vh', width: '100%' }}
          opts={{ renderer: 'svg', locale: 'ZH' }}
          notMerge={true}
        />
      </Modal>
    </>
  );
};

export default SmartChart;
