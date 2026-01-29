import React, { useState } from 'react';
import { BellOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons';
import GlobalConnectionSelector from '../GlobalConnectionSelector';
import '../../styles/TopBar.css';

const TopBar: React.FC = () => {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <header className="glass-panel topbar-container">
      <div className="topbar-left">
        {/* Connection Selector as a Pill */}
        <div className="connection-pill">
          <div className="status-indicator" />
          <div style={{ transform: 'scale(0.9)', marginLeft: '-8px' }}>
             {/* We use the existing component but might need to style it deeply via CSS if we want full transparency.
                 For now, we wrap it. */}
             <GlobalConnectionSelector 
                selectedConnectionId={selectedId} 
                setSelectedConnectionId={setSelectedId} 
             />
          </div>
        </div>
      </div>

      <div className="topbar-right">
        <div className="search-bar">
           <SearchOutlined style={{ marginRight: '8px', opacity: 0.6 }} />
           <span style={{ fontSize: '14px', opacity: 0.6 }}>Search data...</span>
        </div>

        <BellOutlined className="icon-button" />
        
        <div className="user-avatar">
          <UserOutlined />
        </div>
      </div>
    </header>
  );
};

export default TopBar;
