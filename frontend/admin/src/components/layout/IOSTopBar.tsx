import React from 'react';
import { useLocation } from 'react-router-dom';
import { SearchOutlined, BellOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import GlobalConnectionSelector from '../GlobalConnectionSelector';

const IOSTopBar: React.FC = () => {
  const location = useLocation();
  const [selectedId, setSelectedId] = React.useState<number | null>(null);

  const getTitle = (pathname: string) => {
    switch (pathname) {
      case '/': return '首页概览';
      case '/hybrid-qa': return '智能训练中心';
      case '/schema': return '数据建模';
      case '/graph-visualization': return '知识图谱';
      case '/connections': return '连接管理';
      case '/value-mappings': return '数据映射';
      default: return '仪表盘';
    }
  };

  const styles = {
    header: {
      height: 'var(--header-height)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      background: 'var(--glass-bg)',
      backdropFilter: 'blur(var(--blur-amount)) saturate(180%)',
      WebkitBackdropFilter: 'blur(var(--blur-amount)) saturate(180%)',
      borderBottom: '1px solid var(--glass-border)',
      position: 'sticky' as const,
      top: 0,
      zIndex: 100,
      transition: 'all var(--transition-speed) var(--transition-ease)',
    },
    leftGroup: {
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
    },
    title: {
      fontSize: 'var(--font-size-header)',
      fontWeight: 600,
      color: 'var(--text-primary)',
      letterSpacing: '-0.01em',
      fontFamily: 'var(--font-stack)',
      marginLeft: '12px',
    },
    rightSection: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px', // Tighter spacing for toolbar items
    },
    navControls: {
      display: 'flex',
      gap: '0px',
    }
  };

  return (
    <header style={styles.header}>
      <div style={styles.leftGroup}>
        {/* Navigation History Buttons (Imitation) */}
        <div style={styles.navControls}>
          <button className="macos-toolbar-btn">
            <LeftOutlined style={{ fontSize: '14px' }} />
          </button>
          <button className="macos-toolbar-btn">
            <RightOutlined style={{ fontSize: '14px' }} />
          </button>
        </div>
        <div style={styles.title}>{getTitle(location.pathname)}</div>
      </div>
      
      <div style={styles.rightSection}>
        <div style={{ transform: 'scale(0.9)', marginRight: '8px' }}>
          <GlobalConnectionSelector 
             selectedConnectionId={selectedId} 
             setSelectedConnectionId={setSelectedId} 
          />
        </div>
        
        {/* Search Input Imitation */}
        <div style={{ position: 'relative', marginRight: '8px' }}>
          <SearchOutlined style={{ 
            position: 'absolute', 
            left: '10px', 
            top: '50%', 
            transform: 'translateY(-50%)', 
            fontSize: '14px', 
            color: 'var(--text-secondary)',
            pointerEvents: 'none'
          }} />
          <input 
            type="text" 
            placeholder="搜索" 
            className="macos-search-input"
          />
        </div>

        <button className="macos-toolbar-btn">
          <BellOutlined style={{ fontSize: '16px' }} />
        </button>
      </div>
    </header>
  );
};

export default IOSTopBar;
