
import React from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Space
} from 'antd';
import {
  RocketOutlined,
  DatabaseOutlined,
  BulbOutlined,
  ShareAltOutlined,
  ApiOutlined
} from '@ant-design/icons';

const { Title: AntTitle, Paragraph } = Typography;

const HomePage: React.FC = () => {
  const features = [
    {
      icon: <BulbOutlined />,
      title: '智能查询',
      description: '自然语言转SQL，让数据查询变得简单直观',
      color: '#1890ff'
    },
    {
      icon: <DatabaseOutlined />,
      title: '数据建模',
      description: '智能识别数据结构，自动构建数据模型',
      color: '#52c41a'
    },
    {
      icon: <ShareAltOutlined />,
      title: '图可视化',
      description: '直观展示数据关系，洞察数据价值',
      color: '#faad14'
    },
    {
      icon: <ApiOutlined />,
      title: '智能问答',
      description: '基于知识图谱的智能问答系统',
      color: '#f5222d'
    }
  ];

  const handleStartChat = () => {
    window.open('http://localhost:3000', '_blank');
  };

  return (
    <div style={{ padding: '20px', minHeight: '100vh', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      {/* 头部标题区域 */}
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <Card style={{ borderRadius: '20px', background: 'rgba(255, 255, 255, 0.95)' }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <ApiOutlined style={{ fontSize: '80px', color: '#1890ff' }} />

            <AntTitle level={1} style={{ margin: 0, background: 'linear-gradient(45deg, #1890ff, #722ed1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              但问智能数据分析系统
            </AntTitle>

            <Paragraph style={{ fontSize: '18px', color: '#666', maxWidth: '600px', margin: '0 auto' }}>
              基于人工智能的下一代数据分析平台，让数据洞察触手可及
            </Paragraph>

            <Button
              type="primary"
              size="large"
              icon={<RocketOutlined />}
              onClick={handleStartChat}
              style={{
                height: '60px',
                fontSize: '20px',
                borderRadius: '30px',
                padding: '0 40px'
              }}
            >
              开始对话
            </Button>
          </Space>
        </Card>
      </div>

      {/* 功能特性区域 */}
      <div style={{ marginBottom: '40px' }}>
        <AntTitle level={2} style={{ textAlign: 'center', color: 'white', marginBottom: '30px' }}>
          核心功能
        </AntTitle>
        <Row gutter={[24, 24]}>
          {features.map((feature, index) => (
            <Col xs={24} sm={12} md={6} key={index}>
              <Card
                style={{
                  minHeight: '250px',
                  borderRadius: '20px',
                  background: 'rgba(255, 255, 255, 0.95)',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '48px', color: feature.color, marginBottom: '15px' }}>
                  {feature.icon}
                </div>
                <AntTitle level={4} style={{ margin: '10px 0', color: '#333' }}>
                  {feature.title}
                </AntTitle>
                <Paragraph style={{ color: '#666', fontSize: '14px' }}>
                  {feature.description}
                </Paragraph>
              </Card>
            </Col>
          ))}
        </Row>
      </div>
    </div>
  );
};

export default HomePage;
