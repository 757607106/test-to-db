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

  const styles = {
    container: {
      width: 'var(--sidebar-width)',
      height: 'calc(100vh - 40px)', // Top and bottom gap
      position: 'fixed' as const,
      left: '20px',
      top: '20px',
      display: 'flex',
      flexDirection: 'column' as const,
      padding: '24px 16px',
      boxSizing: 'border-box' as const,
      zIndex: 100,
    },
    logoArea: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '0 12px 32px 12px',
      marginBottom: '16px',
      borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
    },
    logoIcon: {
      fontSize: '32px',
      color: 'var(--color-primary)',
      filter: 'drop-shadow(0 0 8px rgba(79, 70, 229, 0.5))',
    },
    logoText: {
      fontSize: '18px',
      fontWeight: 700,
      background: 'linear-gradient(135deg, var(--color-text-main) 0%, var(--color-primary) 100%)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      letterSpacing: '-0.5px',
    },
    menu: {
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '8px',
    },
    menuItem: (isActive: boolean) => ({
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '12px 16px',
      borderRadius: '12px',
      color: isActive ? 'var(--color-primary)' : 'var(--color-text-secondary)',
      background: isActive ? 'rgba(255, 255, 255, 0.8)' : 'transparent',
      textDecoration: 'none',
      transition: 'all 0.3s ease',
      position: 'relative' as const,
      fontWeight: isActive ? 600 : 400,
      boxShadow: isActive ? '0 4px 12px rgba(79, 70, 229, 0.15)' : 'none',
      backdropFilter: isActive ? 'blur(10px)' : 'none',
    }),
    activeIndicator: {
      position: 'absolute' as const,
      left: '0',
      top: '50%',
      transform: 'translateY(-50%)',
      width: '4px',
      height: '20px',
      background: 'var(--color-primary)',
      borderRadius: '0 4px 4px 0',
      boxShadow: '0 0 10px var(--color-primary)',
    }
  };

  return (
    <aside className="glass-panel" style={styles.container}>
      <div style={styles.logoArea}>
        <ApiOutlined style={styles.logoIcon} />
        <span style={styles.logoText}>RWX Data</span>
      </div>
      
      <nav style={styles.menu}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.to;
          return (
            <Link 
              key={item.key} 
              to={item.to} 
              style={styles.menuItem(isActive)}
            >
              {isActive && <div style={styles.activeIndicator} />}
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
