import React from 'react';
import { BellOutlined, SearchOutlined, UserOutlined, SunOutlined, MoonOutlined } from '@ant-design/icons';
import { useTheme } from '../../contexts/ThemeContext';
import { Tooltip } from 'antd';
import '../../styles/TopBar.css';

const TopBar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="glass-panel topbar-container">
      <div className="topbar-left">
        {/* 数据库选择器已移至知识图谱页面内 */}
      </div>

      <div className="topbar-right">
        <div className="search-bar">
           <SearchOutlined style={{ marginRight: '8px', opacity: 0.6 }} />
           <span style={{ fontSize: '14px', opacity: 0.6 }}>Search data...</span>
        </div>

        <Tooltip title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}>
          <div className="icon-button" onClick={toggleTheme}>
            {theme === 'light' ? <MoonOutlined /> : <SunOutlined />}
          </div>
        </Tooltip>

        <BellOutlined className="icon-button" />
        
        <div className="user-avatar">
          <UserOutlined />
        </div>
      </div>
    </header>
  );
};

export default TopBar;
