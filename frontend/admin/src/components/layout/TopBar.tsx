import React, { useState } from 'react';
import { BellOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons';
import GlobalConnectionSelector from '../GlobalConnectionSelector';

const TopBar: React.FC = () => {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const styles = {
    container: {
      height: 'var(--header-height)',
      marginBottom: 'var(--layout-gap)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
    },
    leftSection: {
      display: 'flex',
      alignItems: 'center',
      gap: '24px',
    },
    rightSection: {
      display: 'flex',
      alignItems: 'center',
      gap: '20px',
    },
    searchBar: {
      display: 'flex',
      alignItems: 'center',
      background: 'rgba(255, 255, 255, 0.1)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '20px',
      padding: '8px 16px',
      width: '300px',
      color: 'var(--color-text-secondary)',
    },
    connectionPill: {
      display: 'flex',
      alignItems: 'center',
      background: 'rgba(255, 255, 255, 0.15)',
      backdropFilter: 'blur(10px)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      borderRadius: '50px',
      padding: '4px 16px 4px 8px',
      gap: '8px',
      transition: 'all 0.3s ease',
      cursor: 'pointer',
    },
    indicator: {
      width: '8px',
      height: '8px',
      borderRadius: '50%',
      background: '#2dd4bf', // teal-400
      boxShadow: '0 0 8px #2dd4bf',
      animation: 'pulse-glow 2s infinite',
    },
    iconButton: {
      fontSize: '20px',
      color: 'var(--color-text-secondary)',
      cursor: 'pointer',
      padding: '8px',
      borderRadius: '50%',
      transition: 'background 0.3s',
    },
    avatar: {
      width: '36px',
      height: '36px',
      borderRadius: '50%',
      background: 'linear-gradient(135deg, #4f46e5, #818cf8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontWeight: 600,
      border: '2px solid rgba(255, 255, 255, 0.5)',
    }
  };

  return (
    <header className="glass-panel" style={styles.container}>
      <div style={styles.leftSection}>
        {/* Connection Selector as a Pill */}
        <div style={styles.connectionPill}>
          <div style={styles.indicator} />
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

      <div style={styles.rightSection}>
        <div style={styles.searchBar}>
           <SearchOutlined style={{ marginRight: '8px', opacity: 0.6 }} />
           <span style={{ fontSize: '14px', opacity: 0.6 }}>Search data...</span>
        </div>

        <BellOutlined style={styles.iconButton} />
        
        <div style={styles.avatar}>
          <UserOutlined />
        </div>
      </div>
      
      <style>{`
        /* Local override for Ant Select inside the pill */
        .global-connection-selector .ant-select-selector {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          color: var(--color-text-main) !important;
        }
        .global-connection-selector .ant-select-arrow {
          color: var(--color-text-secondary);
        }
      `}</style>
    </header>
  );
};

export default TopBar;
