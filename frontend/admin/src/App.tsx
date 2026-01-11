
import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import type { MenuProps } from 'antd';
import {
  DatabaseOutlined,
  TableOutlined,
  SearchOutlined,
  SwapOutlined,
  HomeOutlined,
  ApiOutlined,
  ShareAltOutlined,
  BulbOutlined
} from '@ant-design/icons';

import './styles/Header.css';
import './styles/global-styles.css';

import HomePage from './pages/HomePage';
import ConnectionsPage from './pages/ConnectionsPage';
import SchemaManagementPage from './pages/SchemaManagementPage';
import IntelligentQueryPage from './pages/IntelligentQueryPage';
import ValueMappingsPage from './pages/ValueMappingsPage';
import GraphVisualizationPage from './pages/GraphVisualizationPage';
import HybridQAPage from './pages/HybridQA';

const { Header, Content } = Layout;

const App: React.FC = () => {
  const location = useLocation();

  const {
    token: { colorBgContainer },
  } = theme.useToken();

  // 子菜单项
  const items: MenuProps['items'] = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">首页</Link>,
    },
    // {
    //   key: '/text2sql',
    //   icon: <SearchOutlined />,
    //   label: <Link to="/text2sql">智能查询</Link>,
    // },
    {
      key: '/hybrid-qa',
      icon: <BulbOutlined />,
      label: <Link to="/hybrid-qa">智能训练</Link>,
    },
    {
      key: '/schema',
      icon: <TableOutlined />,
      label: <Link to="/schema">数据建模</Link>,
    },
    {
      key: '/graph-visualization',
      icon: <ShareAltOutlined />,
      label: <Link to="/graph-visualization">知识图谱</Link>,
    },
    {
      key: '/connections',
      icon: <DatabaseOutlined />,
      label: <Link to="/connections">连接管理</Link>,
    },
    {
      key: '/value-mappings',
      icon: <SwapOutlined />,
      label: <Link to="/value-mappings">数据映射</Link>,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header className="app-header">
        <ApiOutlined style={{ fontSize: '28px', color: '#1890ff', marginRight: '16px' }} />
        <div className="app-title">
          但问智能数据分析系统
        </div>
        <Menu
          className="app-menu"
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={items}
        />
      </Header>
      <Content style={{
        padding: location.pathname === '/' ? '0' : '0 50px',
        marginTop: location.pathname === '/' ? 0 : 16,
        flex: 1,
        display: 'flex',
        flexDirection: 'column'
      }}>
        <div style={{
          padding: location.pathname === '/' ? 0 : 24,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          background: location.pathname === '/' ? 'transparent' : colorBgContainer,
          borderRadius: location.pathname === '/' ? '0' : '2px'
        }}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/text2sql" element={<IntelligentQueryPage />} />
            <Route path="/hybrid-qa" element={<HybridQAPage />} />
            <Route path="/connections" element={<ConnectionsPage />} />
            <Route path="/schema" element={<SchemaManagementPage />} />
            <Route path="/graph-visualization" element={<GraphVisualizationPage />} />
            <Route path="/value-mappings" element={<ValueMappingsPage />} />
          </Routes>
        </div>
      </Content>
    </Layout>
  );
};

export default App;
