import api from './api';

export interface TenantUser {
  id: number;
  username: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  tenant_id: number | null;
  permissions: UserPermissions | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserPermissions {
  menus: string[];
  features: Record<string, string[]>;
}

export interface TenantInfo {
  id: number;
  name: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface TenantUserListResponse {
  total: number;
  users: TenantUser[];
}

export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
  display_name?: string;
  role?: string;
  permissions?: UserPermissions;
}

export interface UpdateUserRequest {
  display_name?: string;
  role?: string;
  is_active?: boolean;
}

export interface UpdatePermissionsRequest {
  permissions: UserPermissions;
}

export interface PermissionTemplates {
  default: UserPermissions;
  restricted: UserPermissions;
  available_menus: string[];
  available_features: Record<string, string[]>;
}

// Get current tenant info
export const getCurrentTenant = async (): Promise<TenantInfo> => {
  const response = await api.get('/tenant/me');
  return response.data;
};

// Get tenant users list
export const getTenantUsers = async (skip = 0, limit = 100): Promise<TenantUserListResponse> => {
  const response = await api.get('/tenant/users', { params: { skip, limit } });
  return response.data;
};

// Create tenant user
export const createTenantUser = async (data: CreateUserRequest): Promise<TenantUser> => {
  const response = await api.post('/tenant/users', data);
  return response.data;
};

// Get tenant user by ID
export const getTenantUser = async (userId: number): Promise<TenantUser> => {
  const response = await api.get(`/tenant/users/${userId}`);
  return response.data;
};

// Update tenant user
export const updateTenantUser = async (userId: number, data: UpdateUserRequest): Promise<TenantUser> => {
  const response = await api.put(`/tenant/users/${userId}`, data);
  return response.data;
};

// Update user permissions
export const updateUserPermissions = async (userId: number, data: UpdatePermissionsRequest): Promise<TenantUser> => {
  const response = await api.put(`/tenant/users/${userId}/permissions`, data);
  return response.data;
};

// Toggle user status
export const toggleUserStatus = async (userId: number): Promise<TenantUser> => {
  const response = await api.put(`/tenant/users/${userId}/status`);
  return response.data;
};

// Delete tenant user
export const deleteTenantUser = async (userId: number): Promise<void> => {
  await api.delete(`/tenant/users/${userId}`);
};

// Get permission templates
export const getPermissionTemplates = async (): Promise<PermissionTemplates> => {
  const response = await api.get('/tenant/permissions/templates');
  return response.data;
};
