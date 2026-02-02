import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import * as api from '../services/api';

interface Connection {
  id: number;
  name: string;
  type?: string;
  database?: string;
  // Add other properties as needed from your API response
}

interface GlobalConnectionContextType {
  connections: Connection[];
  selectedConnectionId: number | null;
  selectedConnection: Connection | null;
  setSelectedConnectionId: (id: number | null) => void;
  loading: boolean;
  refreshConnections: () => Promise<void>;
}

const GlobalConnectionContext = createContext<GlobalConnectionContextType | undefined>(undefined);

export const GlobalConnectionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshConnections = async () => {
    setLoading(true);
    try {
      const response = await api.getConnections();
      // Ensure we handle the response data correctly based on your API structure
      const data = Array.isArray(response.data) ? response.data : [];
      setConnections(data);
      
      // If there are connections but none selected, optionally select the first one
      // or recover from local storage (future enhancement)
    } catch (error) {
      console.error('Failed to fetch connections:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshConnections();
  }, []);

  const selectedConnection = connections.find(c => c.id === selectedConnectionId) || null;

  return (
    <GlobalConnectionContext.Provider
      value={{
        connections,
        selectedConnectionId,
        selectedConnection,
        setSelectedConnectionId,
        loading,
        refreshConnections
      }}
    >
      {children}
    </GlobalConnectionContext.Provider>
  );
};

export const useGlobalConnection = () => {
  const context = useContext(GlobalConnectionContext);
  if (context === undefined) {
    throw new Error('useGlobalConnection must be used within a GlobalConnectionProvider');
  }
  return context;
};
