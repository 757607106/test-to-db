import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  Space,
  message,
  Tabs,
  Row,
  Col,
} from 'antd';
import {
  UserOutlined,
  LockOutlined,
  MailOutlined,
  ApiOutlined,
  BankOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  RocketOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

const { Title: AntTitle, Paragraph } = Typography;

interface LoginFormData {
  username: string;
  password: string;
}

interface RegisterFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  display_name?: string;
  tenant_name?: string;
}

const LoginPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Get redirect path from location state
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleLogin = async (values: LoginFormData) => {
    setLoading(true);
    try {
      await login(values);
      message.success('登录成功');
      navigate(from, { replace: true });
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '登录失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: RegisterFormData) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
        display_name: values.display_name,
        tenant_name: values.tenant_name,
      });
      message.success('注册成功');
      navigate(from, { replace: true });
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '注册失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
      }}
    >
      {/* Animated Background Shapes */}
      <div
        style={{
          position: 'absolute',
          top: '-10%',
          right: '-5%',
          width: '600px',
          height: '600px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(102, 126, 234, 0.3) 0%, transparent 70%)',
          filter: 'blur(60px)',
          animation: 'float 20s ease-in-out infinite',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '-10%',
          left: '-5%',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(118, 75, 162, 0.3) 0%, transparent 70%)',
          filter: 'blur(60px)',
          animation: 'float 15s ease-in-out infinite reverse',
        }}
      />
      
      {/* Geometric Decorations */}
      <div
        style={{
          position: 'absolute',
          top: '20%',
          left: '10%',
          width: '100px',
          height: '100px',
          border: '2px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          transform: 'rotate(45deg)',
          animation: 'rotate 30s linear infinite',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '30%',
          right: '15%',
          width: '80px',
          height: '80px',
          border: '2px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '50%',
          animation: 'pulse 8s ease-in-out infinite',
        }}
      />

      <style>{`
        @keyframes float {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -30px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        @keyframes rotate {
          from { transform: rotate(45deg); }
          to { transform: rotate(405deg); }
        }
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.2); opacity: 0.8; }
        }
        @keyframes slideInLeft {
          from { opacity: 0; transform: translateX(-30px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(30px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes iconGlow {
          0%, 100% { filter: drop-shadow(0 0 2px currentColor); }
          50% { filter: drop-shadow(0 0 8px currentColor); }
        }
        
        /* Feature Cards Animation */
        .feature-item {
          animation: fadeInUp 0.6s ease-out backwards;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .feature-item:nth-child(1) { animation-delay: 0.2s; }
        .feature-item:nth-child(2) { animation-delay: 0.35s; }
        .feature-item:nth-child(3) { animation-delay: 0.5s; }
        
        .feature-item:hover {
          transform: translateX(8px);
        }
        
        /* Icon Animation */
        .feature-icon-box {
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .feature-item:hover .feature-icon-box {
          transform: scale(1.1) rotate(5deg);
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }
        
        .feature-icon {
          animation: iconGlow 3s ease-in-out infinite;
        }
        .feature-item:nth-child(1) .feature-icon { animation-delay: 0s; }
        .feature-item:nth-child(2) .feature-icon { animation-delay: 1s; }
        .feature-item:nth-child(3) .feature-icon { animation-delay: 2s; }
      `}</style>
      {/* Main Container */}
      <Row
        style={{
          width: '100%',
          maxWidth: '1400px',
          margin: '0 auto',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Left Brand Section - Hidden on mobile */}
        <Col
          xs={0}
          md={0}
          lg={12}
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'flex-start',
            padding: '60px 80px',
            animation: 'slideInLeft 0.8s ease-out',
          }}
        >
          {/* Logo Section */}
          <div style={{ marginBottom: '48px' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '72px',
                height: '72px',
                borderRadius: '20px',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                boxShadow: '0 8px 24px rgba(102, 126, 234, 0.4)',
                marginBottom: '24px',
              }}
            >
              <ApiOutlined style={{ fontSize: '36px', color: '#fff' }} />
            </div>
            <AntTitle
              level={1}
              style={{
                color: '#fff',
                fontSize: '48px',
                margin: '0 0 16px 0',
                fontWeight: '700',
                letterSpacing: '-0.5px',
              }}
            >
              慧眼数据平台
            </AntTitle>
            <Paragraph
              style={{
                color: 'rgba(255, 255, 255, 0.7)',
                fontSize: '18px',
                margin: 0,
                lineHeight: '1.8',
              }}
            >
              企业级AI智能数据分析平台
              <br />
              让数据洞察触手可及
            </Paragraph>
          </div>

          {/* Feature List */}
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <div className="feature-item" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                className="feature-icon-box"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.15)',
                  backdropFilter: 'blur(10px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <ThunderboltOutlined
                  className="feature-icon"
                  style={{ fontSize: '24px', color: '#ffd666' }}
                />
              </div>
              <div>
                <div
                  style={{
                    color: '#fff',
                    fontSize: '16px',
                    fontWeight: '600',
                    marginBottom: '4px',
                  }}
                >
                  自然语言查询
                </div>
                <div
                  style={{
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '14px',
                  }}
                >
                  用对话方式问数据,AI自动生成SQL
                </div>
              </div>
            </div>
          
            <div className="feature-item" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                className="feature-icon-box"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.15)',
                  backdropFilter: 'blur(10px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <TeamOutlined
                  className="feature-icon"
                  style={{ fontSize: '24px', color: '#ff85c0' }}
                />
              </div>
              <div>
                <div
                  style={{
                    color: '#fff',
                    fontSize: '16px',
                    fontWeight: '600',
                    marginBottom: '4px',
                  }}
                >
                  多Agent协作
                </div>
                <div
                  style={{
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '14px',
                  }}
                >
                  LangGraph多智能体协同,智能任务分发
                </div>
              </div>
            </div>
          
            <div className="feature-item" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                className="feature-icon-box"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.15)',
                  backdropFilter: 'blur(10px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <RocketOutlined
                  className="feature-icon"
                  style={{ fontSize: '24px', color: '#69c0ff' }}
                />
              </div>
              <div>
                <div
                  style={{
                    color: '#fff',
                    fontSize: '16px',
                    fontWeight: '600',
                    marginBottom: '4px',
                  }}
                >
                  智能技能训练
                </div>
                <div
                  style={{
                    color: 'rgba(255, 255, 255, 0.7)',
                    fontSize: '14px',
                  }}
                >
                  知识图谱+混合检索,持续学习业务场景
                </div>
              </div>
            </div>
          </Space>
        </Col>

        {/* Right Form Section */}
        <Col
          xs={24}
          md={24}
          lg={12}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
            animation: 'slideInRight 0.8s ease-out',
          }}
        >
          <Card
            style={{
              width: '100%',
              maxWidth: '480px',
              borderRadius: '24px',
              background: 'rgba(255, 255, 255, 0.98)',
              backdropFilter: 'blur(20px)',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.1)',
              border: 'none',
            }}
            bodyStyle={{
              padding: '48px 40px',
            }}
          >
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {/* Mobile Logo - Only shown on small screens */}
              <div
                style={{
                  textAlign: 'center',
                  marginBottom: '20px',
                  display: 'none',
                }}
                className="mobile-logo"
              >
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '56px',
                    height: '56px',
                    borderRadius: '16px',
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    marginBottom: '16px',
                  }}
                >
                  <ApiOutlined style={{ fontSize: '28px', color: '#fff' }} />
                </div>
                <AntTitle
                  level={3}
                  style={{
                    margin: '0 0 8px 0',
                    background: 'linear-gradient(45deg, #667eea, #764ba2)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    fontWeight: '700',
                  }}
                >
                  慧眼数据平台
                </AntTitle>
                <Paragraph
                  style={{
                    color: '#8c8c8c',
                    margin: 0,
                    fontSize: '14px',
                  }}
                >
                  企业级AI智能数据分析平台
                </Paragraph>
              </div>

              <style>{`
                @media (max-width: 991px) {
                  .mobile-logo {
                    display: block !important;
                  }
                }
                .ant-input-affix-wrapper,
                .ant-input {
                  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                  border: 1px solid rgba(0, 0, 0, 0.06);
                  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
                }
                .ant-input-affix-wrapper:hover,
                .ant-input:hover {
                  border-color: rgba(102, 126, 234, 0.3);
                  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
                }
                .ant-input-affix-wrapper:focus-within,
                .ant-input:focus {
                  border-color: #667eea;
                  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                }
                .ant-btn-primary {
                  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  border: none;
                  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                }
                .ant-btn-primary:hover:not(:disabled) {
                  transform: translateY(-2px);
                  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
                  background: linear-gradient(135deg, #7c8ef5 0%, #8b5dba 100%);
                }
                .ant-btn-primary:active:not(:disabled) {
                  transform: translateY(0);
                }
                .ant-tabs-tab {
                  font-weight: 600;
                  transition: all 0.3s;
                }
                .ant-tabs-ink-bar {
                  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                }
              `}</style>

              {/* Tabs for Login/Register */}
              <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as 'login' | 'register')}
            centered
            items={[
              {
                key: 'login',
                label: '登录',
                children: (
                  <Form
                    name="login"
                    onFinish={handleLogin}
                    layout="vertical"
                    size="large"
                    style={{ marginTop: '8px' }}
                  >
                    <Form.Item
                      name="username"
                      rules={[
                        { required: true, message: '请输入用户名或邮箱' },
                      ]}
                    >
                      <Input
                        prefix={<UserOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="用户名或邮箱"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="password"
                      rules={[
                        { required: true, message: '请输入密码' },
                      ]}
                    >
                      <Input.Password
                        prefix={<LockOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="密码"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item>
                      <Button
                        type="primary"
                        htmlType="submit"
                        loading={loading}
                        block
                        style={{
                          height: '52px',
                          borderRadius: '12px',
                          fontSize: '16px',
                          fontWeight: '600',
                        }}
                      >
                        登录
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
              {
                key: 'register',
                label: '注册',
                children: (
                  <Form
                    name="register"
                    onFinish={handleRegister}
                    layout="vertical"
                    size="large"
                    style={{ marginTop: '8px' }}
                  >
                    <Form.Item
                      name="tenant_name"
                      rules={[
                        { required: true, message: '请输入公司名称' },
                        { min: 2, message: '公司名称至少2个字符' },
                      ]}
                    >
                      <Input
                        prefix={<BankOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="公司名称"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="username"
                      rules={[
                        { required: true, message: '请输入用户名' },
                        { min: 3, message: '用户名至少3个字符' },
                      ]}
                    >
                      <Input
                        prefix={<UserOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="用户名"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="email"
                      rules={[
                        { required: true, message: '请输入邮箱' },
                        { type: 'email', message: '请输入有效的邮箱地址' },
                      ]}
                    >
                      <Input
                        prefix={<MailOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="邮箱"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="display_name"
                    >
                      <Input
                        prefix={<UserOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="显示名称（选填）"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="password"
                      rules={[
                        { required: true, message: '请输入密码' },
                        { min: 6, message: '密码至少6个字符' },
                      ]}
                    >
                      <Input.Password
                        prefix={<LockOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="密码"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item
                      name="confirmPassword"
                      dependencies={['password']}
                      rules={[
                        { required: true, message: '请确认密码' },
                        ({ getFieldValue }) => ({
                          validator(_, value) {
                            if (!value || getFieldValue('password') === value) {
                              return Promise.resolve();
                            }
                            return Promise.reject(new Error('两次输入的密码不一致'));
                          },
                        }),
                      ]}
                    >
                      <Input.Password
                        prefix={<LockOutlined style={{ color: '#8c8c8c' }} />}
                        placeholder="确认密码"
                        style={{
                          borderRadius: '10px',
                          height: '48px',
                        }}
                      />
                    </Form.Item>

                    <Form.Item>
                      <Button
                        type="primary"
                        htmlType="submit"
                        loading={loading}
                        block
                        style={{
                          height: '52px',
                          borderRadius: '12px',
                          fontSize: '16px',
                          fontWeight: '600',
                        }}
                      >
                        注册
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
              ]}
              />
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default LoginPage;
