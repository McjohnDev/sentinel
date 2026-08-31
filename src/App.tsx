/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { ToastContainer } from './components/common/ToastContainer';

import { LoginView } from './views/LoginView';
import { DashboardView } from './views/DashboardView';
import { AgentsListView } from './views/AgentsListView';
import { AgentDetailView } from './views/AgentDetailView';
import { AlertsListView } from './views/AlertsListView';
import { SettingsView } from './views/SettingsView';
import { UsersView } from './views/UsersView';
import { IntegrationsView } from './views/IntegrationsView';
import { AuditView } from './views/AuditView';
import { ProfileView } from './views/ProfileView';
import { I18nProvider } from './i18n';

const LoginRoute: React.FC = () => {
  const { currentUser } = useApp();
  if (currentUser) return <Navigate to="/dashboard" replace />;
  return <LoginView />;
};

const MainLayout: React.FC = () => {
  const { currentUser } = useApp();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  if (!currentUser) {
    return (
      <div className="min-h-screen font-sans antialiased">
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <ToastContainer />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen font-sans text-slate-900 antialiased" style={{ background: '#F1F5F9' }}>
      <Sidebar
        isMobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <Header onToggleSidebarMobile={() => setMobileSidebarOpen(true)} />

        <main className="flex-1 px-4 sm:px-7 lg:px-8 py-6 lg:py-7 overflow-y-auto animate-fade-in">
          <div className="max-w-[1280px] mx-auto space-y-6">
            <Routes>
              <Route path="/dashboard" element={<DashboardView />} />
              <Route path="/agents" element={<AgentsListView />} />
              <Route path="/fleet" element={<AgentsListView />} />
              <Route path="/agents/:id" element={<AgentDetailView />} />
              <Route path="/fleet/:id" element={<AgentDetailView />} />
              <Route path="/alerts" element={<AlertsListView />} />
              <Route path="/integrations" element={<IntegrationsView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="/users" element={<UsersView />} />
              <Route path="/audit" element={<AuditView />} />
              <Route path="/profile" element={<ProfileView />} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </div>
        </main>
      </div>

      <ToastContainer />
    </div>
  );
};

export default function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
        <AppProvider>
          <MainLayout />
        </AppProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}
