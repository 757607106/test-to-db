import React from 'react';

const AppBackground: React.FC = () => {
  const styles = {
    container: {
      position: 'fixed' as const,
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      zIndex: -1,
      overflow: 'hidden',
      background: 'var(--color-bg-page)',
      transition: 'background var(--transition-speed) var(--transition-ease)',
    },
    orb1: {
      position: 'absolute' as const,
      top: '10%',
      left: '20%',
      width: '600px',
      height: '600px',
      background: 'radial-gradient(circle, var(--color-primary) 0%, rgba(79, 70, 229, 0) 70%)',
      opacity: 0.15,
      filter: 'blur(60px)',
      borderRadius: '50%',
      animation: 'float-orb 20s infinite ease-in-out',
    },
    orb2: {
      position: 'absolute' as const,
      top: '40%',
      right: '10%',
      width: '500px',
      height: '500px',
      background: 'radial-gradient(circle, var(--color-secondary) 0%, rgba(129, 140, 248, 0) 70%)',
      opacity: 0.15,
      filter: 'blur(50px)',
      borderRadius: '50%',
      animation: 'float-orb 25s infinite ease-in-out reverse',
    },
    orb3: {
      position: 'absolute' as const,
      bottom: '-10%',
      left: '30%',
      width: '700px',
      height: '700px',
      background: 'radial-gradient(circle, var(--color-accent) 0%, rgba(45, 212, 191, 0) 70%)',
      opacity: 0.12,
      filter: 'blur(70px)',
      borderRadius: '50%',
      animation: 'float-orb 30s infinite ease-in-out 2s',
    },
    grid: {
      position: 'absolute' as const,
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      backgroundImage: 'radial-gradient(rgba(0,0,0,0.03) 1px, transparent 1px)',
      backgroundSize: '40px 40px',
      opacity: 0.5,
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.orb1} />
      <div style={styles.orb2} />
      <div style={styles.orb3} />
      <div style={styles.grid} />
    </div>
  );
};

export default AppBackground;
