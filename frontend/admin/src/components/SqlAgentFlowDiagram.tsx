import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Card, Tag, Badge } from 'antd';
import {
  DatabaseOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  BarChartOutlined,
  LineChartOutlined,
  ApiOutlined,
  CloseCircleOutlined,
  UserOutlined,
  MessageOutlined,
  CodeOutlined,
  FileSearchOutlined
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import '../styles/SqlAgentFlowDiagram.css';

interface Agent {
  id: string;
  name: string;
  displayName: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  step?: number;
}

interface FlowStep {
  id: string;
  label: string;
  description: string;
}

const SqlAgentFlowDiagram: React.FC = () => {
  const [activeAgent, setActiveAgent] = useState<string>('user_input');
  const [flowPhase, setFlowPhase] = useState<'input' | 'processing' | 'output'>('input');
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isAnimating, setIsAnimating] = useState(true);

  // 定义Worker Agents（按照处理顺序排列）
  const agents: Agent[] = useMemo(() => [
    {
      id: 'schema',
      name: 'schema_agent',
      displayName: 'Schema Agent',
      icon: <FileSearchOutlined />,
      color: '#14b8a6',
      description: '获取数据库结构',
      step: 1
    },
    {
      id: 'sql_generator',
      name: 'sql_generator_agent',
      displayName: 'SQL Generator',
      icon: <CodeOutlined />,
      color: '#06b6d4',
      description: '生成SQL查询',
      step: 2
    },
    {
      id: 'sql_executor',
      name: 'sql_executor_agent',
      displayName: 'SQL Executor',
      icon: <ThunderboltOutlined />,
      color: '#10b981',
      description: '执行SQL查询',
      step: 3
    },
    {
      id: 'data_analyst',
      name: 'data_analyst_agent',
      displayName: 'Data Analyst',
      icon: <BarChartOutlined />,
      color: '#8b5cf6',
      description: '数据分析',
      step: 4
    },
    {
      id: 'chart_generator',
      name: 'chart_generator_agent',
      displayName: 'Chart Generator',
      icon: <LineChartOutlined />,
      color: '#f97316',
      description: '图表生成',
      step: 5
    },
    {
      id: 'error_recovery',
      name: 'error_recovery_agent',
      displayName: 'Error Recovery',
      icon: <CloseCircleOutlined />,
      color: '#ef4444',
      description: '错误恢复',
      step: 6
    }
  ], []);

  // 数据流步骤说明
  const flowSteps: FlowStep[] = useMemo(() => [
    { id: 'user_input', label: '用户输入', description: '自然语言查询请求' },
    { id: 'supervisor', label: 'Supervisor调度', description: 'LLM智能决策路由' },
    { id: 'schema', label: 'Schema分析', description: '解析数据库结构' },
    { id: 'sql_generator', label: 'SQL生成', description: '转换为SQL语句' },
    { id: 'sql_executor', label: 'SQL执行', description: '数据库查询执行' },
    { id: 'data_analyst', label: '数据分析', description: '分析查询结果' },
    { id: 'chart_generator', label: '图表生成', description: '可视化展示' },
    { id: 'output', label: '结果输出', description: '返回最终结果' }
  ], []);

  // 动画序列
  const animationSequence = useMemo(() => [
    'user_input',
    'supervisor',
    'schema',
    'supervisor',
    'sql_generator',
    'supervisor',
    'sql_executor',
    'supervisor',
    'data_analyst',
    'supervisor',
    'chart_generator',
    'supervisor',
    'output'
  ], []);

  // 动画效果：依次激活Agent
  useEffect(() => {
    if (!isAnimating) return;

    let currentIndex = 0;
    const interval = setInterval(() => {
      const current = animationSequence[currentIndex];
      setActiveAgent(current);
      
      // 更新流程阶段
      if (current === 'user_input') {
        setFlowPhase('input');
        setCurrentStep(0);
      } else if (current === 'output') {
        setFlowPhase('output');
        setCurrentStep(flowSteps.length - 1);
      } else {
        setFlowPhase('processing');
        const stepIndex = flowSteps.findIndex(s => s.id === current);
        if (stepIndex >= 0) setCurrentStep(stepIndex);
      }

      currentIndex = (currentIndex + 1) % animationSequence.length;
    }, 1800);

    return () => clearInterval(interval);
  }, [isAnimating, animationSequence, flowSteps]);

  // 计算Agent在Hub周围的位置
  const getAgentPosition = useCallback((index: number, total: number) => {
    const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
    const radius = 180;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius
    };
  }, []);

  return (
    <div className="sql-agent-flow-container">
      {/* 顶部：流程步骤指示器 */}
      <div className="flow-steps-indicator">
        <div className="steps-track">
          {flowSteps.map((step, index) => (
            <div
              key={step.id}
              className={`step-item ${currentStep >= index ? 'completed' : ''} ${activeAgent === step.id ? 'active' : ''}`}
            >
              <motion.div
                className="step-dot"
                animate={{
                  scale: activeAgent === step.id ? 1.3 : 1,
                  backgroundColor: currentStep >= index ? '#6366f1' : '#e2e8f0'
                }}
                transition={{ duration: 0.3 }}
              />
              <span className="step-label">{step.label}</span>
              {index < flowSteps.length - 1 && (
                <div className={`step-connector ${currentStep > index ? 'active' : ''}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 主图区域 */}
      <div className="flow-diagram-main">
        {/* 左侧：用户输入 */}
        <motion.div
          className={`flow-endpoint user-input ${activeAgent === 'user_input' ? 'active' : ''}`}
          animate={{
            scale: activeAgent === 'user_input' ? 1.08 : 1,
            boxShadow: activeAgent === 'user_input'
              ? '0 0 30px rgba(99, 102, 241, 0.4)'
              : '0 4px 12px rgba(0, 0, 0, 0.1)'
          }}
          transition={{ duration: 0.3 }}
        >
          <div className="endpoint-icon" style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
            <UserOutlined />
          </div>
          <div className="endpoint-content">
            <div className="endpoint-title">用户查询</div>
            <div className="endpoint-desc">自然语言输入</div>
          </div>
          <AnimatePresence>
            {activeAgent === 'user_input' && (
              <motion.div
                className="data-packet"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
              >
                <MessageOutlined /> 发送请求
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* 连接线：输入到Supervisor */}
        <svg className="flow-connector input-to-hub" viewBox="0 0 120 100">
          <defs>
            <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#6366f1" />
            </marker>
          </defs>
          <path
            d="M 10 50 L 110 50"
            stroke={flowPhase !== 'output' && activeAgent !== 'output' ? 'url(#lineGradient)' : '#e2e8f0'}
            strokeWidth={activeAgent === 'user_input' || activeAgent === 'supervisor' ? 3 : 2}
            fill="none"
            strokeDasharray={activeAgent === 'user_input' ? '8 4' : 'none'}
            className={activeAgent === 'user_input' ? 'animated-dash' : ''}
            markerEnd="url(#arrowhead)"
          />
          <AnimatePresence>
            {activeAgent === 'user_input' && (
              <motion.circle
                r="6"
                fill="#6366f1"
                initial={{ cx: 10, cy: 50 }}
                animate={{ cx: 110, cy: 50 }}
                transition={{ duration: 0.8, ease: 'easeInOut' }}
              />
            )}
          </AnimatePresence>
        </svg>

        {/* 中心：Hub-and-Spoke 区域 */}
        <div className="hub-spoke-area">
          {/* SVG连接线层 */}
          <svg className="spoke-lines-layer" viewBox="-250 -250 500 500">
            <defs>
              {agents.map(agent => (
                <linearGradient key={`grad-${agent.id}`} id={`grad-${agent.id}`} x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#6366f1" />
                  <stop offset="100%" stopColor={agent.color} />
                </linearGradient>
              ))}
            </defs>
            {agents.map((agent, index) => {
              const pos = getAgentPosition(index, agents.length);
              const isActive = activeAgent === agent.id;
              return (
                <g key={`line-${agent.id}`}>
                  <path
                    d={`M 0 0 L ${pos.x * 0.55} ${pos.y * 0.55}`}
                    stroke={isActive ? `url(#grad-${agent.id})` : '#e2e8f0'}
                    strokeWidth={isActive ? 3 : 2}
                    fill="none"
                    strokeDasharray={isActive ? '6 3' : 'none'}
                    className={isActive ? 'animated-dash' : ''}
                  />
                  <AnimatePresence>
                    {isActive && (
                      <motion.circle
                        r="5"
                        fill={agent.color}
                        initial={{ cx: 0, cy: 0, opacity: 0 }}
                        animate={{ 
                          cx: pos.x * 0.55, 
                          cy: pos.y * 0.55, 
                          opacity: 1 
                        }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.6, ease: 'easeOut' }}
                      />
                    )}
                  </AnimatePresence>
                </g>
              );
            })}
          </svg>

          {/* Supervisor中心节点 */}
          <motion.div
            className={`supervisor-hub ${activeAgent === 'supervisor' ? 'active' : ''}`}
            animate={{
              scale: activeAgent === 'supervisor' ? 1.1 : 1,
              boxShadow: activeAgent === 'supervisor'
                ? '0 0 40px rgba(99, 102, 241, 0.5)'
                : '0 8px 24px rgba(99, 102, 241, 0.2)'
            }}
            transition={{ duration: 0.3 }}
          >
            <div className="hub-inner">
              <motion.div
                className="hub-icon-container"
                animate={{ rotate: activeAgent === 'supervisor' ? 360 : 0 }}
                transition={{ duration: 2, ease: 'linear', repeat: activeAgent === 'supervisor' ? Infinity : 0 }}
              >
                <ApiOutlined />
              </motion.div>
              <div className="hub-label">Supervisor</div>
              <div className="hub-sublabel">LLM智能调度</div>
            </div>
            <div className="hub-ring" />
            <div className="hub-ring ring-2" />
          </motion.div>

          {/* Worker Agent节点 */}
          {agents.map((agent, index) => {
            const pos = getAgentPosition(index, agents.length);
            const isActive = activeAgent === agent.id;
            return (
              <motion.div
                key={agent.id}
                className={`worker-agent ${isActive ? 'active' : ''}`}
                style={{
                  left: `calc(50% + ${pos.x}px)`,
                  top: `calc(50% + ${pos.y}px)`,
                  '--agent-color': agent.color
                } as React.CSSProperties}
                animate={{
                  scale: isActive ? 1.15 : 1,
                  zIndex: isActive ? 10 : 5
                }}
                transition={{ duration: 0.3 }}
                whileHover={{ scale: 1.1 }}
              >
                <div className="agent-card">
                  <Badge 
                    count={agent.step} 
                    style={{ backgroundColor: agent.color }}
                    className="agent-step-badge"
                  />
                  <div className="agent-icon" style={{ backgroundColor: agent.color }}>
                    {agent.icon}
                  </div>
                  <div className="agent-info">
                    <div className="agent-name">{agent.displayName}</div>
                    <div className="agent-desc">{agent.description}</div>
                  </div>
                  {isActive && (
                    <motion.div
                      className="agent-status"
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <Tag color={agent.color} className="status-tag">处理中</Tag>
                    </motion.div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* 连接线：Supervisor到输出 */}
        <svg className="flow-connector hub-to-output" viewBox="0 0 120 100">
          <path
            d="M 10 50 L 110 50"
            stroke={flowPhase === 'output' || activeAgent === 'output' ? 'url(#lineGradient)' : '#e2e8f0'}
            strokeWidth={activeAgent === 'output' ? 3 : 2}
            fill="none"
            strokeDasharray={activeAgent === 'output' ? '8 4' : 'none'}
            className={activeAgent === 'output' ? 'animated-dash' : ''}
            markerEnd="url(#arrowhead)"
          />
          <AnimatePresence>
            {activeAgent === 'output' && (
              <motion.circle
                r="6"
                fill="#10b981"
                initial={{ cx: 10, cy: 50 }}
                animate={{ cx: 110, cy: 50 }}
                transition={{ duration: 0.8, ease: 'easeInOut' }}
              />
            )}
          </AnimatePresence>
        </svg>

        {/* 右侧：结果输出 */}
        <motion.div
          className={`flow-endpoint result-output ${activeAgent === 'output' ? 'active' : ''}`}
          animate={{
            scale: activeAgent === 'output' ? 1.08 : 1,
            boxShadow: activeAgent === 'output'
              ? '0 0 30px rgba(16, 185, 129, 0.4)'
              : '0 4px 12px rgba(0, 0, 0, 0.1)'
          }}
          transition={{ duration: 0.3 }}
        >
          <div className="endpoint-icon" style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>
            <CheckCircleOutlined />
          </div>
          <div className="endpoint-content">
            <div className="endpoint-title">结果输出</div>
            <div className="endpoint-desc">数据与图表</div>
          </div>
          <AnimatePresence>
            {activeAgent === 'output' && (
              <motion.div
                className="data-packet success"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
              >
                <CheckCircleOutlined /> 完成
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* 底部：流程说明卡片 */}
      <div className="flow-info-section">
        <div className="info-cards-grid">
          <Card className="flow-info-card" variant="borderless">
            <div className="info-card-icon" style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
              <ApiOutlined />
            </div>
            <div className="info-card-content">
              <h4>Hub-and-Spoke 架构</h4>
              <p>Supervisor作为中心调度节点，智能路由请求到对应的Worker Agent</p>
            </div>
          </Card>
          <Card className="flow-info-card" variant="borderless">
            <div className="info-card-icon" style={{ background: 'linear-gradient(135deg, #14b8a6, #06b6d4)' }}>
              <DatabaseOutlined />
            </div>
            <div className="info-card-content">
              <h4>多Agent协作</h4>
              <p>6个专业Agent分工协作，从Schema分析到图表生成，全流程自动化</p>
            </div>
          </Card>
          <Card className="flow-info-card" variant="borderless">
            <div className="info-card-icon" style={{ background: 'linear-gradient(135deg, #f97316, #ef4444)' }}>
              <ThunderboltOutlined />
            </div>
            <div className="info-card-content">
              <h4>智能错误恢复</h4>
              <p>内置错误恢复机制，自动处理SQL执行异常，确保查询稳定性</p>
            </div>
          </Card>
        </div>
      </div>

      {/* 动画控制按钮 */}
      <div className="animation-control">
        <button
          className={`control-btn ${isAnimating ? 'active' : ''}`}
          onClick={() => setIsAnimating(!isAnimating)}
        >
          {isAnimating ? '暂停动画' : '播放动画'}
        </button>
      </div>
    </div>
  );
};

export default SqlAgentFlowDiagram;
