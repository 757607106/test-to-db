
import React from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Space,
  message
} from 'antd';
import {
  RocketOutlined,
  DatabaseOutlined,
  BulbOutlined,
  ShareAltOutlined,
  ApiOutlined
} from '@ant-design/icons';
import { createSessionCode } from '../services/auth';
import '../styles/HomePage.css';

const { Title: AntTitle, Paragraph } = Typography;

const HomePage: React.FC = () => {
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
      // 使用 code 而非 token 跳转，更安全
      window.open(`http://localhost:3000?code=${code}`, '_blank');
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
              <ApiOutlined className="hero-icon" />
            </div>

            <AntTitle level={1} className="hero-title">
              慧眼数据平台
            </AntTitle>

            <Paragraph className="hero-subtitle">
              基于人工智能的下一代数据分析平台，让数据洞察触手可及。<br/>
              连接您的数据源，开启智能对话之旅。
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

      {/* 功能特性区域 */}
      <div className="features-section">
        <AntTitle level={2} className="section-title">
          核心功能
        </AntTitle>
        <Row gutter={[24, 24]}>
          {features.map((feature, index) => (
            <Col xs={24} sm={12} md={6} key={index}>
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
      </div>

      <div className="footer-section">
        © 2024 慧眼数据平台 · Powered by LLM & Knowledge Graph
      </div>
    </div>
  );
};

export default HomePage;
