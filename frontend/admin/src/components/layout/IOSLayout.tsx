import React from 'react';
import IOSSidebar from './IOSSidebar';
import IOSTopBar from './IOSTopBar';

interface IOSLayoutProps {
  children: React.ReactNode;
}

const IOSLayout: React.FC<IOSLayoutProps> = ({ children }) => {
  const styles = {
    container: {
      display: 'flex',
      minHeight: '100vh',
      background: 'var(--bg-base)',
      transition: 'background-color var(--transition-speed) var(--transition-ease)',
    },
    sidebarWrapper: {
      width: 'var(--sidebar-width)',
      flexShrink: 0,
    },
    mainWrapper: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
      // macOS Style: Tighter integration, usually flush or small gap.
      // We will make it flush with the sidebar for a "Split View" look, 
      // but keep the content area distinct.
      marginLeft: 'var(--sidebar-width)', 
      background: 'var(--bg-card)',
      position: 'relative' as const,
      height: '100vh',
      transition: 'background-color var(--transition-speed) var(--transition-ease)',
      boxShadow: '-1px 0 0 0 var(--glass-border)', // Divider line
    },
    contentArea: {
      flex: 1,
      overflowY: 'auto' as const,
      padding: '24px',
      position: 'relative' as const,
    }
  };

  return (
    <div style={styles.container} className="ios-layout">
      <IOSSidebar />
      <div style={styles.mainWrapper} className="ios-layout-main">
        <IOSTopBar />
        <main style={styles.contentArea} className="page-content-enter ios-layout-content">
          {children}
        </main>
      </div>
    </div>
  );
};

export default IOSLayout;
