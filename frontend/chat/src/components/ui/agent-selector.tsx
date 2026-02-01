"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Bot } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getAgentProfiles, type AgentProfile } from '@/lib/api';
import { cn } from '@/lib/utils';

interface AgentSelectorProps {
  value?: number | null;
  onChange: (agentId: number | null) => void;
  className?: string;
  // 新增: 加载完成后回调，通知父组件智能体数量
  onLoaded?: (count: number) => void;
}

export function AgentSelector({
  value,
  onChange,
  className,
  onLoaded
}: AgentSelectorProps) {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSelected, setAutoSelected] = useState(false);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 传递 is_system=false 参数，只显示自定义智能体
      const response = await getAgentProfiles({ is_system: false });
      // Only show active agents
      const activeAgents = Array.isArray(response.data) 
        ? response.data.filter(a => a.is_active) 
        : [];
      setAgents(activeAgents);
      // 通知父组件智能体数量
      onLoaded?.(activeAgents.length);
    } catch (err) {
      console.error('获取智能体失败:', err);
      setError('获取智能体失败');
      setAgents([]);
      onLoaded?.(0);
    } finally {
      setLoading(false);
    }
  }, [onLoaded]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // 新增: 当只有一个自定义智能体时自动选择
  useEffect(() => {
    if (!autoSelected && agents.length === 1 && !value) {
      const singleAgent = agents[0];
      onChange(singleAgent.id);
      setAutoSelected(true);
      console.log(`自动选择唯一的智能体: ${singleAgent.name} (ID: ${singleAgent.id})`);
    }
  }, [agents, value, onChange, autoSelected]);

  const handleValueChange = (stringValue: string) => {
    if (stringValue === "none") {
      onChange(null);
    } else {
      const agentId = parseInt(stringValue, 10);
      onChange(agentId);
    }
  };

  const currentValue = value ? value.toString() : "none";
  const selectedAgent = agents.find(a => a.id === value);

  return (
    <div className={cn("flex items-center", className)}>
      <Select value={currentValue} onValueChange={handleValueChange}>
        <SelectTrigger className="h-8 border-0 bg-transparent shadow-none focus:ring-0 focus:ring-offset-0 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors p-0 gap-1 min-w-0">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-gray-600 flex-shrink-0" />
            <SelectValue
              placeholder={loading ? "加载中..." : "选择智能体"}
              className="text-sm"
            >
              {selectedAgent ? (
                <span className="truncate max-w-[120px] text-sm font-medium text-gray-600">
                  {selectedAgent.name}
                </span>
              ) : (
                <span className="text-gray-600 font-medium">选择智能体</span>
              )}
            </SelectValue>
          </div>
        </SelectTrigger>
        <SelectContent className="min-w-[240px]">
          <SelectItem value="none">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-gray-300"></div>
              <span className="text-gray-500">默认分析模式</span>
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
            agents.map((agent) => (
              <SelectItem key={agent.id} value={agent.id.toString()}>
                <div className="flex items-center gap-2 w-full">
                  <div className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0"></div>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="font-medium text-gray-900 truncate">
                      {agent.name}
                    </span>
                    <span className="text-xs text-gray-500 truncate">
                      {agent.role_description}
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
