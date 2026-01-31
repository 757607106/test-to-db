// Dashboard和Widget服务

import api from './api';
import type {
  DashboardDetail,
  DashboardCreate,
  DashboardUpdate,
  DashboardListResponse,
  Widget,
  WidgetCreate,
  WidgetUpdate,
  WidgetRefreshResponse,
  WidgetRegenerateRequest,
  WidgetRegenerateResponse,
  DashboardPermission,
  PermissionCreate,
  PermissionUpdate,
  LayoutUpdateRequest,
  AIChartRecommendResponse,
  RefreshConfig,
  GlobalRefreshRequest,
  GlobalRefreshResponse,
} from '../types/dashboard';

// Dashboard服务
export const dashboardService = {
  // 获取Dashboard列表
  async getDashboards(params?: {
    scope?: 'mine' | 'shared' | 'public' | 'all';
    page?: number;
    page_size?: number;
    search?: string;
  }): Promise<DashboardListResponse> {
    const response = await api.get('/dashboards/', { params });
    return response.data;
  },

  // 获取Dashboard详情
  async getDashboardDetail(id: number): Promise<DashboardDetail> {
    const response = await api.get(`/dashboards/${id}`);
    return response.data;
  },

  // 创建Dashboard
  async createDashboard(data: DashboardCreate): Promise<DashboardDetail> {
    const response = await api.post('/dashboards/', data);
    return response.data;
  },

  // 更新Dashboard
  async updateDashboard(id: number, data: DashboardUpdate): Promise<DashboardDetail> {
    const response = await api.put(`/dashboards/${id}`, data);
    return response.data;
  },

  // 删除Dashboard
  async deleteDashboard(id: number): Promise<{ message: string }> {
    const response = await api.delete(`/dashboards/${id}`);
    return response.data;
  },

  // 更新Dashboard布局
  async updateDashboardLayout(id: number, layout: LayoutUpdateRequest): Promise<DashboardDetail> {
    const response = await api.put(`/dashboards/${id}/layout`, layout);
    return response.data;
  },

  // 获取Dashboard权限列表
  async getDashboardPermissions(dashboardId: number): Promise<DashboardPermission[]> {
    const response = await api.get(`/dashboards/${dashboardId}/permissions`);
    return response.data;
  },

  // 添加Dashboard权限
  async addDashboardPermission(dashboardId: number, data: PermissionCreate): Promise<DashboardPermission> {
    const response = await api.post(`/dashboards/${dashboardId}/permissions`, data);
    return response.data;
  },

  // 更新Dashboard权限
  async updateDashboardPermission(
    dashboardId: number,
    userId: number,
    data: PermissionUpdate
  ): Promise<DashboardPermission> {
    const response = await api.put(`/dashboards/${dashboardId}/permissions/${userId}`, data);
    return response.data;
  },

  // 删除Dashboard权限
  async deleteDashboardPermission(dashboardId: number, userId: number): Promise<{ message: string }> {
    const response = await api.delete(`/dashboards/${dashboardId}/permissions/${userId}`);
    return response.data;
  },

  // 生成智能挖掘建议
  async generateMiningSuggestions(
    dashboardId: number,
    connectionId: number,
    intent?: string,
    limit?: number
  ): Promise<{ suggestions: any[] }> {
    const response = await api.post(`/dashboards/${dashboardId}/mining/suggestions`, {
      connection_id: connectionId,
      intent,
      limit: limit || 10
    });
    return response.data;
  },

  // 应用智能挖掘建议
  async applyMiningSuggestions(
    dashboardId: number,
    connectionId: number,
    suggestions: any[]
  ): Promise<any> {
    const response = await api.post(`/dashboards/${dashboardId}/mining/apply`, {
      connection_id: connectionId,
      suggestions
    });
    return response.data;
  },

  // P1: 获取刷新配置
  async getRefreshConfig(dashboardId: number): Promise<RefreshConfig> {
    const response = await api.get(`/dashboards/${dashboardId}/refresh/config`);
    const data = response.data;
    return {
      enabled: data.enabled || false,
      intervalSeconds: data.interval_seconds || 300,
      autoRefreshWidgetIds: data.auto_refresh_widget_ids || [],
      lastGlobalRefresh: data.last_global_refresh,
    };
  },

  // P1: 更新刷新配置
  async updateRefreshConfig(
    dashboardId: number,
    config: RefreshConfig
  ): Promise<RefreshConfig> {
    const response = await api.put(`/dashboards/${dashboardId}/refresh/config`, {
      enabled: config.enabled,
      interval_seconds: config.intervalSeconds,
      auto_refresh_widget_ids: config.autoRefreshWidgetIds,
    });
    const data = response.data;
    return {
      enabled: data.enabled || false,
      intervalSeconds: data.interval_seconds || 300,
      autoRefreshWidgetIds: data.auto_refresh_widget_ids || [],
      lastGlobalRefresh: data.last_global_refresh,
    };
  },

  // P1: 全局刷新
  async globalRefresh(
    dashboardId: number,
    request: GlobalRefreshRequest
  ): Promise<GlobalRefreshResponse> {
    const response = await api.post(`/dashboards/${dashboardId}/refresh/global`, {
      force: request.force,
      widget_ids: request.widgetIds,
    });
    const data = response.data;
    
    // 转换results中的key和value
    const results: Record<number, any> = {};
    if (data.results) {
      for (const [key, value] of Object.entries(data.results)) {
        const v = value as any;
        results[parseInt(key)] = {
          widgetId: v.widget_id,
          success: v.success,
          durationMs: v.duration_ms || 0,
          error: v.error,
          fromCache: v.from_cache || false,
          rowCount: v.row_count || 0,
        };
      }
    }
    
    return {
      successCount: data.success_count || 0,
      failedCount: data.failed_count || 0,
      results,
      totalDurationMs: data.total_duration_ms || 0,
      refreshTimestamp: data.refresh_timestamp,
    };
  },
};

