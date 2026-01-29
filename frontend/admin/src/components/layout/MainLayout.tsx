import React from 'react';
import AppBackground from './AppBackground';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import '../../styles/Layout.css';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <>
      <AppBackground />
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <TopBar />
          <div className="content-wrapper">
            {children}
          </div>
        </main>
      </div>
    </>
  );
};

export default MainLayout;
