/**
 * 帕累托图组件
 * 柱状图 + 累计折线图，展示 ABC 分类的帕累托分布
 */
import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { ParetoData } from '../types/inventoryAnalysis';

interface ParetoChartProps {
  data: ParetoData;
  maxItems?: number;
  height?: number | string;
  onBarClick?: (productId: string) => void;
}

/** ABC 分类颜色 */
const ABC_COLORS: Record<string, string> = {
  'A': '#52c41a',
  'B': '#1890ff',
  'C': '#ff4d4f',
};

const ParetoChart: React.FC<ParetoChartProps> = ({
  data,
  maxItems = 30,
  height = 350,
  onBarClick,
}) => {
  // 截取显示数量
  const displayData = useMemo(() => ({
    labels: data.labels.slice(0, maxItems),
    values: data.values.slice(0, maxItems),
    cumulative_pct: data.cumulative_pct.slice(0, maxItems),
    abc_class: data.abc_class.slice(0, maxItems),
  }), [data, maxItems]);

  // 格式化数值
  const formatValue = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(0)}K`;
    }
    return value.toFixed(0);
  };

  // 图表配置
  const option = useMemo(() => ({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#999',
        },
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (params: any[]) => {
        if (!params || params.length === 0) return '';
        const index = params[0].dataIndex;
        const label = displayData.labels[index];
        const value = displayData.values[index];
        const cumPct = displayData.cumulative_pct[index];
        const abcClass = displayData.abc_class[index];
        
        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${label}</div>
            <div>价值: <b>${formatValue(value)}</b></div>
            <div>累计占比: <b>${(cumPct * 100).toFixed(1)}%</b></div>
            <div>分类: <span style="color: ${ABC_COLORS[abcClass]}; font-weight: bold;">${abcClass}类</span></div>
          </div>
        `;
      },
    },
    legend: {
      data: ['价值', '累计占比'],
      top: 0,
    },
    grid: {
      top: 50,
      left: 60,
      right: 60,
      bottom: 80,
    },
    xAxis: {
      type: 'category',
      data: displayData.labels,
      axisLabel: {
        rotate: 45,
        interval: 0,
        formatter: (value: string) => {
          return value.length > 8 ? value.slice(0, 8) + '...' : value;
        },
      },
      axisPointer: {
        type: 'shadow',
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '价值',
        nameTextStyle: { padding: [0, 40, 0, 0] },
        axisLabel: {
          formatter: (value: number) => formatValue(value),
        },
      },
      {
        type: 'value',
        name: '累计%',
        max: 100,
        axisLabel: {
          formatter: '{value}%',
        },
      },
    ],
    series: [
      {
        name: '价值',
        type: 'bar',
        data: displayData.values.map((value, index) => ({
          value,
          itemStyle: {
            color: ABC_COLORS[displayData.abc_class[index]] || '#999',
          },
        })),
        barMaxWidth: 40,
      },
      {
        name: '累计占比',
        type: 'line',
        yAxisIndex: 1,
        data: displayData.cumulative_pct.map(v => (v * 100).toFixed(1)),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          color: '#722ed1',
          width: 2,
        },
        itemStyle: {
          color: '#722ed1',
        },
        markLine: {
          silent: true,
          lineStyle: {
            type: 'dashed',
          },
          data: [
            {
              yAxis: 70,
              label: {
                formatter: 'A类分界 (70%)',
                position: 'end',
              },
              lineStyle: {
                color: '#52c41a',
              },
            },
            {
              yAxis: 90,
              label: {
                formatter: 'B类分界 (90%)',
                position: 'end',
              },
              lineStyle: {
                color: '#1890ff',
              },
            },
          ],
        },
      },
    ],
  }), [displayData]);

  // 点击事件
  const onEvents = useMemo(() => ({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    click: (params: any) => {
      if (params.seriesType === 'bar' && onBarClick) {
        const productId = displayData.labels[params.dataIndex];
        onBarClick(productId);
      }
    },
  }), [displayData, onBarClick]);

  return (
    <div>
      <div style={{ 
        marginBottom: 8, 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <span style={{ fontWeight: 'bold' }}>帕累托分析图</span>
        <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
          <span><span style={{ color: '#52c41a' }}>●</span> A类 (0-70%)</span>
          <span><span style={{ color: '#1890ff' }}>●</span> B类 (70-90%)</span>
          <span><span style={{ color: '#ff4d4f' }}>●</span> C类 (90-100%)</span>
        </div>
      </div>
      <ReactECharts
        option={option}
        style={{ height }}
        onEvents={onEvents}
      />
      {data.labels.length > maxItems && (
        <div style={{ textAlign: 'center', color: '#999', fontSize: 12, marginTop: 4 }}>
          显示前 {maxItems} 个产品，共 {data.labels.length} 个
        </div>
      )}
    </div>
  );
};

export default ParetoChart;
