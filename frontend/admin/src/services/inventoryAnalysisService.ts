/**
 * 库存分析 API 服务
 * 商业级库存分析引擎：ABC-XYZ分类、周转率分析、安全库存计算、供应商评估
 */
import api from './api';
import {
  ABCXYZRequest,
  ABCXYZResult,
  TurnoverRequest,
  TurnoverResult,
  SafetyStockRequest,
  SafetyStockResult,
  SupplierEvaluationRequest,
  SupplierResult,
  InventoryAnalysisResponse,
} from '../types/inventoryAnalysis';

/**
 * ABC-XYZ 库存分类分析
 * 
 * @param request 分析请求参数
 * @returns 分析结果（汇总、矩阵、帕累托图、详细列表）
 */
export const analyzeABCXYZ = async (
  request: ABCXYZRequest
): Promise<InventoryAnalysisResponse<ABCXYZResult>> => {
  const response = await api.post<InventoryAnalysisResponse<ABCXYZResult>>(
    '/inventory/abc-xyz',
    request
  );
  return response.data;
};

/**
 * 库存周转率分析
 * 
 * @param request 分析请求参数
 * @returns 分析结果（周转率、库存天数、健康度）
 */
export const analyzeTurnover = async (
  request: TurnoverRequest
): Promise<InventoryAnalysisResponse<TurnoverResult>> => {
  const response = await api.post<InventoryAnalysisResponse<TurnoverResult>>(
    '/inventory/turnover',
    request
  );
  return response.data;
};

/**
 * 安全库存计算
 * 
 * @param request 计算请求参数
 * @returns 计算结果（安全库存、再订货点、统计依据）
 */
export const calculateSafetyStock = async (
  request: SafetyStockRequest
): Promise<InventoryAnalysisResponse<SafetyStockResult>> => {
  const response = await api.post<InventoryAnalysisResponse<SafetyStockResult>>(
    '/inventory/safety-stock',
    request
  );
  return response.data;
};

/**
 * 供应商评估
 * 
 * @param request 评估请求参数
 * @returns 评估结果（加权得分、排名、聚类分组）
 */
export const evaluateSuppliers = async (
  request: SupplierEvaluationRequest
): Promise<InventoryAnalysisResponse<SupplierResult>> => {
  const response = await api.post<InventoryAnalysisResponse<SupplierResult>>(
    '/inventory/supplier-eval',
    request
  );
  return response.data;
};

// 导出统一服务对象
export const inventoryAnalysisService = {
  analyzeABCXYZ,
  analyzeTurnover,
  calculateSafetyStock,
  evaluateSuppliers,
};
