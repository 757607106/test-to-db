/**
 * 数据可视化组件
 * 
 * 支持图表和表格两种视图模式，使用 Recharts 进行图表渲染
 */
import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
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
import { CheckCircle2, BarChart2, Table2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { DataQueryEvent, ChartConfig } from "@/types/stream-events";

interface DataVisualizationProps {
  data: DataQueryEvent;
}

// 图表颜色
const CHART_COLORS = [
  "#3b82f6", // blue-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#06b6d4", // cyan-500
  "#84cc16", // lime-500
];

export function DataVisualization({ data }: DataVisualizationProps) {
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");

  // 获取图表配置，如果没有配置则使用默认值
  const chartConfig = useMemo<ChartConfig>(() => {
    if (data.chart_config) {
      return data.chart_config;
    }
    // 默认配置: 第一列为 X 轴，第二列为 Y 轴
    const columns = data.columns || [];
    return {
      type: "bar",
      xAxis: columns[0] || "x",
      yAxis: columns[1] || "y",
      xDataKey: columns[0] || "x",
      dataKey: columns[1] || "y",
    };
  }, [data]);

  // 获取数值类型的列（用于多数据系列）
  const numericColumns = useMemo(() => {
    if (!data.rows || data.rows.length === 0) return [];
    const firstRow = data.rows[0];
    return data.columns.filter((col) => {
      const value = firstRow[col];
      return typeof value === "number" || !isNaN(Number(value));
    });
  }, [data]);

  // 渲染图表
  const renderChart = () => {
    if (!data.rows || data.rows.length === 0) {
      return (
        <div className="flex items-center justify-center h-[300px] text-muted-foreground">
          暂无数据
        </div>
      );
    }

    const xDataKey = chartConfig.xDataKey || data.columns[0];
    const yDataKeys = numericColumns.filter((col) => col !== xDataKey);
    if (yDataKeys.length === 0 && data.columns.length > 1) {
      yDataKeys.push(data.columns[1]);
    }

    switch (chartConfig.type) {
      case "line":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={xDataKey} tick={{ fontSize: 12 }} stroke="#64748b" />
              <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {yDataKeys.map((key, index) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={CHART_COLORS[index % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case "area":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={xDataKey} tick={{ fontSize: 12 }} stroke="#64748b" />
              <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {yDataKeys.map((key, index) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={CHART_COLORS[index % CHART_COLORS.length]}
                  fill={CHART_COLORS[index % CHART_COLORS.length]}
                  fillOpacity={0.3}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case "pie":
        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data.rows}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={100}
                fill="#8884d8"
                dataKey={chartConfig.dataKey || yDataKeys[0]}
                nameKey={xDataKey}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {data.rows.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case "bar":
      default:
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey={xDataKey} tick={{ fontSize: 12 }} stroke="#64748b" />
              <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                }}
              />
              <Legend />
              {yDataKeys.map((key, index) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={CHART_COLORS[index % CHART_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
    }
  };

  // 渲染表格
  const renderTable = () => {
    if (!data.rows || data.rows.length === 0) {
      return (
        <div className="flex items-center justify-center h-[200px] text-muted-foreground">
          暂无数据
        </div>
      );
    }

    return (
      <div className="overflow-auto max-h-[400px]">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800 sticky top-0">
            <tr>
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-medium text-slate-700 dark:text-slate-300 whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={cn(
                  "border-b border-slate-100 dark:border-slate-800",
                  rowIndex % 2 === 0 ? "bg-white dark:bg-slate-900" : "bg-slate-50/50 dark:bg-slate-800/50"
                )}
              >
                {data.columns.map((col) => (
                  <td
                    key={col}
                    className="px-3 py-2 text-slate-600 dark:text-slate-400 whitespace-nowrap"
                  >
                    {formatCellValue(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="rounded-lg border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
          <span className="font-medium text-slate-700 dark:text-slate-200">
            {data.title || "数据查询"}
          </span>
          <span className="text-muted-foreground text-sm">
            ({data.row_count || data.rows?.length || 0} 条数据)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <BarChart2 className={cn("h-4 w-4", viewMode === "chart" ? "text-blue-500" : "text-slate-400")} />
          <Switch
            checked={viewMode === "table"}
            onCheckedChange={(checked) => setViewMode(checked ? "table" : "chart")}
          />
          <Table2 className={cn("h-4 w-4", viewMode === "table" ? "text-blue-500" : "text-slate-400")} />
        </div>
      </div>

      {/* 内容区 */}
      <div className="p-4">
        {viewMode === "chart" ? renderChart() : renderTable()}
      </div>
    </div>
  );
}

/**
 * 格式化单元格值
 */
function formatCellValue(value: any): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "number") {
    // 格式化数字，保留两位小数
    return value.toLocaleString("zh-CN", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  return String(value);
}
