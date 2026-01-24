
import React, { useMemo } from "react";
import { Table2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QueryContext } from "@/types/stream-events";
import { transformQueryData } from "../utils";

// 格式化单元格值
function formatValue(value: any): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return value.toLocaleString("zh-CN", { 
      minimumFractionDigits: 0, 
      maximumFractionDigits: 2 
    });
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

// 数据表格
export const DataTable = React.memo(function DataTable({ data, columns }: { data: Record<string, any>[]; columns: string[] }) {
  return (
    <div className="overflow-auto max-h-80 rounded-lg border border-slate-200">
      <table className="w-full text-sm">
        <thead className="bg-gradient-to-b from-slate-50 to-slate-100 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th 
                key={col} 
                className="px-4 py-3 text-left font-semibold text-slate-600 whitespace-nowrap border-b border-slate-200"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.slice(0, 50).map((row, i) => (
            <tr 
              key={i} 
              className={cn(
                "transition-colors",
                i % 2 === 0 ? "bg-white" : "bg-slate-50/50",
                "hover:bg-blue-50/50"
              )}
            >
              {columns.map((col) => (
                <td 
                  key={col} 
                  className="px-4 py-2.5 text-slate-600 whitespace-nowrap"
                >
                  {formatValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 50 && (
        <div className="text-center text-xs text-slate-500 py-2 bg-slate-50 border-t border-slate-200">
          显示前 50 条，共 {data.length} 条数据
        </div>
      )}
    </div>
  );
});

// 数据查询结果组件 - 只显示表格
export const DataQueryResult = React.memo(function DataQueryResult({ 
  dataQuery, 
}: { 
  dataQuery: QueryContext["dataQuery"]; 
}) {
  // 使用统一的数据转换函数
  const tableData = useMemo(() => {
    if (!dataQuery?.rows || !dataQuery?.columns) return [];
    return transformQueryData(dataQuery.columns, dataQuery.rows);
  }, [dataQuery?.rows, dataQuery?.columns]);

  if (!dataQuery) return null;

  const { columns, rows, row_count } = dataQuery;
  const hasData = rows && rows.length > 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Table2 className="h-4 w-4 text-blue-600" />
          <span className="font-medium text-sm text-slate-700">查询结果</span>
          <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
            {row_count || rows?.length || 0} 条记录
          </span>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="p-4">
        {!hasData ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-500">
            <AlertCircle className="h-8 w-8 mb-2 text-slate-400" />
            <span className="text-sm">查询结果为空</span>
          </div>
        ) : (
          <DataTable data={tableData} columns={columns} />
        )}
      </div>
    </div>
  );
});