// Widget服务
export const widgetService = {
  // 创建Widget
  async createWidget(dashboardId: number, data: WidgetCreate): Promise<Widget> {
    const response = await api.post(`/dashboards/${dashboardId}/widgets`, data);
    return response.data;
  },

  // 更新Widget
  async updateWidget(widgetId: number, data: WidgetUpdate): Promise<Widget> {
    const response = await api.put(`/widgets/${widgetId}`, data);
    return response.data;
  },

  // 删除Widget
  async deleteWidget(widgetId: number): Promise<{ message: string }> {
    const response = await api.delete(`/widgets/${widgetId}`);
    return response.data;
  },

  // 手动刷新Widget数据
  async refreshWidget(widgetId: number): Promise<WidgetRefreshResponse> {
    const response = await api.post(`/widgets/${widgetId}/refresh`);
    return response.data;
  },

  // 重新生成Widget查询
  async regenerateWidgetQuery(widgetId: number, data: WidgetRegenerateRequest): Promise<WidgetRegenerateResponse> {
    const response = await api.post(`/widgets/${widgetId}/regenerate`, data);
    return response.data;
  },

  // 批量更新Widget位置（用于拖拽后批量保存）
  async batchUpdateWidgetPositions(
    widgets: Array<{ id: number; position_config: any }>
  ): Promise<{ message: string; updated_count: number }> {
    const updatePromises = widgets.map((widget) =>
      api.put(`/widgets/${widget.id}`, { position_config: widget.position_config })
    );
    
    try {
      await Promise.all(updatePromises);
      return {
        message: 'Positions updated successfully',
        updated_count: widgets.length,
      };
    } catch (error) {
      throw new Error('Failed to update widget positions');
    }
  },

  // AI 智能推荐图表类型
  async getAIChartRecommendation(
    widgetId: number,
    dataSample?: any,
    intent?: string
  ): Promise<AIChartRecommendResponse> {
    const response = await api.post(`/widgets/${widgetId}/ai-recommend`, {
      data_sample: dataSample,
      intent,
    });
    return response.data;
  },

  // 批量刷新所有Widget
  async batchRefreshWidgets(widgetIds: number[]): Promise<{
    success: number[];
    failed: number[];
    results: Record<number, WidgetRefreshResponse>;
  }> {
    const results: Record<number, WidgetRefreshResponse> = {};
    const success: number[] = [];
    const failed: number[] = [];

    await Promise.all(
      widgetIds.map(async (id) => {
        try {
          const response = await api.post(`/widgets/${id}/refresh`);
          results[id] = response.data;
          success.push(id);
        } catch (error) {
          failed.push(id);
        }
      })
    );

    return { success, failed, results };
  },
};

// 导出统一的服务对象
export default {
  dashboard: dashboardService,
  widget: widgetService,
};
