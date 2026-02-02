import React from 'react';
import { useLocation } from 'react-router-dom';
import { SearchOutlined, BellOutlined, BulbOutlined, BulbFilled } from '@ant-design/icons';
import { Tooltip } from 'antd';
import GlobalConnectionSelector from '../GlobalConnectionSelector';
import { useTheme } from '../../contexts/ThemeContext';
import '../../styles/TopBar.css';

const IOSTopBar: React.FC = () => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [selectedId, setSelectedId] = React.useState<number | null>(null);

  const getTitle = (pathname: string) => {
    // Handle sub-paths by matching the start of the pathname
    if (pathname === '/') return '首页';
    if (pathname.startsWith('/intelligent-tuning')) return '智能调优中心';
    if (pathname.startsWith('/schema')) return '数据建模';
    if (pathname.startsWith('/graph-visualization')) return '知识图谱';
    if (pathname.startsWith('/skills')) return 'Skills';
    if (pathname.startsWith('/dashboards')) return 'BI仪表盘';
    if (pathname.startsWith('/connections')) return '连接管理';
    if (pathname.startsWith('/value-mappings')) return '数据映射';
    if (pathname.startsWith('/llm-config')) return '模型配置';
    if (pathname.startsWith('/agent-profile')) return '智能体配置';
    if (pathname.startsWith('/users')) return '用户管理';
    
    return '仪表盘';
  };

  return (
    <header className="topbar-container">
      <div className="topbar-left">
        <div style={{ 
          fontSize: '18px', 
          fontWeight: 600, 
          color: 'var(--color-text-main)', 
          fontFamily: 'var(--font-stack)' 
        }}>
          {getTitle(location.pathname)}
        </div>
      </div>
      
      <div className="topbar-right">
        <div style={{ transform: 'scale(0.95)' }}>
          <GlobalConnectionSelector 
             selectedConnectionId={selectedId} 
             setSelectedConnectionId={setSelectedId} 
          />
        </div>
        
        <div className="search-bar">
          <SearchOutlined style={{ marginRight: 8, fontSize: '16px' }} />
          <input 
            type="text" 
            placeholder="搜索..." 
            style={{ 
              border: 'none', 
              background: 'transparent', 
              outline: 'none', 
              color: 'inherit', 
              width: '100%',
              fontSize: '14px'
            }} 
          />
        </div>

        <button className="icon-button">
          <BellOutlined />
        </button>

        <Tooltip title={theme === 'light' ? '切换到深色模式' : '切换到浅色模式'}>
          <button className="icon-button" onClick={toggleTheme}>
            {theme === 'light' ? (
              <BulbOutlined />
            ) : (
              <BulbFilled style={{ color: 'var(--color-accent)' }} />
            )}
          </button>
        </Tooltip>
      </div>
    </header>
  );
};

export default IOSTopBar;
