/**
 * 智能调优中心
 * 整合智能训练、指标库、SQL增强配置三个模块
 */
import React from 'react';
import { Tabs } from 'antd';
import { 
  BulbOutlined, 
  FunctionOutlined, 
  SettingOutlined 
} from '@ant-design/icons';
import { HybridQAContent } from './HybridQA';
import { MetricsContent } from './MetricsPage';
import { SQLEnhancementConfigContent } from './SQLEnhancementConfigPage';

const IntelligentTuningCenter: React.FC = () => {
  const items = [
    {
      key: 'training',
      label: (
        <span>
          <BulbOutlined style={{ marginRight: 8 }} />
          智能训练
        </span>
      ),
      children: <HybridQAContent />,
    },
    {
      key: 'metrics',
      label: (
        <span>
          <FunctionOutlined style={{ marginRight: 8 }} />
          指标库
        </span>
      ),
      children: <MetricsContent />,
    },
    {
      key: 'sql-enhancement',
      label: (
        <span>
          <SettingOutlined style={{ marginRight: 8 }} />
          SQL增强配置
        </span>
      ),
      children: <SQLEnhancementConfigContent />,
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Tabs 
        defaultActiveKey="training" 
        items={items}
        size="large"
      />
    </div>
  );
};

export default IntelligentTuningCenter;
