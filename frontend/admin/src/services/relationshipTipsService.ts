
import api from './api';

/**
 * 获取关系类型提示信息
 * @returns 关系类型提示信息
 */
export const getRelationshipTips = async () => {
  try {
    const response = await api.get('/relationship-tips/');
    return response.data;
  } catch (error) {
    console.error('获取关系类型提示信息出错:', error);
    // 返回空对象作为降级处理
    return {};
  }
};
