import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  DatabaseOutlined,
  TableOutlined,
  SwapOutlined,
  HomeOutlined,
  ApiOutlined,
  ShareAltOutlined,
  BulbOutlined
} from '@ant-design/icons';
import '../../styles/Sidebar.css';

const Sidebar: React.FC = () => {
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: '首页', to: '/' },
    { key: '/hybrid-qa', icon: <BulbOutlined />, label: '智能训练', to: '/hybrid-qa' },
    { key: '/schema', icon: <TableOutlined />, label: '数据建模', to: '/schema' },
    { key: '/graph-visualization', icon: <ShareAltOutlined />, label: '知识图谱', to: '/graph-visualization' },
    { key: '/connections', icon: <DatabaseOutlined />, label: '连接管理', to: '/connections' },
    { key: '/value-mappings', icon: <SwapOutlined />, label: '数据映射', to: '/value-mappings' },
  ];

  return (
    <aside className="glass-panel sidebar-container">
      <div className="logo-area">
        <ApiOutlined className="logo-icon" />
        <span className="logo-text">RWX Data</span>
      </div>

      <nav className="sidebar-menu">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.to || 
                          (item.to !== '/' && location.pathname.startsWith(item.to));
          
          return (
            <Link
              key={item.key}
              to={item.to}
              className={`menu-item ${isActive ? 'active' : ''}`}
            >
              {isActive && <div className="active-indicator" />}
              <span style={{ fontSize: '20px' }}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
};

export default Sidebar;
