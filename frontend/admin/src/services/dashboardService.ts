// Dashboard和Widget服务

import axios from 'axios';
import type {
  Dashboard,
  DashboardListItem,
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
  DashboardInsightRequest,
  DashboardInsightResponse,
  InsightConditions,
} from '../types/dashboard';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

  // 生成Dashboard洞察
  async generateDashboardInsights(
    dashboardId: number,
    request?: DashboardInsightRequest
  ): Promise<DashboardInsightResponse> {
    const response = await api.post(`/dashboards/${dashboardId}/insights`, request || {});
    return response.data;
  },

  // 获取Dashboard洞察
  async getDashboardInsights(dashboardId: number): Promise<Widget | null> {
    const response = await api.get(`/dashboards/${dashboardId}/insights`);
    return response.data;
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

  // 刷新洞察Widget
  async refreshInsightWidget(
    widgetId: number,
    conditions?: InsightConditions
  ): Promise<DashboardInsightResponse> {
    const response = await api.put(`/widgets/${widgetId}/refresh-insights`, { conditions });
    return response.data;
  },
};

// 导出统一的服务对象
export default {
  dashboard: dashboardService,
  widget: widgetService,
};
