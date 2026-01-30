/**
 * 智能调优中心
 * 
 * 核心功能：智能训练（HybridQA）
 * - 问答对管理
 * - 向量检索训练
 * - 用户反馈收集
 */
import React from 'react';
import { HybridQAContent } from './HybridQA';

const IntelligentTuningCenter: React.FC = () => {
  return (
    <div style={{ padding: '24px' }}>
      <HybridQAContent />
    </div>
  );
};

export default IntelligentTuningCenter;
