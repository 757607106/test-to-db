import React from 'react';
import { Routes, Route } from 'react-router-dom';
import IOSLayout from './components/layout/IOSLayout';

import './styles/global-styles.css';
import './styles/ios-theme.css';

import HomePage from './pages/HomePage';
import ConnectionsPage from './pages/ConnectionsPage';
import SchemaManagementPage from './pages/SchemaManagementPage';
import IntelligentQueryPage from './pages/IntelligentQueryPage';
import ValueMappingsPage from './pages/ValueMappingsPage';
import GraphVisualizationPage from './pages/GraphVisualizationPage';
import HybridQAPage from './pages/HybridQA';

const App: React.FC = () => {
  return (
    <IOSLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/text2sql" element={<IntelligentQueryPage />} />
        <Route path="/hybrid-qa" element={<HybridQAPage />} />
        <Route path="/connections" element={<ConnectionsPage />} />
        <Route path="/schema" element={<SchemaManagementPage />} />
        <Route path="/graph-visualization" element={<GraphVisualizationPage />} />
        <Route path="/value-mappings" element={<ValueMappingsPage />} />
      </Routes>
    </IOSLayout>
  );
};

export default App;
