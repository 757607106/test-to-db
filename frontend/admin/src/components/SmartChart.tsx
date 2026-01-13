/**
 * SmartChart 组件
 * 根据数据自动选择合适的ECharts图表类型进行渲染
 */
import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface SmartChartProps {
  data: any;
  title?: string;
  height?: number;
}

// 分析数据结构，判断最适合的图表类型
type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'table';

function analyzeDataAndGetChartType(data: any): {
  chartType: ChartType;
  xAxisData: string[];
  seriesData: { name: string; data: number[] }[];
  pieData: { name: string; value: number }[];
} {
  // 默认返回值
  const result: {
    chartType: ChartType;
    xAxisData: string[];
    seriesData: { name: string; data: number[] }[];
    pieData: { name: string; value: number }[];
  } = {
    chartType: 'bar',
    xAxisData: [],
    seriesData: [],
    pieData: [],
  };

  if (!data) return result;

  // 处理不同的数据格式
  let rows: any[] = [];
  let columns: string[] = [];

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
  // 格式3: 直接是数组 [{...}, {...}]
  else if (Array.isArray(data)) {
    rows = data;
    columns = rows[0] ? Object.keys(rows[0]) : [];
  }

  if (rows.length === 0 || columns.length === 0) {
    return result;
  }

  // 分析列类型
  const numericColumns: string[] = [];
  const stringColumns: string[] = [];
  const dateColumns: string[] = [];

  columns.forEach((col) => {
    const sampleValues = rows.slice(0, 5).map((row) => row[col]).filter((v) => v !== null && v !== undefined);
    
    if (sampleValues.length === 0) return;

    // 检查是否是数值类型
    if (sampleValues.every((v) => typeof v === 'number' || !isNaN(Number(v)))) {
      numericColumns.push(col);
    }
    // 检查是否是日期类型
    else if (sampleValues.every((v) => /^\d{4}[-/]\d{2}[-/]\d{2}/.test(String(v)) || /date|time|日期|时间/i.test(col))) {
      dateColumns.push(col);
    }
    else {
      stringColumns.push(col);
    }
  });

  // 决定图表类型
  const hasDimension = stringColumns.length > 0 || dateColumns.length > 0;
  const hasMetric = numericColumns.length > 0;

  // 只有一个数值列且有分类列 → 饼图
  if (numericColumns.length === 1 && stringColumns.length === 1 && rows.length <= 10) {
    result.chartType = 'pie';
    const labelCol = stringColumns[0];
    const valueCol = numericColumns[0];
    result.pieData = rows.map((row) => ({
      name: String(row[labelCol] || ''),
      value: Number(row[valueCol]) || 0,
    }));
    return result;
  }

  // 有日期列 → 折线图
  if (dateColumns.length > 0 && numericColumns.length > 0) {
    result.chartType = 'line';
    const xCol = dateColumns[0];
    result.xAxisData = rows.map((row) => String(row[xCol] || ''));
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: rows.map((row) => Number(row[col]) || 0),
    }));
    return result;
  }

  // 有分类列和数值列 → 柱状图
  if (stringColumns.length > 0 && numericColumns.length > 0) {
    result.chartType = 'bar';
    const xCol = stringColumns[0];
    result.xAxisData = rows.map((row) => String(row[xCol] || ''));
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: rows.map((row) => Number(row[col]) || 0),
    }));
    return result;
  }

  // 两个数值列 → 散点图
  if (numericColumns.length >= 2) {
    result.chartType = 'scatter';
    result.seriesData = [{
      name: `${numericColumns[0]} vs ${numericColumns[1]}`,
      data: rows.map((row) => [Number(row[numericColumns[0]]) || 0, Number(row[numericColumns[1]]) || 0]) as any,
    }];
    return result;
  }

  // 默认柱状图
  if (numericColumns.length > 0) {
    result.chartType = 'bar';
    result.xAxisData = rows.map((_, i) => `数据${i + 1}`);
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: rows.map((row) => Number(row[col]) || 0),
    }));
  }

  return result;
}

// 生成ECharts配置
function generateChartOption(
  chartType: string,
  xAxisData: string[],
  seriesData: { name: string; data: number[] }[],
  pieData: { name: string; value: number }[],
  title?: string
): EChartsOption {
  const baseOption: EChartsOption = {
    title: title ? { text: title, left: 'center', textStyle: { fontSize: 14 } } : undefined,
    tooltip: { trigger: chartType === 'pie' ? 'item' : 'axis' },
    toolbox: {
      feature: {
        saveAsImage: { title: '保存' },
        dataZoom: chartType !== 'pie' ? { title: { zoom: '缩放', back: '还原' } } : undefined,
      },
      right: 10,
    },
    grid: chartType !== 'pie' ? { left: '3%', right: '4%', bottom: '3%', containLabel: true } : undefined,
  };

  switch (chartType) {
    case 'pie':
      return {
        ...baseOption,
        legend: { orient: 'vertical', left: 'left', top: 'middle' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}: {c} ({d}%)' },
          emphasis: {
            label: { show: true, fontSize: 16, fontWeight: 'bold' },
          },
          data: pieData,
        }],
      };

    case 'line':
      return {
        ...baseOption,
        legend: { data: seriesData.map((s) => s.name), bottom: 0 },
        xAxis: { type: 'category', data: xAxisData, boundaryGap: false },
        yAxis: { type: 'value' },
        series: seriesData.map((s) => ({
          name: s.name,
          type: 'line',
          smooth: true,
          data: s.data,
          areaStyle: seriesData.length === 1 ? { opacity: 0.3 } : undefined,
        })),
      };

    case 'scatter':
      return {
        ...baseOption,
        xAxis: { type: 'value', scale: true },
        yAxis: { type: 'value', scale: true },
        series: seriesData.map((s) => ({
          name: s.name,
          type: 'scatter',
          data: s.data,
          symbolSize: 10,
        })),
      };

    case 'bar':
    default:
      return {
        ...baseOption,
        legend: seriesData.length > 1 ? { data: seriesData.map((s) => s.name), bottom: 0 } : undefined,
        xAxis: { type: 'category', data: xAxisData, axisLabel: { interval: 0, rotate: xAxisData.length > 5 ? 30 : 0 } },
        yAxis: { type: 'value' },
        series: seriesData.map((s) => ({
          name: s.name,
          type: 'bar',
          data: s.data,
          barMaxWidth: 50,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        })),
      };
  }
}

export const SmartChart: React.FC<SmartChartProps> = ({ data, title, height = 350 }) => {
  const chartOption = useMemo(() => {
    if (!data) return null;

    const { chartType, xAxisData, seriesData, pieData } = analyzeDataAndGetChartType(data);

    // 数据不足以生成图表
    if (chartType === 'pie' && pieData.length === 0) return null;
    if (chartType !== 'pie' && seriesData.length === 0) return null;

    return generateChartOption(chartType, xAxisData, seriesData, pieData, title);
  }, [data, title]);

  if (!chartOption) {
    return (
      <div style={{ 
        height, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: '#fafafa',
        borderRadius: 8,
        color: '#999'
      }}>
        数据格式不支持图表展示
      </div>
    );
  }

  return (
    <ReactECharts
      option={chartOption}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'svg' }}
    />
  );
};

export default SmartChart;
