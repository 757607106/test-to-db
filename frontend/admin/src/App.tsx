import React from 'react';
import { Routes, Route, Outlet, Navigate } from 'react-router-dom';
import IOSLayout from './components/layout/IOSLayout';
import ProtectedRoute from './components/ProtectedRoute';

import './styles/global-styles.css';
import './styles/ios-theme.css';

import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import ConnectionsPage from './pages/ConnectionsPage';
import SchemaManagementPage from './pages/SchemaManagementPage';
import IntelligentQueryPage from './pages/IntelligentQueryPage';
import ValueMappingsPage from './pages/ValueMappingsPage';
import GraphVisualizationPage from './pages/GraphVisualizationPage';
import HybridQAPage from './pages/HybridQA';
import DashboardListPage from './pages/DashboardListPage';
import DashboardEditorPage from './pages/DashboardEditorPage';
import LLMConfigPage from './pages/LLMConfig';
import AgentProfilePage from './pages/AgentProfile';
import UsersPage from './pages/UsersPage';
import MetricsPage from './pages/MetricsPage';
import SkillsPage from './pages/SkillsPage';

// Layout wrapper that uses IOSLayout with Outlet
const ProtectedLayout: React.FC = () => {
  return (
    <IOSLayout>
      <Outlet />
    </IOSLayout>
  );
};

const App: React.FC = () => {
  return (
    <Routes>
      {/* Public route - Login */}
      <Route path="/login" element={<LoginPage />} />
      
      {/* Protected routes - require authentication */}
      <Route element={<ProtectedRoute />}>
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/text2sql" element={<IntelligentQueryPage />} />
          <Route path="/hybrid-qa" element={<HybridQAPage />} />
          <Route path="/connections" element={<ConnectionsPage />} />
          <Route path="/schema" element={<SchemaManagementPage />} />
          <Route path="/graph-visualization" element={<GraphVisualizationPage />} />
          <Route path="/value-mappings" element={<ValueMappingsPage />} />
          <Route path="/dashboards" element={<DashboardListPage />} />
          <Route path="/dashboards/:id" element={<DashboardEditorPage />} />
          <Route path="/metrics" element={<MetricsPage />} />
          <Route path="/join-rules" element={<Navigate to="/skills" replace />} />
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/llm-config" element={<LLMConfigPage />} />
          <Route path="/agent-profile" element={<AgentProfilePage />} />
          <Route path="/users" element={<UsersPage />} />
        </Route>
      </Route>
    </Routes>
  );
};

export default App;
