import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  BulbOutlined,
  TableOutlined,
  ShareAltOutlined,
  DatabaseOutlined,
  SwapOutlined,
  UserOutlined,
  DashboardOutlined,
  ApiOutlined,
  RobotOutlined,
  TeamOutlined,
  AppstoreOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { message, Modal, type MenuProps } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import '../../styles/Sidebar.css';

const IOSSidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    Modal.confirm({
      title: '退出登录',
      content: '确定要退出登录吗？',
      okText: '确定',
      cancelText: '取消',
      onOk: () => {
        logout();
        message.success('已退出登录');
        navigate('/login');
      }
    });
  };

  // Menu permission mapping
  const menuPermissionMap: Record<string, string> = {
    '/': 'chat',
    '/intelligent-tuning': 'training',
    '/schema': 'training',
    '/graph-visualization': 'training',
    '/dashboards': 'chat',
    '/connections': 'connections',
    '/value-mappings': 'training',
    '/llm-config': 'llm_configs',
    '/agent-profile': 'agents',
    '/users': 'users',
  };

  // Check if user has permission for a menu
  const hasMenuPermission = (path: string): boolean => {
    // Super admin and tenant admin have all permissions
    if (user?.role === 'super_admin' || user?.role === 'tenant_admin') {
      return true;
    }
    
    const menuKey = menuPermissionMap[path];
    if (!menuKey) return true; // No permission required
    
    const permissions = user?.permissions as { menus?: string[] } | null;
    if (!permissions?.menus) return false;
    
    return permissions.menus.includes(menuKey);
  };

  const allMenuItems = [
    { key: '/', icon: <HomeOutlined />, label: '首页', to: '/' },
    { key: '/intelligent-tuning', icon: <BulbOutlined />, label: '智能调优中心', to: '/intelligent-tuning' },
    { key: '/schema', icon: <TableOutlined />, label: '数据建模', to: '/schema' },
    { key: '/graph-visualization', icon: <ShareAltOutlined />, label: '知识图谱', to: '/graph-visualization' },
    { key: '/skills', icon: <AppstoreOutlined />, label: 'Skills', to: '/skills' },
    { key: '/dashboards', icon: <DashboardOutlined />, label: 'BI仪表盘', to: '/dashboards' },
    { key: '/connections', icon: <DatabaseOutlined />, label: '连接管理', to: '/connections' },
    { key: '/value-mappings', icon: <SwapOutlined />, label: '数据映射', to: '/value-mappings' },
    { key: '/llm-config', icon: <ApiOutlined />, label: '模型配置', to: '/llm-config' },
    { key: '/agent-profile', icon: <RobotOutlined />, label: '智能体配置', to: '/agent-profile' },
    { key: '/users', icon: <TeamOutlined />, label: '用户管理', to: '/users', adminOnly: true },
  ];

  // Filter menu items based on permissions
  const menuItems = allMenuItems.filter(item => {
    // Admin-only items
    if (item.adminOnly) {
      return user?.role === 'super_admin' || user?.role === 'tenant_admin';
    }
    return hasMenuPermission(item.to);
  });

  return (
    <aside className="sidebar-container">
      {/* Imitate Window Controls Area Space */}
      <div className="drag-region" /> 
      
      <div className="logo-area" style={{ borderBottom: 'none', marginBottom: 0, paddingBottom: 0 }}>
        <span className="logo-text" style={{ fontSize: '15px', textTransform: 'uppercase', letterSpacing: '0.02em', opacity: 0.9 }}>慧眼数据</span>
      </div>

      <ul className="sidebar-menu">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.to || 
            (item.to === '/dashboards' && location.pathname.startsWith('/dashboards'));
          return (
            <li key={item.key}>
              <Link
                to={item.to}
                className={`menu-item ${isActive ? 'active' : ''}`}
              >
                {isActive && <div className="active-indicator" />}
                <span className="sidebar-icon" style={{ fontSize: '16px' }}>{item.icon}</span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="sidebar-footer">
        <div className="menu-item user-profile">
          <div className="user-avatar-small">
            <UserOutlined style={{ fontSize: '14px' }} />
          </div>
          <span className="user-name">{user?.display_name || user?.username || '用户'}</span>
        </div>
        
        <div 
          className="menu-item" 
          onClick={handleLogout}
          style={{ color: 'var(--color-error)', marginTop: '4px' }}
        >
          <span className="sidebar-icon"><LogoutOutlined /></span>
          退出登录
        </div>
      </div>
    </aside>
  );
};

export default IOSSidebar;
