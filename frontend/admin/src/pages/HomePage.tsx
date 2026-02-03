
import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Space,
  message,
  Tabs
} from 'antd';
import {
  RocketOutlined,
  DatabaseOutlined,
  BulbOutlined,
  ShareAltOutlined,
  ApiOutlined,
  DeploymentUnitOutlined
} from '@ant-design/icons';
import { createSessionCode } from '../services/auth';
import { getChatUrl } from '../utils/apiConfig';
import SqlAgentFlowDiagram from '../components/SqlAgentFlowDiagram';
import '../styles/HomePage.css';

const { Title: AntTitle, Paragraph } = Typography;
const { TabPane } = Tabs;

const HomePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const features = [
    {
      icon: <BulbOutlined />,
      title: '智能查询',
      description: '自然语言转SQL，让数据查询变得简单直观',
      className: 'feature-indigo'
    },
    {
      icon: <DatabaseOutlined />,
      title: '数据建模',
      description: '智能识别数据结构，自动构建数据模型',
      className: 'feature-teal'
    },
    {
      icon: <ShareAltOutlined />,
      title: '图可视化',
      description: '直观展示数据关系，洞察数据价值',
      className: 'feature-amber'
    },
    {
      icon: <ApiOutlined />,
      title: '智能问答',
      description: '基于知识图谱的智能问答系统',
      className: 'feature-pink'
    }
  ];

  const handleStartChat = async () => {
    try {
      // 获取一次性 session code
      const { code } = await createSessionCode();
      // 使用动态 Chat URL，支持局域网访问
      const chatUrl = getChatUrl();
      window.open(`${chatUrl}?code=${code}`, '_blank');
    } catch (error) {
      console.error('获取 session code 失败:', error);
      message.error('跳转失败，请重试');
    }
  };

  return (
    <div className="homepage-container">
      {/* 头部标题区域 */}
      <div className="hero-section">
        <Card className="hero-card" variant="borderless">
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div className="hero-icon-wrapper">
              <DeploymentUnitOutlined className="hero-icon" />
            </div>

            <AntTitle level={1} className="hero-title">
              慧眼数据平台
            </AntTitle>

            <Paragraph className="hero-subtitle">
              基于LangGraph的智能Text-to-SQL系统，采用Hub-and-Spoke架构<br/>
              支持多轮对话、混合检索与可视化分析，让数据洞察触手可及
            </Paragraph>

            <Button
              type="primary"
              size="large"
              icon={<RocketOutlined />}
              onClick={handleStartChat}
              className="start-button"
            >
              开始对话
            </Button>
          </Space>
        </Card>
      </div>

      {/* 核心内容区域 - 使用Tabs切换 */}
      <div className="content-section">
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          centered
          size="large"
          className="homepage-tabs"
        >
          <TabPane tab="核心功能" key="overview">
            <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
              {features.map((feature, index) => (
                <Col xs={24} sm={12} lg={6} key={index}>
                  <Card className="feature-card" variant="borderless">
                    <div className={`feature-icon-wrapper ${feature.className}`}>
                      {feature.icon}
                    </div>
                    <AntTitle level={4} className="feature-title">
                      {feature.title}
                    </AntTitle>
                    <Paragraph className="feature-desc">
                      {feature.description}
                    </Paragraph>
                  </Card>
                </Col>
              ))}
            </Row>
          </TabPane>
          
          <TabPane tab="系统架构" key="architecture">
            <div className="architecture-section">
              <Card className="architecture-card" variant="borderless">
                <AntTitle level={3} style={{ textAlign: 'center', marginBottom: 32 }}>
                  SQL Agent 数据流程架构
                </AntTitle>
                <Paragraph style={{ textAlign: 'center', color: '#64748b', marginBottom: 40 }}>
                  基于LangGraph的Hub-and-Spoke Graph架构，实现智能SQL生成与执行
                </Paragraph>
                <div className="flow-diagram-placeholder">
                  <SqlAgentFlowDiagram />
                </div>
              </Card>
            </div>
          </TabPane>
        </Tabs>
      </div>

      <div className="footer-section">
        © 2024 慧眼数据平台 · Powered by LangGraph & LLM
      </div>
    </div>
  );
};

export default HomePage;
