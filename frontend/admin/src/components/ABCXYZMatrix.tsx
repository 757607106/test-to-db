/**
 * ABC-XYZ 9宫格矩阵热力图组件
 * 可视化展示 ABC 和 XYZ 分类的交叉分布
 */
import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { ABCXYZMatrix as MatrixData } from '../types/inventoryAnalysis';

interface ABCXYZMatrixProps {
  data: MatrixData;
  onCellClick?: (abc: string, xyz: string) => void;
  height?: number | string;
}

/** 9宫格矩阵颜色配置 */
const MATRIX_COLORS: Record<string, string> = {
  'AX': '#16a34a', // 深绿 - 高价值+稳定
  'AY': '#22c55e', // 绿色
  'AZ': '#86efac', // 浅绿
  'BX': '#3b82f6', // 蓝色
  'BY': '#60a5fa', // 浅蓝
  'BZ': '#93c5fd', // 更浅蓝
  'CX': '#f97316', // 橙色
  'CY': '#fb923c', // 浅橙
  'CZ': '#ef4444', // 红色 - 低价值+不稳定
};

/** 分类说明 */
const CLASS_DESCRIPTIONS: Record<string, string> = {
  'AX': '核心产品：高价值+需求稳定，重点管理',
  'AY': '重要产品：高价值+需求波动，需精细预测',
  'AZ': '风险产品：高价值+需求不稳，需特别关注',
  'BX': '中等产品：中价值+需求稳定，常规管理',
  'BY': '中等产品：中价值+需求波动，适度关注',
  'BZ': '低优产品：中价值+需求不稳，降低库存',
  'CX': '长尾产品：低价值+需求稳定，批量采购',
  'CY': '边缘产品：低价值+需求波动，最小库存',
  'CZ': '淘汰候选：低价值+需求不稳，考虑清理',
};

const ABCXYZMatrix: React.FC<ABCXYZMatrixProps> = ({ 
  data, 
  onCellClick,
  height = 350 
}) => {
  // 准备热力图数据
  const heatmapData = useMemo(() => {
    const result: [number, number, number, number, string][] = [];
    
    for (let i = 0; i < 3; i++) { // ABC (rows)
      for (let j = 0; j < 3; j++) { // XYZ (cols)
        const count = data.data[i][j];
        const value = data.values[i][j];
        const abc = data.rows[i];
        const xyz = data.cols[j];
        result.push([j, 2 - i, count, value, `${abc}${xyz}`]);
      }
    }
    
    return result;
  }, [data]);

  // 获取最大值用于颜色映射
  const maxCount = useMemo(() => {
    return Math.max(...data.data.flat(), 1);
  }, [data]);

  // 点击事件处理
  const handleChartClick = useCallback((params: { data?: [number, number, number, number, string] }) => {
    if (params.data && onCellClick) {
      const [x, y] = params.data;
      const abc = data.rows[2 - y];
      const xyz = data.cols[x];
      onCellClick(abc, xyz);
    }
  }, [data, onCellClick]);

  // 图表配置
  const option = useMemo(() => ({
    tooltip: {
      position: 'top',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      formatter: (params: any) => {
        if (!params.data) return '';
        const dataIndex = params.dataIndex;
        const item = heatmapData[dataIndex];
        if (!item) return '';
        const [, , count, value, combined] = item;
        const description = CLASS_DESCRIPTIONS[combined] || '';
        const formattedValue = value >= 1000000 
          ? `${(value / 1000000).toFixed(2)}M` 
          : value >= 1000 
            ? `${(value / 1000).toFixed(1)}K`
            : value.toFixed(0);
        
        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${combined} 类</div>
            <div>产品数量: <b>${count}</b></div>
            <div>总价值: <b>${formattedValue}</b></div>
            <div style="margin-top: 8px; font-size: 12px; color: #666;">
              ${description}
            </div>
          </div>
        `;
      },
    },
    grid: {
      top: 40,
      left: 80,
      right: 20,
      bottom: 60,
    },
    xAxis: {
      type: 'category',
      data: ['X (稳定)', 'Y (波动)', 'Z (不稳)'],
      splitArea: { show: true },
      axisLabel: { fontWeight: 'bold' },
      name: 'XYZ分类 (需求稳定性)',
      nameLocation: 'center',
      nameGap: 35,
    },
    yAxis: {
      type: 'category',
      data: ['C (低值)', 'B (中值)', 'A (高值)'],
      splitArea: { show: true },
      axisLabel: { fontWeight: 'bold' },
      name: 'ABC分类 (价值)',
      nameLocation: 'center',
      nameGap: 55,
    },
    visualMap: {
      show: false,
      min: 0,
      max: maxCount,
      inRange: {
        color: ['#f0fdf4', '#16a34a'],
      },
    },
    series: [{
      name: 'ABC-XYZ 矩阵',
      type: 'heatmap',
      data: heatmapData.map(item => ({
        value: [item[0], item[1], item[2]],
        itemStyle: {
          color: MATRIX_COLORS[item[4]] || '#ccc',
          opacity: Math.max(0.3, item[2] / maxCount),
        },
      })),
      label: {
        show: true,
        formatter: (params: { value?: [number, number, number] }) => {
          if (!params.value) return '';
          const count = params.value[2];
          return count.toString();
        },
        fontSize: 16,
        fontWeight: 'bold',
        color: '#fff',
        textShadowColor: 'rgba(0,0,0,0.3)',
        textShadowBlur: 2,
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
    }],
  }), [heatmapData, maxCount]);

  // 事件配置
  const onEvents = useMemo(() => ({
    click: handleChartClick,
  }), [handleChartClick]);

  return (
    <div>
      <div style={{ 
        marginBottom: 8, 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <span style={{ fontWeight: 'bold' }}>ABC-XYZ 分类矩阵</span>
        <div style={{ display: 'flex', gap: 8, fontSize: 12 }}>
          <span style={{ color: '#16a34a' }}>■ 重点关注</span>
          <span style={{ color: '#3b82f6' }}>■ 适度管理</span>
          <span style={{ color: '#ef4444' }}>■ 优化清理</span>
        </div>
      </div>
      <ReactECharts
        option={option}
        style={{ height }}
        onEvents={onEvents}
      />
    </div>
  );
};

export default ABCXYZMatrix;
