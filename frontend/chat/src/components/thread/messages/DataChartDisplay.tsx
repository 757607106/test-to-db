/**
 * 数据图表展示组件（独立于流水线，在回答后展示）
 * 
 * 智能匹配合适的图表类型，支持最多5种图表
 */
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart2,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  Table2,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { QueryContext } from "@/types/stream-events";

// 图表颜色配置
const CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

interface DataChartDisplayProps {
  dataQuery: QueryContext["dataQuery"];
}

export function DataChartDisplay({ dataQuery }: DataChartDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [selectedChartIndex, setSelectedChartIndex] = useState(0);

  if (!dataQuery || !dataQuery.chart_config) return null;

  const { columns, rows, chart_config } = dataQuery;
  const hasData = rows && rows.length > 0;

  if (!hasData) return null;

  // 转换数据格式
  const tableData = rows.map(row => {
    if (Array.isArray(row)) {
      const obj: Record<string, any> = {};
      columns.forEach((col, i) => {
        obj[col] = row[i];
      });
      return obj;
    }
    return row;
  });

  // 生成多个图表配置（最多5个）
  const chartConfigs = generateChartConfigs(tableData, columns, chart_config);

  return (
    <div className="mt-4 rounded-xl border border-blue-200 bg-gradient-to-b from-blue-50/50 to-white overflow-hidden shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-blue-50/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-blue-100 to-indigo-100 shadow-sm">
            <BarChart2 className="h-4 w-4 text-blue-600" />
          </div>
          <div className="flex flex-col items-start">
            <span className="font-semibold text-sm text-blue-800">数据可视化</span>
            <span className="text-xs text-blue-500">{chartConfigs.length} 个图表</span>
          </div>
        </div>

        <motion.div
          animate={{ rotate: isExpanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-4 w-4 text-blue-500" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="p-4 space-y-4">
              {/* 图表选择器 */}
              {chartConfigs.length > 1 && (
                <div className="flex items-center gap-2 overflow-x-auto pb-2">
                  {chartConfigs.map((config, index) => (
                    <button
                      key={index}
                      onClick={() => setSelectedChartIndex(index)}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                        selectedChartIndex === index
                          ? "bg-blue-600 text-white shadow-md"
                          : "bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:bg-blue-50"
                      )}
                    >
                      {getChartIcon(config.type)}
                      <span>{config.label}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* 图表显示区域 */}
              <div className="bg-white rounded-lg border border-slate-200 p-4">
                <ChartRenderer
                  data={tableData}
                  config={chartConfigs[selectedChartIndex]}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 生成多个图表配置
function generateChartConfigs(
  data: Record<string, any>[],
  columns: string[],
  baseConfig: any
): ChartConfig[] {
  const configs: ChartConfig[] = [];
  
  // 分析列类型
  const numericColumns = columns.filter(col => 
    data.every(row => typeof row[col] === "number" || row[col] === null)
  );
  
  const categoryColumns = columns.filter(col => 
    !numericColumns.includes(col)
  );

  const xCol = categoryColumns[0] || columns[0];
  const yColumns = numericColumns.slice(0, 3);

  // 1. 柱状图
  if (yColumns.length > 0) {
    configs.push({
      type: "bar",
      label: "柱状图",
      xDataKey: xCol,
      yDataKeys: yColumns,
    });
  }

  // 2. 折线图
  if (yColumns.length > 0 && data.length > 2) {
    configs.push({
      type: "line",
      label: "折线图",
      xDataKey: xCol,
      yDataKeys: yColumns,
    });
  }

  // 3. 饼图（仅当只有一个数值列时）
  if (yColumns.length === 1 && data.length <= 10) {
    configs.push({
      type: "pie",
      label: "饼图",
      xDataKey: xCol,
      yDataKeys: [yColumns[0]],
    });
  }

  return configs.slice(0, 5); // 最多5个
}

// 图表配置类型
interface ChartConfig {
  type: "bar" | "line" | "pie";
  label: string;
  xDataKey: string;
  yDataKeys: string[];
}

// 图表渲染器
function ChartRenderer({ data, config }: { data: Record<string, any>[]; config: ChartConfig }) {
  if (config.type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            dataKey={config.yDataKeys[0]}
            nameKey={config.xDataKey}
            cx="50%"
            cy="50%"
            outerRadius={100}
            label
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  const ChartComponent = config.type === "line" ? LineChart : BarChart;
  const DataComponent = config.type === "line" ? Line : Bar;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ChartComponent data={data} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey={config.xDataKey}
          tick={{ fontSize: 11, fill: "#64748b" }}
          stroke="#cbd5e1"
          tickLine={{ stroke: "#cbd5e1" }}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#64748b" }}
          stroke="#cbd5e1"
          tickLine={{ stroke: "#cbd5e1" }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#fff",
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            fontSize: "12px",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
        {config.yDataKeys.map((key, index) =>
          config.type === "line" ? (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[index % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4, fill: "#fff", strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
          ) : (
            <Bar
              key={key}
              dataKey={key}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              radius={[4, 4, 0, 0]}
            />
          )
        )}
      </ChartComponent>
    </ResponsiveContainer>
  );
}

// 获取图表图标
function getChartIcon(type: string) {
  switch (type) {
    case "line":
      return <LineChartIcon className="h-3.5 w-3.5" />;
    case "pie":
      return <PieChartIcon className="h-3.5 w-3.5" />;
    default:
      return <BarChart2 className="h-3.5 w-3.5" />;
  }
}
