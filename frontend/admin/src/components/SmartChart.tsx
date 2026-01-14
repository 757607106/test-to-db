/**
 * SmartChart 组件
 * 根据数据自动选择合适的ECharts图表类型进行渲染
 */
import React, { useMemo, useRef, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface SmartChartProps {
  data: any;
  title?: string;
  height?: number;
  chartType?: string;  // 可选的手动指定图表类型
}

// 分析数据结构，判断最适合的图表类型
type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'heatmap' | 'radar' | 'funnel' | 'table';

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
    tooltip: { trigger: chartType === 'pie' ? 'item' : (chartType === 'radar' ? 'item' : 'axis') },
    toolbox: {
      feature: {
        saveAsImage: { title: '保存' },
        ...(!['pie', 'radar', 'funnel'].includes(chartType) && {
          dataZoom: { title: { zoom: '缩放', back: '还原' } }
        }),
      },
      right: 10,
    },
    grid: !['pie', 'radar', 'funnel'].includes(chartType) ? { left: '3%', right: '4%', bottom: '3%', containLabel: true } : undefined,
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
        })),
      };

    case 'area':
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
          areaStyle: { opacity: 0.5 },
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

    case 'radar':
      // 雷达图需要特殊处理数据
      const indicators = xAxisData.map(name => ({ name, max: Math.max(...seriesData.flatMap(s => s.data)) }));
      return {
        ...baseOption,
        legend: { data: seriesData.map((s) => s.name), bottom: 0 },
        radar: {
          indicator: indicators,
        },
        series: [{
          type: 'radar',
          data: seriesData.map((s) => ({
            value: s.data,
            name: s.name,
          })),
        }],
      };

    case 'funnel':
      // 漏斗图使用pieData
      return {
        ...baseOption,
        legend: { bottom: 0 },
        series: [{
          type: 'funnel',
          left: '10%',
          top: 60,
          bottom: 60,
          width: '80%',
          min: 0,
          max: 100,
          minSize: '0%',
          maxSize: '100%',
          sort: 'descending',
          gap: 2,
          label: {
            show: true,
            position: 'inside',
          },
          labelLine: {
            length: 10,
            lineStyle: {
              width: 1,
              type: 'solid',
            },
          },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 1,
          },
          emphasis: {
            label: {
              fontSize: 20,
            },
          },
          data: pieData.length > 0 ? pieData : seriesData[0]?.data.map((val, idx) => ({
            value: val,
            name: xAxisData[idx] || `项目${idx + 1}`,
          })) || [],
        }],
      };

    case 'heatmap':
      // 热力图需要特殊的数据格式 [x, y, value]
      const heatmapData: any[] = [];
      seriesData.forEach((series, seriesIdx) => {
        series.data.forEach((value, dataIdx) => {
          heatmapData.push([dataIdx, seriesIdx, value]);
        });
      });
      return {
        ...baseOption,
        xAxis: {
          type: 'category',
          data: xAxisData,
          splitArea: { show: true },
        },
        yAxis: {
          type: 'category',
          data: seriesData.map(s => s.name),
          splitArea: { show: true },
        },
        visualMap: {
          min: Math.min(...heatmapData.map(d => d[2])),
          max: Math.max(...heatmapData.map(d => d[2])),
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: '0%',
        },
        series: [{
          type: 'heatmap',
          data: heatmapData,
          label: {
            show: true,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        }],
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

export const SmartChart: React.FC<SmartChartProps> = ({ data, title, height = 350, chartType: manualChartType }) => {
  const chartRef = useRef<ReactECharts>(null);

  // 清理函数，确保组件卸载时正常清理 ECharts 实例
  useEffect(() => {
    return () => {
      try {
        if (chartRef.current) {
          const echartInstance = chartRef.current.getEchartsInstance();
          if (echartInstance && !echartInstance.isDisposed()) {
            echartInstance.dispose();
          }
        }
      } catch (error) {
        // 静默处理清理错误
        console.debug('Chart cleanup:', error);
      }
    };
  }, []);

  const chartOption = useMemo(() => {
    // 数据验证
    if (!data) return null;
    
    try {

    // 如果手动指定了图表类型,使用指定的类型;否则自动分析
    let finalChartType: ChartType;
    let xAxisData: string[];
    let seriesData: { name: string; data: number[] }[];
    let pieData: { name: string; value: number }[];

    if (manualChartType) {
      // 使用手动指定的图表类型,但仍需要分析数据结构
      const analyzed = analyzeDataAndGetChartType(data);
      finalChartType = manualChartType as ChartType;
      
      // 如果指定的是饼图但数据不适合，使用分析出的类型数据
      // 但仍尝试用指定的类型渲染（如果有数据的话）
      if (manualChartType === 'pie' && analyzed.pieData.length === 0) {
        // 饼图数据为空，但可能有其他类型的数据，尝试使用柱状图数据作为饼图
        if (analyzed.seriesData.length > 0 && analyzed.xAxisData.length > 0) {
          // 使用第一个系列的数据转换为饼图数据
          pieData = analyzed.xAxisData.map((name, idx) => ({
            name: name,
            value: analyzed.seriesData[0].data[idx] || 0
          }));
        } else {
          pieData = analyzed.pieData;
        }
        xAxisData = analyzed.xAxisData;
        seriesData = analyzed.seriesData;
      } else {
        xAxisData = analyzed.xAxisData;
        seriesData = analyzed.seriesData;
        pieData = analyzed.pieData;
      }
    } else {
      // 自动分析
      const analyzed = analyzeDataAndGetChartType(data);
      finalChartType = analyzed.chartType;
      xAxisData = analyzed.xAxisData;
      seriesData = analyzed.seriesData;
      pieData = analyzed.pieData;
    }

    // 数据不足以生成图表
    if (finalChartType === 'pie' && pieData.length === 0) return null;
    if (finalChartType !== 'pie' && seriesData.length === 0) return null;

    return generateChartOption(finalChartType, xAxisData, seriesData, pieData, title);
    } catch (error) {
      console.error('图表配置生成失败:', error);
      return null;
    }
  }, [data, title, manualChartType]);

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
      ref={chartRef}
      option={chartOption}
      style={{ height, width: '100%' }}
      opts={{ renderer: 'svg', locale: 'ZH' }}
      notMerge={true}
      lazyUpdate={true}
    />
  );
};

export default SmartChart;
