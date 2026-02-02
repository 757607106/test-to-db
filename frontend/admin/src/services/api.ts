import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://192.168.13.163:8000/api';
console.log('API_URL:', API_URL);

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth data
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Database Connections
export const getConnections = () => api.get('/connections');
export const getConnection = (id: number) => api.get(`/connections/${id}`);
export const createConnection = (data: any) => api.post('/connections', data);
export const updateConnection = (id: number, data: any) => api.put(`/connections/${id}`, data);
export const deleteConnection = (id: number) => api.delete(`/connections/${id}`);
export const testConnection = (id: number) => api.post(`/connections/${id}/test`);
export const discoverAndSaveSchema = (id: number) => api.post(`/connections/${id}/discover-and-save`);

// Schema Management
export const discoverSchema = (connectionId: number) => api.get(`/schema/${connectionId}/discover`);
export const getSchemaMetadata = (connectionId: number) => api.get(`/schema/${connectionId}/metadata`);
export const getSavedSchema = (connectionId: number) => api.get(`/schema/${connectionId}/saved`);
export const publishSchema = (connectionId: number, data: any) => api.post(`/schema/${connectionId}/publish`, data);
export const updateTable = (tableId: number, data: any) => api.put(`/schema/tables/${tableId}`, data);
export const updateColumn = (columnId: number, data: any) => api.put(`/schema/columns/${columnId}`, data);
export const syncToNeo4j = (connectionId: number) => api.post(`/schema/${connectionId}/sync-to-neo4j`);
export const discoverAndSyncSchema = (connectionId: number) => api.post(`/schema/${connectionId}/discover-and-sync`);

// Intelligent Query
export const executeQuery = (data: any) => api.post('/query', data);

// Value Mappings
export const getValueMappings = (columnId?: number) =>
  columnId ? api.get(`/value-mappings?column_id=${columnId}`) : api.get('/value-mappings');
export const createValueMapping = (data: any) => api.post('/value-mappings', data);
export const updateValueMapping = (id: number, data: any) => api.put(`/value-mappings/${id}`, data);
export const deleteValueMapping = (id: number) => api.delete(`/value-mappings/${id}`);

// Graph Visualization
export const getGraphVisualization = (connectionId: number) => api.get(`/graph-visualization/${connectionId}`);

export default api;
