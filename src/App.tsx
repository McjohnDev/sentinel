/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
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

// Protected Route Component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser } = useApp();

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Login Route Component
const LoginRoute: React.FC = () => {
  const { currentUser } = useApp();

  if (currentUser) {
    return <Navigate to="/dashboard" replace />;
  }

  return <LoginView />;
};

const MainLayout: React.FC = () => {
  const { currentUser } = useApp();

  if (!currentUser) {
    return (
      <div className="min-h-screen bg-slate-900 font-sans antialiased">
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <ToastContainer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100/70 font-sans text-slate-900 antialiased flex flex-col">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto max-w-7xl mx-auto w-full space-y-6">
          <Routes>
            <Route path="/dashboard" element={<DashboardView />} />
            <Route path="/agents" element={<AgentsListView />} />
            <Route path="/agents/:id" element={<AgentDetailView />} />
            <Route path="/alerts" element={<AlertsListView />} />
            <Route path="/settings" element={<SettingsView />} />
            <Route path="/users" element={<UsersView />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>

      <ToastContainer />
    </div>
  );
};

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <MainLayout />
      </AppProvider>
    </BrowserRouter>
  );
}
