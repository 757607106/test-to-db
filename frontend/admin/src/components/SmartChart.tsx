/**
 * SmartChart 组件
 * 根据数据自动选择合适的ECharts图表类型进行渲染，支持自动降级为表格
 */
import React, { useMemo, useRef, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { Table, Empty, Alert, Button, Modal } from 'antd';
import { BugOutlined } from '@ant-design/icons';

interface SmartChartProps {
  data: any;
  title?: string;
  height?: number;
  chartType?: string;  // 可选的手动指定图表类型
  debug?: boolean; // 开启调试模式
}

// 分析数据结构，判断最适合的图表类型
type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'area' | 'heatmap' | 'radar' | 'funnel' | 'table';

// 数据标准化结果
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
  // 格式3: 直接是数组 [{...}, {...}]
  else if (Array.isArray(data)) {
    rows = data;
    columns = rows[0] ? Object.keys(rows[0]) : [];
  }
  // 格式4: 可能是 { result: [...] } 或其他嵌套
  else if (data.result && Array.isArray(data.result)) {
     rows = data.result;
     columns = rows[0] ? Object.keys(rows[0]) : [];
  }

  return { rows, columns };
}

function analyzeDataAndGetChartType(data: any): {
  chartType: ChartType;
  xAxisData: string[];
  seriesData: { name: string; data: number[] }[];
  pieData: { name: string; value: number }[];
  normalizedData: NormalizedData;
} {
  // 默认返回值
  const result: {
    chartType: ChartType;
    xAxisData: string[];
    seriesData: { name: string; data: number[] }[];
    pieData: { name: string; value: number }[];
    normalizedData: NormalizedData;
  } = {
    chartType: 'table', // 默认为 table，如果无法生成图表则回退
    xAxisData: [],
    seriesData: [],
    pieData: [],
    normalizedData: { rows: [], columns: [] }
  };

  const { rows, columns } = normalizeData(data);
  result.normalizedData = { rows, columns };

  if (rows.length === 0 || columns.length === 0) {
    return result;
  }

  // 分析列类型
  const numericColumns: string[] = [];
  const stringColumns: string[] = [];
  const dateColumns: string[] = [];

  columns.forEach((col) => {
    // 过滤掉 null/undefined，取前10行采样
    const sampleValues = rows.slice(0, 10).map((row) => row[col]).filter((v) => v !== null && v !== undefined);
    
    if (sampleValues.length === 0) return;

    // 检查是否是数值类型
    if (sampleValues.every((v) => typeof v === 'number' || (!isNaN(Number(v)) && v !== ''))) {
      numericColumns.push(col);
    }
    // 检查是否是日期类型 (增强的日期检测)
    else if (sampleValues.every((v) => {
        const str = String(v);
        // 常见日期格式正则
        if (/^\d{4}[-/]\d{2}[-/]\d{2}/.test(str)) return true;
        // 尝试 Date.parse
        const date = new Date(str);
        return !isNaN(date.getTime()) && str.length > 4; // 长度>4避免纯数字被当做日期
    }) || /date|time|日期|时间/i.test(col)) {
      dateColumns.push(col);
    }
    else {
      stringColumns.push(col);
    }
  });

  // 决定图表类型
  
  // 1. 饼图: 只有一个数值列 + 一个分类列 + 数据行数少
  if (numericColumns.length === 1 && stringColumns.length === 1 && rows.length <= 20) {
    result.chartType = 'pie';
    const labelCol = stringColumns[0];
    const valueCol = numericColumns[0];
    result.pieData = rows.map((row) => ({
      name: String(row[labelCol] || ''),
      value: Number(row[valueCol]) || 0,
    }));
    return result;
  }

  // 2. 折线图: 有日期列 + 数值列
  if (dateColumns.length > 0 && numericColumns.length > 0) {
    result.chartType = 'line';
    const xCol = dateColumns[0];
    // 按日期排序
    const sortedRows = [...rows].sort((a, b) => new Date(a[xCol]).getTime() - new Date(b[xCol]).getTime());
    
    result.xAxisData = sortedRows.map((row) => String(row[xCol] || ''));
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: sortedRows.map((row) => Number(row[col]) || 0),
    }));
    return result;
  }

  // 3. 柱状图: 有分类列 + 数值列
  if (stringColumns.length > 0 && numericColumns.length > 0) {
    result.chartType = 'bar';
    const xCol = stringColumns[0];
    // 如果数据太多，只取前20条，避免柱状图太挤
    const displayRows = rows.length > 50 ? rows.slice(0, 50) : rows;
    
    result.xAxisData = displayRows.map((row) => String(row[xCol] || ''));
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: displayRows.map((row) => Number(row[col]) || 0),
    }));
    return result;
  }

  // 4. 散点图: 两个以上数值列
  if (numericColumns.length >= 2) {
    result.chartType = 'scatter';
    result.seriesData = [{
      name: `${numericColumns[0]} vs ${numericColumns[1]}`,
      data: rows.map((row) => [Number(row[numericColumns[0]]) || 0, Number(row[numericColumns[1]]) || 0]) as any,
    }];
    return result;
  }

  // 5. 默认柱状图 (如果没有分类列，用行号)
  if (numericColumns.length > 0) {
    result.chartType = 'bar';
    result.xAxisData = rows.map((_, i) => `数据${i + 1}`);
    result.seriesData = numericColumns.map((col) => ({
      name: col,
      data: rows.map((row) => Number(row[col]) || 0),
    }));
    return result;
  }

  // 如果没有数值列，只能返回 table
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
        legend: { orient: 'vertical', left: 'left', top: 'middle', type: 'scroll' },
        series: [{
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
          label: { show: true, formatter: '{b}: {d}%' },
          emphasis: {
            label: { show: true, fontSize: 16, fontWeight: 'bold' },
          },
          data: pieData,
        }],
      };

    case 'line':
      return {
        ...baseOption,
        legend: { data: seriesData.map((s) => s.name), bottom: 0, type: 'scroll' },
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
        legend: { data: seriesData.map((s) => s.name), bottom: 0, type: 'scroll' },
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
      const indicators = xAxisData.map(name => ({ name, max: Math.max(...seriesData.flatMap(s => s.data)) || 100 }));
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
      return {
        ...baseOption,
        legend: { bottom: 0, type: 'scroll' },
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
          data: pieData.length > 0 ? pieData : seriesData[0]?.data.map((val, idx) => ({
            value: val,
            name: xAxisData[idx] || `项目${idx + 1}`,
          })) || [],
        }],
      };

    case 'heatmap':
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
          min: Math.min(...heatmapData.map(d => d[2])) || 0,
          max: Math.max(...heatmapData.map(d => d[2])) || 100,
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
        }],
      };

    case 'bar':
    default:
      return {
        ...baseOption,
        legend: seriesData.length > 1 ? { data: seriesData.map((s) => s.name), bottom: 0, type: 'scroll' } : undefined,
        xAxis: { 
          type: 'category', 
          data: xAxisData, 
          axisLabel: { 
            interval: 0, 
            rotate: xAxisData.length > 8 ? 30 : 0,
            hideOverlap: true
          } 
        },
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

export const SmartChart: React.FC<SmartChartProps> = ({ data, title, height = 350, chartType: manualChartType, debug = false }) => {
  const chartRef = useRef<ReactECharts>(null);
  const [debugVisible, setDebugVisible] = React.useState(false);

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
        console.debug('Chart cleanup:', error);
      }
    };
  }, []);

  const { chartOption, normalizedData, error } = useMemo(() => {
    // 数据验证
    if (!data) return { chartOption: null, normalizedData: { rows: [], columns: [] }, error: null };
    
    // 检查后端返回的错误
    if (data.error) {
        return { chartOption: null, normalizedData: { rows: [], columns: [] }, error: data.error };
    }
    
    try {
      let finalChartType: ChartType;
      let xAxisData: string[];
      let seriesData: { name: string; data: number[] }[];
      let pieData: { name: string; value: number }[];
      let analyzedData: {
        chartType: ChartType;
        xAxisData: string[];
        seriesData: { name: string; data: number[] }[];
        pieData: { name: string; value: number }[];
        normalizedData: NormalizedData;
      };

      // 分析数据
      analyzedData = analyzeDataAndGetChartType(data);

      if (manualChartType) {
        finalChartType = manualChartType as ChartType;
        
        // 尝试复用分析结果
        if (manualChartType === 'pie' && analyzedData.pieData.length === 0) {
          // 强制转换
          if (analyzedData.seriesData.length > 0 && analyzedData.xAxisData.length > 0) {
            pieData = analyzedData.xAxisData.map((name, idx) => ({
              name: name,
              value: analyzedData.seriesData[0].data[idx] || 0
            }));
          } else {
            pieData = analyzedData.pieData;
          }
        } else {
          pieData = analyzedData.pieData;
        }
        xAxisData = analyzedData.xAxisData;
        seriesData = analyzedData.seriesData;
      } else {
        finalChartType = analyzedData.chartType;
        xAxisData = analyzedData.xAxisData;
        seriesData = analyzedData.seriesData;
        pieData = analyzedData.pieData;
      }

      // 如果分析结果是 table 或数据不足，返回空 option 但保留 normalizedData 用于渲染表格
      if (finalChartType === 'table') {
          return { chartOption: null, normalizedData: analyzedData.normalizedData, error: null };
      }
      
      if (finalChartType === 'pie' && pieData.length === 0) {
          return { chartOption: null, normalizedData: analyzedData.normalizedData, error: null };
      }
      if (finalChartType !== 'pie' && seriesData.length === 0) {
          return { chartOption: null, normalizedData: analyzedData.normalizedData, error: null };
      }

      const option = generateChartOption(finalChartType, xAxisData, seriesData, pieData, title);
      return { chartOption: option, normalizedData: analyzedData.normalizedData, error: null };

    } catch (error) {
      console.error('图表配置生成失败:', error);
      // 出错时尝试返回标准化数据以显示表格
      const normData = normalizeData(data);
      return { chartOption: null, normalizedData: normData, error: String(error) };
    }
  }, [data, title, manualChartType]);

  const renderDebugInfo = () => (
      <div style={{ position: 'absolute', right: 0, top: 0, zIndex: 10 }}>
          <Button 
            type="text" 
            size="small" 
            icon={<BugOutlined />} 
            onClick={() => setDebugVisible(true)}
            style={{ opacity: 0.3 }}
          />
          <Modal
            title="数据调试"
            open={debugVisible}
            onCancel={() => setDebugVisible(false)}
            footer={null}
            width={800}
          >
              <pre style={{ maxHeight: '600px', overflow: 'auto', background: '#f5f5f5', padding: 10 }}>
                  {JSON.stringify(data, null, 2)}
              </pre>
          </Modal>
      </div>
  );

  if (error) {
      return (
          <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
              <Alert
                  message="数据加载失败"
                  description={error}
                  type="error"
                  showIcon
              />
              {renderDebugInfo()}
          </div>
      );
  }

  if (!chartOption) {
    // 降级渲染为表格
    if (normalizedData.rows.length > 0 && normalizedData.columns.length > 0) {
        const columns = normalizedData.columns.map(col => ({
            title: col,
            dataIndex: col,
            key: col,
            render: (text: any) => <span title={String(text)}>{String(text)}</span>
        }));
        
        return (
            <div style={{ height, display: 'flex', flexDirection: 'column', position: 'relative' }}>
                {title && <div style={{ textAlign: 'center', marginBottom: 10, fontWeight: 'bold' }}>{title}</div>}
                <Table 
                    dataSource={normalizedData.rows.map((r, i) => ({ ...r, key: i }))} 
                    columns={columns} 
                    pagination={{ pageSize: 5, size: 'small' }} 
                    size="small" 
                    scroll={{ y: height - 100 }}
                    style={{ flex: 1, overflow: 'hidden' }}
                />
                {renderDebugInfo()}
            </div>
        );
    }

    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
        {renderDebugInfo()}
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
        <ReactECharts
        ref={chartRef}
        option={chartOption}
        style={{ height, width: '100%' }}
        opts={{ renderer: 'svg', locale: 'ZH' }}
        notMerge={true}
        lazyUpdate={true}
        />
        {renderDebugInfo()}
    </div>
  );
};

export default SmartChart;
