import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  BulbOutlined,
  TableOutlined,
  ShareAltOutlined,
  DatabaseOutlined,
  SwapOutlined,
  SettingOutlined,
  UserOutlined,
  DashboardOutlined,
  ApiOutlined,
  RobotOutlined,
  TeamOutlined,
  FunctionOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { message } from 'antd';
import { useAuth } from '../../contexts/AuthContext';

const IOSSidebar: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();

  // Menu permission mapping
  const menuPermissionMap: Record<string, string> = {
    '/': 'chat',
    '/hybrid-qa': 'training',
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
    { key: '/hybrid-qa', icon: <BulbOutlined />, label: '智能训练', to: '/hybrid-qa' },
    { key: '/schema', icon: <TableOutlined />, label: '数据建模', to: '/schema' },
    { key: '/graph-visualization', icon: <ShareAltOutlined />, label: '知识图谱', to: '/graph-visualization' },
    { key: '/metrics', icon: <FunctionOutlined />, label: '指标库', to: '/metrics' },
    { key: '/skills', icon: <AppstoreOutlined />, label: 'Skills', to: '/skills' },
    { key: '/dashboards', icon: <DashboardOutlined />, label: 'BI仪表盘', to: '/dashboards' },
    { key: '/connections', icon: <DatabaseOutlined />, label: '连接管理', to: '/connections' },
    { key: '/value-mappings', icon: <SwapOutlined />, label: '数据映射', to: '/value-mappings' },
    { key: '/llm-config', icon: <ApiOutlined />, label: '模型配置', to: '/llm-config' },
    { key: '/sql-enhancement', icon: <SettingOutlined />, label: 'SQL增强配置', to: '/sql-enhancement' },
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

  const styles = {
    sidebar: {
      width: 'var(--sidebar-width)',
      height: '100vh',
      background: 'var(--glass-bg)',
      backdropFilter: 'blur(var(--blur-amount)) saturate(180%)',
      WebkitBackdropFilter: 'blur(var(--blur-amount)) saturate(180%)',
      borderRight: '1px solid var(--glass-border)',
      display: 'flex',
      flexDirection: 'column' as const,
      padding: '0 8px', // Adjusted for macOS spacing
      boxSizing: 'border-box' as const,
      position: 'fixed' as const,
      left: 0,
      top: 0,
      zIndex: 1000,
      transition: 'all var(--transition-speed) var(--transition-ease)',
    },
    logoArea: {
      height: '52px', // Compact toolbar height
      display: 'flex',
      alignItems: 'center',
      paddingLeft: '12px',
      marginTop: '0', // Flush to top traffic lights area (conceptually)
      marginBottom: '10px',
    },
    logoText: {
      fontSize: '15px', // Increased from 13px
      fontWeight: 600,
      color: 'var(--text-secondary)', // Sidebar titles are usually subtle in macOS
      fontFamily: 'var(--font-stack)',
      letterSpacing: '0.02em',
      textTransform: 'uppercase' as const,
      opacity: 0.9,
      paddingLeft: '4px', // Align with new padding
    },
    menuList: {
      listStyle: 'none',
      padding: 0,
      margin: 0,
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
    },
    bottomSection: {
      padding: '10px 0 16px 0',
      borderTop: '1px solid var(--glass-border)',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '2px',
    },
  };

  return (
    <aside style={styles.sidebar} className="ios-layout-sidebar">
      {/* Imitate Window Controls Area Space */}
      <div style={{ height: '38px', WebkitAppRegion: 'drag' } as any} /> 
      
      <div style={styles.logoArea}>
        <span style={styles.logoText}>RWX Admin</span>
      </div>

      <ul style={styles.menuList}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.to || 
            (item.to === '/dashboards' && location.pathname.startsWith('/dashboards'));
          return (
            <li key={item.key}>
              <Link
                to={item.to}
                className={`macos-sidebar-item ${isActive ? 'active' : ''}`}
              >
                <span className="sidebar-icon">{item.icon}</span>
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>

      <div style={styles.bottomSection}>
        <div className="macos-sidebar-item">
          <SettingOutlined className="sidebar-icon" style={{ fontSize: '18px' }} />
          <span style={{ fontWeight: 500 }}>设置</span>
        </div>
        <div className="macos-sidebar-item">
          <div style={{ 
            width: '24px', 
            height: '24px', 
            borderRadius: '50%', 
            background: 'var(--bg-tertiary)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            marginRight: '12px',
            color: 'var(--text-secondary)'
          }}>
            <UserOutlined style={{ fontSize: '14px' }} />
          </div>
          <span style={{ fontWeight: 500 }}>{user?.display_name || user?.username || '用户'}</span>
        </div>
      </div>
    </aside>
  );
};

export default IOSSidebar;
