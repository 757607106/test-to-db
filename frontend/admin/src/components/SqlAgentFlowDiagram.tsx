import React, { useEffect, useState } from 'react';
import { Card } from 'antd';
import {
  RocketOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  BarChartOutlined,
  LineChartOutlined,
  BulbOutlined,
  ApiOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import '../styles/SqlAgentFlowDiagram.css';

interface Agent {
  id: string;
  name: string;
  icon: React.ReactNode;
  color: string;
  description: string;
}

const SqlAgentFlowDiagram: React.FC = () => {
  const [activeAgent, setActiveAgent] = useState<string>('supervisor');

  // 定义Worker Agents
  const agents: Agent[] = [
    {
      id: 'schema',
      name: 'schema_agent',
      icon: <DatabaseOutlined />,
      color: '#14b8a6',
      description: '获取数据库结构'
    },
    {
      id: 'sql_generator',
      name: 'sql_generator_agent',
      icon: <DatabaseOutlined />,
      color: '#06b6d4',
      description: '生成SQL查询'
    },
    {
      id: 'sql_executor',
      name: 'sql_executor_agent',
      icon: <ThunderboltOutlined />,
      color: '#10b981',
      description: '执行SQL查询'
    },
    {
      id: 'data_analyst',
      name: 'data_analyst_agent',
      icon: <BarChartOutlined />,
      color: '#ec4899',
      description: '数据分析'
    },
    {
      id: 'chart_generator',
      name: 'chart_generator_agent',
      icon: <LineChartOutlined />,
      color: '#f97316',
      description: '图表生成'
    },
    {
      id: 'error_recovery',
      name: 'error_recovery_agent',
      icon: <CloseCircleOutlined />,
      color: '#ef4444',
      description: '错误恢复'
    }
  ];

  // 动画效果：依次激活Agent
  useEffect(() => {
    const sequence = ['supervisor', ...agents.map(a => a.id), 'supervisor'];
    let currentIndex = 0;

    const interval = setInterval(() => {
      setActiveAgent(sequence[currentIndex]);
      currentIndex = (currentIndex + 1) % sequence.length;
    }, 1500);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="sql-agent-hub-spoke">
      {/* 顶部说明 */}
      <div className="hub-spoke-header">
        <h4>Hub-and-Spoke Graph 架构</h4>
        <p>Supervisor作为中心节点，协调所有Worker Agent的执行</p>
      </div>

      {/* 架构图 */}
      <div className="hub-spoke-diagram">
        {/* 左侧：start节点 */}
        <div className="endpoint-node start-node">
          <div className="node-icon" style={{ background: '#6366f1' }}>
            <RocketOutlined />
          </div>
          <div className="node-label">start</div>
        </div>

        {/* 连接线：start to supervisor */}
        <svg className="connection-line start-to-hub">
          <path
            d="M 0 50 L 100 50"
            stroke="#cbd5e1"
            strokeWidth="2"
            fill="none"
            className={activeAgent === 'supervisor' ? 'active-path' : ''}
          />
        </svg>

        {/* 中心：Supervisor Hub */}
        <div className={`hub-node ${activeAgent === 'supervisor' ? 'active' : ''}`}>
          <div className="hub-icon">
            <ApiOutlined />
          </div>
          <div className="hub-label">supervisor</div>
          <div className="hub-desc">LLM智能调度</div>
        </div>

        {/* Worker Agents围绕Supervisor */}
        <div className="spoke-agents">
          {agents.map((agent, index) => {
            const isActive = activeAgent === agent.id;
            const angle = (index / agents.length) * 2 * Math.PI - Math.PI / 2;
            const radius = 200;
            const x = Math.cos(angle) * radius;
            const y = Math.sin(angle) * radius;

            return (
              <div key={agent.id}>
                {/* 连接线 */}
                <svg
                  className="spoke-line"
                  style={{
                    position: 'absolute',
                    left: '50%',
                    top: '50%',
                    width: Math.abs(x) + 20,
                    height: Math.abs(y) + 20,
                    pointerEvents: 'none',
                    transform: `translate(-50%, -50%)`
                  }}
                >
                  <path
                    d={`M ${Math.abs(x) / 2} ${Math.abs(y) / 2} Q ${Math.abs(x) * 0.75} ${Math.abs(y) * 0.75} ${Math.abs(x)} ${Math.abs(y)}`}
                    stroke={isActive ? agent.color : '#e2e8f0'}
                    strokeWidth={isActive ? '3' : '2'}
                    fill="none"
                    className={isActive ? 'active-spoke' : ''}
                  />
                </svg>

                {/* Agent节点 */}
                <div
                  className={`spoke-node ${isActive ? 'active' : ''}`}
                  style={{
                    left: `calc(50% + ${x}px)`,
                    top: `calc(50% + ${y}px)`,
                    borderColor: agent.color
                  }}
                >
                  <div className="spoke-icon" style={{ background: agent.color }}>
                    {agent.icon}
                  </div>
                  <div className="spoke-label">{agent.name}</div>
                  <div className="spoke-desc">{agent.description}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 连接线：supervisor to end */}
        <svg className="connection-line hub-to-end">
          <path
            d="M 0 50 L 100 50"
            stroke="#cbd5e1"
            strokeWidth="2"
            fill="none"
          />
        </svg>

        {/* 右侧：end节点 */}
        <div className="endpoint-node end-node">
          <div className="node-icon" style={{ background: '#6366f1' }}>
            <CheckCircleOutlined />
          </div>
          <div className="node-label">__end__</div>
        </div>
      </div>

      {/* 底部说明 */}
      <div className="hub-spoke-footer">
        <Card className="info-card" variant="borderless">
          <div className="info-grid">
            <div className="info-item">
              <strong>🎯 Supervisor调度</strong>
              <p>LLM决策下一步调用哪个Agent</p>
            </div>
            <div className="info-item">
              <strong>🔄 Hub-and-Spoke</strong>
              <p>中心调度模式，灵活路由</p>
            </div>
            <div className="info-item">
              <strong>🤝 Worker Agents</strong>
              <p>6个专业Agent处理具体任务</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default SqlAgentFlowDiagram;
