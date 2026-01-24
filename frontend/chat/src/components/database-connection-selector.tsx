
"use client";

import React, { useState, useEffect } from 'react';
import { Database, ChevronDown } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getConnections, type DBConnection } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DatabaseConnectionSelectorProps {
  value?: number | null;
  onChange: (connectionId: number | null) => void;
  className?: string;
  // 新增: 加载完成后回调，通知父组件连接数量
  onLoaded?: (count: number) => void;
}

export function DatabaseConnectionSelector({
  value,
  onChange,
  className,
  onLoaded
}: DatabaseConnectionSelectorProps) {
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSelected, setAutoSelected] = useState(false);

  useEffect(() => {
    fetchConnections();
  }, []);

  // 新增: 当只有一个数据库连接时自动选择
  useEffect(() => {
    if (!autoSelected && connections.length === 1 && !value) {
      const singleConnection = connections[0];
      onChange(singleConnection.id);
      setAutoSelected(true);
      console.log(`自动选择唯一的数据库连接: ${singleConnection.name} (ID: ${singleConnection.id})`);
    }
  }, [connections, value, onChange, autoSelected]);

  const fetchConnections = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getConnections();
      const data = response.data || [];
      setConnections(data);
      // 通知父组件连接数量
      onLoaded?.(data.length);
    } catch (err) {
      console.error('获取数据库连接失败:', err);
      setError('获取数据库连接失败');
      setConnections([]);
      onLoaded?.(0);
    } finally {
      setLoading(false);
    }
  };

  const handleValueChange = (stringValue: string) => {
    if (stringValue === "none") {
      onChange(null);
    } else {
      const connectionId = parseInt(stringValue, 10);
      onChange(connectionId);
    }
  };

  const currentValue = value ? value.toString() : "none";
  const selectedConnection = connections.find(conn => conn.id === value);

  return (
    <div className={cn("flex items-center", className)}>
      <Select value={currentValue} onValueChange={handleValueChange}>
        <SelectTrigger className="h-8 border-0 bg-transparent shadow-none focus:ring-0 focus:ring-offset-0 text-sm text-gray-600 hover:text-gray-800 transition-colors p-0 gap-1 min-w-0">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-gray-600 flex-shrink-0" />
            <SelectValue
              placeholder={loading ? "加载中..." : "选择数据库"}
              className="text-sm"
            >
              {selectedConnection ? (
                <span className="truncate max-w-[120px]">
                  {selectedConnection.name}
                </span>
              ) : (
                <span className="text-gray-600">选择数据库</span>
              )}
            </SelectValue>
          </div>
        </SelectTrigger>
        <SelectContent className="min-w-[240px]">
          <SelectItem value="none">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-gray-300"></div>
              <span className="text-gray-500">未选择数据库</span>
            </div>
          </SelectItem>
          {error ? (
            <SelectItem value="error" disabled>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-400"></div>
                <span className="text-red-500">{error}</span>
              </div>
            </SelectItem>
          ) : (
            connections.map((connection) => (
              <SelectItem key={connection.id} value={connection.id.toString()}>
                <div className="flex items-center gap-2 w-full">
                  <div className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0"></div>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="font-medium text-gray-900 truncate">
                      {connection.name}
                    </span>
                    <span className="text-xs text-gray-500 truncate">
                      {connection.db_type} • {connection.host}:{connection.port}
                    </span>
                  </div>
                </div>
              </SelectItem>
            ))
          )}
        </SelectContent>
      </Select>
    </div>
  );
}
