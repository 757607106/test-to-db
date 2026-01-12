import React from 'react';
import AppBackground from './AppBackground';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const styles = {
    layout: {
      display: 'flex',
      minHeight: '100vh',
      position: 'relative' as const,
      padding: '20px',
      boxSizing: 'border-box' as const,
    },
    main: {
      marginLeft: 'calc(var(--sidebar-width) + 20px)', // Sidebar width + gap
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
      minWidth: 0, // Prevent flex overflow
    },
    contentWrapper: {
      flex: 1,
      padding: '24px',
      overflow: 'auto',
      position: 'relative' as const,
    }
  };

  return (
    <>
      <AppBackground />
      <div style={styles.layout}>
        <Sidebar />
        <main style={styles.main}>
          <TopBar />
          <div className="glass-panel" style={styles.contentWrapper}>
            {children}
          </div>
        </main>
      </div>
    </>
  );
};

export default MainLayout;
